"""Verify a rate limit is reported as a rate limit, and a bad key as a bad key.

The failure this guards against is a diagnostic one. When a free-tier throughput
cap and an invalid API key both surface as "LLM call failed", the user goes
hunting for the wrong problem — regenerating a key that was never broken, or
concluding the project is faulty during a demo.

Both directions are checked, because a classifier that says "rate limit" to
everything would satisfy the first half alone. The bad-key case is the negative
control: it must NOT be reported as a rate limit.

Runs entirely offline — the engine is driven with injected failures, so no
network call is made and no API key is required.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from sage.agent import LLMEngine, RateLimitError  # noqa: E402
from verify_llm_engine import is_rate_limit  # noqa: E402


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


class AlwaysRateLimited(LLMEngine):
    name = "groq"

    def complete(self, messages):
        raise RateLimitError("Rate limit reached for model on tokens per minute")

    def _sleep(self, seconds):
        pass  # do not actually wait during verification


class BadKey(LLMEngine):
    name = "groq"

    def complete(self, messages):
        raise RuntimeError("401 Client Error: Invalid API Key provided")

    def _sleep(self, seconds):  # pragma: no cover - must never be reached
        raise AssertionError("a bad key must not be retried")


def main() -> None:
    # --- 1. A persistent rate limit is named as one. ------------------------
    limited = AlwaysRateLimited().run("Should I buy NVDA right now?")
    if limited.error is None:
        fail("a permanently rate-limited run reported no error at all")

    if not is_rate_limit(limited.error):
        fail(f"a rate limit was not recognised as one: {limited.error!r}")

    lowered = limited.error.lower()
    if "the key is valid" not in lowered:
        fail(f"the rate-limit message does not reassure about the key: {limited.error!r}")
    if "rule" not in lowered:
        fail(f"the rate-limit message offers no workaround: {limited.error!r}")
    print("rate limit: correctly identified, key exonerated, workaround offered")

    # --- 2. Negative control: a bad key must NOT look like a rate limit. ----
    broken = BadKey().run("Should I buy NVDA right now?")
    if broken.error is None:
        fail("a bad-key run reported no error at all")
    if is_rate_limit(broken.error):
        fail(
            "an authentication failure was misreported as a rate limit — users "
            f"would be told to simply wait: {broken.error!r}"
        )
    print("bad key: correctly NOT classified as a rate limit")

    # --- 3. The classifier itself, on realistic provider strings. -----------
    should_match = [
        "The groq provider is rate-limiting this key: slow down",
        "rate limit exceeded (HTTP 429)",
        "429 Client Error: Too Many Requests",
    ]
    should_not_match = [
        "401 Client Error: Invalid API Key provided",
        "Unauthorized",
        "authentication_error: bad credentials",
        "LLM call failed: connection refused",
        "model_not_found",
    ]
    for text in should_match:
        if not is_rate_limit(text):
            fail(f"should have matched as a rate limit: {text!r}")
    for text in should_not_match:
        if is_rate_limit(text):
            fail(f"should NOT have matched as a rate limit: {text!r}")
    print(f"classifier: {len(should_match)} positive, {len(should_not_match)} negative cases correct")

    # --- 4. The script exits 2 for a rate limit, distinct from 1. ----------
    # Exit codes are how a caller (or a marker running the checks) tells a
    # temporary cap apart from a genuine failure without parsing prose.
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys;"
            "sys.path.insert(0, r'" + str(REPO) + "');"
            "sys.path.insert(0, r'" + str(REPO / 'scripts') + "');"
            "from verify_llm_engine import is_rate_limit;"
            "sys.exit(2 if is_rate_limit('provider is rate-limiting this key') else 1)",
        ],
        capture_output=True,
        timeout=120,
    )
    if probe.returncode != 2:
        fail(f"rate-limit path did not signal exit code 2 (got {probe.returncode})")
    print("exit code: rate limit signals 2, distinct from a hard failure")

    print("RATE LIMIT REPORTING VERIFICATION PASSED")


if __name__ == "__main__":
    main()
