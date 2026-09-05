"""Verify that tied comparisons are reported honestly and order-independently.

The audit found that ``_comparison_verdict`` picked a winner with ``max()``,
which returns the first key encountered. Two equally-scored tickers therefore
produced a confident-looking "PREFER X" whose choice flipped when the question
named them in the other order — a verdict the visible trace could not justify,
in a project whose whole claim is that the trace justifies the verdict.

This script fails if that behaviour returns. It asserts three things:

1. A tie is *declared* as a tie, not silently resolved to one ticker.
2. The verdict is invariant under input order (the original defect).
3. A genuine winner is still chosen when the scores actually differ, so the
   fix does not simply refuse to ever pick — a negative control against a
   check that would pass by making every verdict a tie.

Exits non-zero on any failure and prints the success marker only at the end.
"""

from __future__ import annotations

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sage.agent import RuleEngine

_verdict = RuleEngine._comparison_verdict

GOLDEN = "golden_cross"
DEATH = "death_cross"


def row(ticker: str, crossover: str = GOLDEN, rsi: float = 50.0, pe: float = 30.0) -> dict:
    """Build one comparison row of the shape ``compare_tickers`` returns."""
    return {"ticker": ticker, "crossover_signal": crossover, "rsi": rsi, "trailing_pe": pe}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    # --- 1. A tie must be declared, not silently broken. --------------------
    # Both rows are deliberately identical apart from the ticker symbol.
    tied_ab = [row("AAPL"), row("MSFT")]
    tied_ba = [row("MSFT"), row("AAPL")]

    verdict_ab, scores_ab = _verdict(tied_ab)
    verdict_ba, scores_ba = _verdict(tied_ba)

    if scores_ab["AAPL"] != scores_ba["AAPL"] or scores_ab["MSFT"] != scores_ba["MSFT"]:
        fail(f"scoring is order-dependent: {scores_ab} vs {scores_ba}")

    if scores_ab["AAPL"] != scores_ab["MSFT"]:
        fail(f"fixture is not actually tied, so this check proves nothing: {scores_ab}")

    # The recommendation must not name a single winner out of a dead heat.
    rec_ab = verdict_ab.recommendation
    if rec_ab.strip().upper().startswith("PREFER "):
        fail(f"a tie was silently resolved to a single winner: {rec_ab!r}")

    # It must positively say the candidates are level.
    if "TOO CLOSE" not in rec_ab.upper():
        fail(f"a tie is not declared as a tie: {rec_ab!r}")

    # --- 2. The tie verdict must be invariant under input order. ------------
    if verdict_ab.recommendation != verdict_ba.recommendation:
        fail(
            "tied verdict flips with input order: "
            f"{verdict_ab.recommendation!r} vs {verdict_ba.recommendation!r}"
        )

    if verdict_ab.confidence != verdict_ba.confidence:
        fail(
            "tied confidence flips with input order: "
            f"{verdict_ab.confidence!r} vs {verdict_ba.confidence!r}"
        )

    # Both tickers must be named, so the user can see what was level.
    for ticker in ("AAPL", "MSFT"):
        if ticker not in verdict_ab.rationale:
            fail(f"tied rationale omits {ticker}: {verdict_ab.rationale!r}")

    # A dead heat cannot be high confidence.
    if verdict_ab.confidence != "low":
        fail(f"a tie should not be confident, got {verdict_ab.confidence!r}")

    # --- 3. Negative control: a real winner is still chosen. ----------------
    # Without this, a "fix" that declared *everything* a tie would pass above.
    decided = [
        row("TSLA", crossover=DEATH, rsi=75.0, pe=60.0),   # bad on all three
        row("NVDA", crossover=GOLDEN, rsi=25.0, pe=20.0),  # good on all three
    ]
    verdict_win, scores_win = _verdict(decided)

    if scores_win["NVDA"] <= scores_win["TSLA"]:
        fail(f"control fixture did not produce a clear winner: {scores_win}")

    if not verdict_win.recommendation.strip().upper().startswith("PREFER NVDA"):
        fail(
            "a decisive comparison no longer names its winner: "
            f"{verdict_win.recommendation!r}"
        )

    # And that decisive verdict must also be order-independent.
    verdict_win_rev, _ = _verdict(list(reversed(decided)))
    if verdict_win_rev.recommendation != verdict_win.recommendation:
        fail(
            "decisive verdict flips with input order: "
            f"{verdict_win.recommendation!r} vs {verdict_win_rev.recommendation!r}"
        )

    # A clear 3-point sweep should not be reported as low confidence.
    if verdict_win.confidence == "low":
        fail("a decisive sweep was reported as low confidence")

    print(f"tie verdict (both orders): {verdict_ab.recommendation}")
    print(f"decisive verdict (both orders): {verdict_win.recommendation}")
    print("TIE VERIFICATION PASSED")


if __name__ == "__main__":
    main()
