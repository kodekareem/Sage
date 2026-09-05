"""Tests for rate-limit (HTTP 429) handling in the LLM engines.

A real Groq free-tier run hit a token-per-minute cap mid-trace and lost the
whole run. These tests pin the behaviour that replaced it: a rate-limited turn
is retried with backoff, a run that recovers still completes, and a run that
cannot recover reports a *rate limit* rather than a generic failure — so nobody
goes looking for a bad key when the key is fine.

They run offline and never actually sleep: ``_sleep`` is captured so the backoff
schedule can be asserted directly.
"""

from __future__ import annotations

import json

import pytest

from sage.agent import GroqEngine, LLMEngine, RateLimitError, _parse_duration


class FakeResponse:
    """Minimal stand-in for a ``requests`` response."""

    def __init__(self, status_code: int, payload: dict, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code} Client Error")


class FlakyEngine(LLMEngine):
    """An engine that is rate-limited for the first ``fail_times`` calls."""

    name = "flaky"

    def __init__(self, fail_times: int, retry_after=None, **kwargs):
        super().__init__(**kwargs)
        self.fail_times = fail_times
        self.retry_after = retry_after
        self.calls = 0
        self.slept: list[float] = []
        self.backoff_base = 1.0

    def complete(self, messages):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RateLimitError("rate limit exceeded", retry_after=self.retry_after)
        return 'Thought: done\nFinal Answer: {"recommendation": "HOLD", ' \
               '"confidence": "low", "rationale": "ok"}'

    def _sleep(self, seconds: float) -> None:
        self.slept.append(seconds)  # record instead of waiting


# --------------------------------------------------------------------------- #
# Retry behaviour
# --------------------------------------------------------------------------- #
def test_a_transient_rate_limit_is_retried_and_succeeds():
    engine = FlakyEngine(fail_times=2)
    text = engine.complete_with_retry([{"role": "user", "content": "hi"}])

    assert "Final Answer" in text
    assert engine.calls == 3          # two refusals, then success
    assert len(engine.slept) == 2     # it waited between attempts


def test_backoff_grows_exponentially():
    engine = FlakyEngine(fail_times=3)
    engine.complete_with_retry([{"role": "user", "content": "hi"}])
    # 1s, 2s, 4s — each wait doubles rather than hammering the provider.
    assert engine.slept == [1.0, 2.0, 4.0]


def test_provider_retry_after_is_honoured_over_backoff():
    engine = FlakyEngine(fail_times=1, retry_after=7.5)
    engine.complete_with_retry([{"role": "user", "content": "hi"}])
    assert engine.slept == [7.5]


def test_backoff_is_capped():
    """A provider asking for an absurd wait cannot stall the run indefinitely."""
    engine = FlakyEngine(fail_times=1, retry_after=9999)
    engine.complete_with_retry([{"role": "user", "content": "hi"}])
    assert engine.slept == [engine.backoff_cap]


def test_persistent_rate_limit_gives_up_after_max_retries():
    engine = FlakyEngine(fail_times=99)
    with pytest.raises(RateLimitError):
        engine.complete_with_retry([{"role": "user", "content": "hi"}])
    # One initial attempt plus max_retries retries, and no more.
    assert engine.calls == engine.max_retries + 1


def test_non_rate_limit_errors_are_not_retried():
    """A bad key must fail immediately; retrying it only wastes the user's time."""
    class BrokenEngine(LLMEngine):
        name = "broken"

        def __init__(self):
            super().__init__()
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            raise RuntimeError("401 Unauthorized")

        def _sleep(self, seconds):  # pragma: no cover - must never run
            raise AssertionError("a non-rate-limit error must not be retried")

    engine = BrokenEngine()
    with pytest.raises(RuntimeError):
        engine.complete_with_retry([{"role": "user", "content": "hi"}])
    assert engine.calls == 1


# --------------------------------------------------------------------------- #
# What the run reports
# --------------------------------------------------------------------------- #
def test_run_recovers_from_a_transient_rate_limit():
    """The whole ReAct run survives a rate limit that clears."""
    engine = FlakyEngine(fail_times=2)
    result = engine.run("Should I buy NVDA right now?")

    assert result.error is None
    assert result.final is not None
    assert result.final.recommendation == "HOLD"


def test_run_reports_a_rate_limit_as_a_rate_limit_not_a_bad_key():
    engine = FlakyEngine(fail_times=99)
    result = engine.run("Should I buy NVDA right now?")

    assert result.final is None
    assert result.error is not None
    lowered = result.error.lower()
    assert "rate-limiting" in lowered
    # It must actively reassure that the key is fine, and point somewhere useful.
    assert "the key is valid" in lowered
    assert "rule" in lowered
    # And it must NOT accuse the key.
    assert "invalid api key" not in lowered


# --------------------------------------------------------------------------- #
# Groq's 429 shape
# --------------------------------------------------------------------------- #
@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    return GroqEngine(model="test-model", url="https://example.invalid/v1")


def test_groq_raises_rate_limit_error_on_429(groq, monkeypatch):
    payload = {"error": {"message": "Rate limit reached for model", "code": "rate_limit_exceeded"}}
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: FakeResponse(429, payload, {"retry-after": "3"}),
    )

    with pytest.raises(RateLimitError) as excinfo:
        groq.complete([{"role": "user", "content": "hi"}])

    assert excinfo.value.retry_after == 3.0
    assert "Rate limit reached" in str(excinfo.value)


def test_groq_reads_the_token_reset_window_when_no_retry_after(groq, monkeypatch):
    """Groq exposes the token window as e.g. '172ms'; use it when present."""
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: FakeResponse(
            429, {"error": {"message": "slow down"}},
            {"x-ratelimit-reset-tokens": "2s"},
        ),
    )

    with pytest.raises(RateLimitError) as excinfo:
        groq.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.retry_after == 2.0


def test_groq_429_without_headers_still_raises_cleanly(groq, monkeypatch):
    monkeypatch.setattr(
        "requests.post", lambda *a, **k: FakeResponse(429, {}, {})
    )
    with pytest.raises(RateLimitError) as excinfo:
        groq.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.retry_after is None


def test_groq_400_is_still_not_treated_as_a_rate_limit(groq, monkeypatch):
    """The native-tool-call recovery path must be unaffected by this change."""
    rejection = {
        "error": {
            "code": "tool_use_failed",
            "failed_generation": json.dumps(
                {"name": "get_quote", "arguments": {"ticker": "NVDA"}}
            ),
        }
    }
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(400, rejection))

    text = groq.complete([{"role": "user", "content": "hi"}])
    assert "Action: get_quote" in text


# --------------------------------------------------------------------------- #
# Duration parsing (Groq's header format)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("3", 3.0),
        ("1.5", 1.5),
        ("2s", 2.0),
        ("172ms", 0.172),      # must not be read as 172 seconds
        ("7m12s", 432.0),
        ("1h", 3600.0),
        ("", None),
        (None, None),
        ("later", None),
    ],
)
def test_parse_duration(raw, expected):
    actual = _parse_duration(raw)
    if expected is None:
        assert actual is None
    else:
        # Approximate: 172ms is 0.172 only up to binary floating-point.
        assert actual == pytest.approx(expected)


# --------------------------------------------------------------------------- #
# The other backends signal rate limits too
# --------------------------------------------------------------------------- #
def test_ollama_raises_rate_limit_error_on_429(monkeypatch):
    """A busy local server is a rate limit, not an unexplained failure."""
    from sage.agent import OllamaEngine

    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: FakeResponse(429, {}, {"retry-after": "5"}),
    )
    engine = OllamaEngine(model="m", url="http://127.0.0.1:11434")

    with pytest.raises(RateLimitError) as excinfo:
        engine.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.retry_after == 5.0


def test_ollama_non_429_still_raises_normally(monkeypatch):
    from sage.agent import OllamaEngine

    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(500, {}))
    engine = OllamaEngine(model="m", url="http://127.0.0.1:11434")

    with pytest.raises(RuntimeError):
        engine.complete([{"role": "user", "content": "hi"}])


def test_claude_translates_the_sdk_rate_limit_error(monkeypatch):
    """The Anthropic SDK's own RateLimitError becomes Sage's, so the loop retries.

    Built without importing `anthropic`, which is an optional dependency.
    """
    from sage.agent import ClaudeEngine

    # A stand-in exception whose class name matches what the SDK raises.
    RateLimitFromSDK = type("RateLimitError", (Exception,), {})

    class FakeMessages:
        def create(self, **kwargs):
            raise RateLimitFromSDK("rate_limit_error: too many tokens")

    class FakeClient:
        messages = FakeMessages()

    engine = ClaudeEngine.__new__(ClaudeEngine)  # bypass __init__ (needs a key)
    LLMEngine.__init__(engine)
    engine.model = "test-model"
    engine._client = FakeClient()

    with pytest.raises(RateLimitError):
        engine.complete([{"role": "user", "content": "hi"}])


def test_claude_other_errors_are_not_swallowed(monkeypatch):
    from sage.agent import ClaudeEngine

    class FakeMessages:
        def create(self, **kwargs):
            raise ValueError("model_not_found")

    class FakeClient:
        messages = FakeMessages()

    engine = ClaudeEngine.__new__(ClaudeEngine)
    LLMEngine.__init__(engine)
    engine.model = "test-model"
    engine._client = FakeClient()

    with pytest.raises(ValueError):
        engine.complete([{"role": "user", "content": "hi"}])


def test_backoff_has_a_floor():
    """A near-zero reset window must not cause an instant retry storm.

    A live Groq 429 reported a token-window reset of 0.001s. Honouring that
    literally would fire a retry immediately into a window that is still closed.
    """
    engine = FlakyEngine(fail_times=1, retry_after=0.001)
    engine.complete_with_retry([{"role": "user", "content": "hi"}])
    assert engine.slept == [engine.backoff_floor]
    assert engine.backoff_floor >= 0.25


# --------------------------------------------------------------------------- #
# Aggregators that answer 200 with an error body
# --------------------------------------------------------------------------- #
def test_error_body_on_a_200_is_treated_as_a_rate_limit(groq, monkeypatch):
    """OpenRouter returns HTTP 200 carrying an upstream refusal.

    A shared free model being briefly unavailable is a throughput problem, so
    the loop should back off and retry rather than lose the run.
    """
    body = {"id": "gen-1", "error": {"code": 429,
                                     "message": "model is temporarily rate-limited upstream"}}
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, body))

    with pytest.raises(RateLimitError):
        groq.complete([{"role": "user", "content": "hi"}])


def test_non_rate_limit_error_body_raises_a_clear_error(groq, monkeypatch):
    """A genuine provider fault is reported, not disguised as a rate limit."""
    body = {"id": "gen-2", "error": {"code": 400, "message": "no endpoints found"}}
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, body))

    with pytest.raises(RuntimeError) as excinfo:
        groq.complete([{"role": "user", "content": "hi"}])
    assert "no endpoints found" in str(excinfo.value)
    assert not isinstance(excinfo.value, RateLimitError)


def test_a_normal_200_still_returns_content(groq, monkeypatch):
    """The error check must not disturb a healthy response."""
    body = {"choices": [{"message": {"content": "Thought: fine"}}]}
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(200, body))
    assert groq.complete([{"role": "user", "content": "hi"}]) == "Thought: fine"
