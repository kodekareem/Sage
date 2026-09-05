"""Verify the rule engine still produces a grounded trace against live data.

This is the end-to-end check behind the project's central claim: that every
figure in the recommendation can be traced back to a tool observation the user
can see. It runs a real question against real yfinance data and asserts that the
numbers quoted in the final rationale actually appear in the recorded
observations — i.e. that the agent is reading its tools rather than asserting.

It requires network access. A network failure is reported as a failure rather
than skipped, because a green "verified" that silently skipped is exactly the
kind of false completion this project's ledger exists to prevent.
"""

from __future__ import annotations

import json
import re
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sage.agent import RuleEngine

TICKER = "NVDA"
QUESTION = f"Should I buy {TICKER} right now?"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def numbers_in(text: str) -> set[str]:
    """Extract numeric literals from text, normalised without trailing zeros."""
    found = set()
    for raw in re.findall(r"-?\d+(?:\.\d+)?", text):
        found.add(raw)
    return found


def main() -> None:
    result = RuleEngine().run(QUESTION)

    if result.error:
        fail(f"live run errored: {result.error}")
    if result.final is None:
        fail("live run produced no final recommendation")
    if not result.steps:
        fail("live run produced no reasoning steps")

    # Every step must be a complete Thought -> Action -> Observation record.
    for step in result.steps:
        if not step.thought or not step.thought.strip():
            fail(f"step {step.index} has no thought")
        if step.action is not None and step.observation is None:
            fail(f"step {step.index} took an action but recorded no observation")

    observed_blob = json.dumps([s.observation for s in result.steps], default=str)
    observed_numbers = numbers_in(observed_blob)

    rationale = result.final.rationale
    if not rationale.strip():
        fail("final answer has an empty rationale")

    # --- Groundedness: the figures cited must come from the observations. ---
    # Ignore the bull/bear tally counts, which are derived, single-digit values.
    cited = {n for n in numbers_in(rationale) if len(n.replace("-", "")) > 1 or "." in n}
    ungrounded = {n for n in cited if n not in observed_numbers}
    if ungrounded:
        fail(
            "the rationale cites figures that appear in no observation "
            f"(possible fabrication): {sorted(ungrounded)}\nrationale: {rationale}"
        )

    if result.final.recommendation not in {"BUY", "SELL", "HOLD"}:
        fail(f"unexpected recommendation: {result.final.recommendation!r}")
    if result.final.confidence not in {"low", "medium", "high"}:
        fail(f"unexpected confidence: {result.final.confidence!r}")

    print(f"question: {QUESTION}")
    print(f"steps: {len(result.steps)}")
    print(f"verdict: {result.final.recommendation} ({result.final.confidence})")
    print(f"cited figures all traceable to observations: {len(cited)} checked")
    print("LIVE VERIFICATION PASSED")


if __name__ == "__main__":
    main()
