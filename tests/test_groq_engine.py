"""Tests for the Groq engine's request shaping and error recovery.

These run offline: ``requests.post`` is replaced so no network call is made and
no API key is needed. They cover the two things unique to this engine — the
OpenAI-compatible payload it sends, and its recovery from a model that reaches
for native function calling when Sage expects plain-text ReAct.

The behaviour under test came from a real failure: ``openai/gpt-oss-20b`` on
Groq answered the ReAct prompt with a native tool call, which the API rejects
with HTTP 400 ``tool_use_failed`` because Sage declares no ``tools`` array.
Rather than lose the turn, the engine translates the attempted call back into
the text format the loop parses.
"""

from __future__ import annotations

import json

import pytest

from sage import config
from sage.agent import GroqEngine


class FakeResponse:
    """Minimal stand-in for a ``requests`` response."""

    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code} Client Error")


@pytest.fixture
def engine(monkeypatch):
    """A GroqEngine with a key present but no network."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    return GroqEngine(model="test-model", url="https://example.invalid/v1")


def test_groq_sends_an_openai_compatible_payload(engine, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse(200, {"choices": [{"message": {"content": "Thought: hi"}}]})

    monkeypatch.setattr("requests.post", fake_post)

    text = engine.complete([{"role": "user", "content": "hello"}])

    assert text == "Thought: hi"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert captured["json"]["model"] == "test-model"
    # The system role is posted inline, unlike the Anthropic API.
    assert captured["json"]["messages"] == [{"role": "user", "content": "hello"}]
    # No `tools` array: Sage parses tool calls out of the text itself.
    assert "tools" not in captured["json"]


def test_groq_recovers_a_rejected_native_tool_call(engine, monkeypatch):
    """A 400 tool_use_failed becomes a parseable plain-text action."""
    rejection = {
        "error": {
            "message": "Tool choice is none, but model called a tool",
            "type": "invalid_request_error",
            "code": "tool_use_failed",
            "failed_generation": json.dumps(
                {"name": "get_quote", "arguments": {"ticker": "NVDA"}}
            ),
        }
    }
    monkeypatch.setattr(
        "requests.post", lambda *a, **k: FakeResponse(400, rejection)
    )

    text = engine.complete([{"role": "user", "content": "Should I buy NVDA?"}])

    assert "Action: get_quote" in text
    assert '"ticker": "NVDA"' in text

    # And the loop's own parser must accept what we produced.
    from sage.agent import parse_react_output

    parsed = parse_react_output(text)
    assert parsed["kind"] == "action"
    assert parsed["action"] == "get_quote"
    assert parsed["action_input"] == {"ticker": "NVDA"}


def test_groq_recovers_stringified_arguments(engine, monkeypatch):
    """Some models stringify the arguments object; that is handled too."""
    rejection = {
        "error": {
            "code": "tool_use_failed",
            "failed_generation": json.dumps(
                {"name": "get_fundamentals", "arguments": '{"ticker": "AAPL"}'}
            ),
        }
    }
    monkeypatch.setattr(
        "requests.post", lambda *a, **k: FakeResponse(400, rejection)
    )

    from sage.agent import parse_react_output

    parsed = parse_react_output(engine.complete([{"role": "user", "content": "x"}]))
    assert parsed["action"] == "get_fundamentals"
    assert parsed["action_input"] == {"ticker": "AAPL"}


def test_groq_does_not_swallow_other_400s(engine, monkeypatch):
    """A genuine bad request must still surface as an error."""
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: FakeResponse(
            400, {"error": {"code": "model_not_found", "message": "no such model"}}
        ),
    )

    with pytest.raises(RuntimeError):
        engine.complete([{"role": "user", "content": "x"}])


def test_groq_engine_is_registered_and_falls_back_without_a_key(monkeypatch):
    """The engine is selectable, but never claims availability without a key."""
    assert "groq" in config.ENGINES

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    # Streamlit secrets must not be consulted in a way that fakes availability.
    monkeypatch.setattr(config, "get_groq_key", lambda: None)
    assert config.groq_available() is False
    assert config.resolve_engine("groq") == "rule"


def test_recovery_strips_a_namespaced_tool_name(engine, monkeypatch):
    """`tool.get_quote` maps to the registered `get_quote`.

    GPT-OSS models namespace their native calls. Left as-is, every recovered
    call named a tool the registry does not hold, so each step failed and the
    run spun to its step cap without answering.
    """
    rejection = {
        "error": {
            "code": "tool_use_failed",
            "failed_generation": json.dumps(
                {"name": "tool.get_quote", "arguments": {"ticker": "NVDA"}}
            ),
        }
    }
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(400, rejection))

    from sage.agent import parse_react_output

    parsed = parse_react_output(engine.complete([{"role": "user", "content": "x"}]))
    assert parsed["action"] == "get_quote"
    assert parsed["action_input"] == {"ticker": "NVDA"}


def test_recovery_keeps_an_unknown_tool_name_intact(engine, monkeypatch):
    """An unrecognised call is passed through, not rewritten into a real tool.

    Stripping blindly would turn `assistant` or `foo.bar` into whatever came
    last, hiding a genuine failure. The loop should see the unknown name and
    report it.
    """
    rejection = {
        "error": {
            "code": "tool_use_failed",
            "failed_generation": json.dumps(
                {"name": "namespace.not_a_real_tool", "arguments": {}}
            ),
        }
    }
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse(400, rejection))

    from sage.agent import parse_react_output

    parsed = parse_react_output(engine.complete([{"role": "user", "content": "x"}]))
    assert parsed["action"] == "namespace.not_a_real_tool"
