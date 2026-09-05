"""Verify the groundedness scorer measures what the report says it measures.

Chapter 5 quotes a groundedness percentage. That figure is only worth printing
if the scorer behind it can both catch a fabricated number and leave correct
financial writing alone. This project found the hard way that a scorer can fail
in either direction: an early version reported 41.7% groundedness for the LLM
engine purely because it counted "the 200-day SMA" and "RSI below 70" as data
readings that needed grounding.

So this checks both directions:

  * a figure that appears in no observation must be caught (no false negatives)
  * indicator names and textbook thresholds must not be treated as readings
    (no false positives)
  * differences of formatting and sign must not count as fabrication, because
    "down 48.59%" and an observed -48.59 are the same reading

Runs offline. Exits non-zero on any failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from run_evaluation import numbers_in, score_run, strip_domain_vocabulary  # noqa: E402

from sage.react import Action, FinalAnswer, ReActResult, ReActStep  # noqa: E402


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def build(rationale: str, observation: dict) -> ReActResult:
    """A one-step result whose rationale is scored against one observation."""
    result = ReActResult(question="q", engine="test")
    result.steps.append(
        ReActStep(
            index=1,
            thought="checking",
            action=Action(tool="calculate_technical_indicators", tool_input={"ticker": "X"}),
            observation=observation,
        )
    )
    result.final = FinalAnswer("HOLD", "low", rationale)
    return result


ITEM = {"id": "T", "q": "q", "kind": "single", "needs": set()}

OBSERVATION = {
    "ok": True, "ticker": "NVDA", "price": 222.82, "rsi": 97.78,
    "sma50": 206.74, "sma200": 166.2, "period_return_pct": -48.59,
    "trailing_pe": 45.0,
}


def grounded(rationale: str) -> bool:
    return score_run(ITEM, build(rationale, OBSERVATION))["grounded"]


def main() -> None:
    # --- 1. Fabrication must be caught. -----------------------------------
    fabrications = [
        "The price is 999.99, which looks cheap.",
        "Its RSI of 12.34 suggests it is oversold.",
        "Revenue grew 87.65% last quarter.",
    ]
    for text in fabrications:
        if grounded(text):
            fail(f"a fabricated figure was scored as grounded: {text!r}")
    print(f"caught {len(fabrications)}/{len(fabrications)} fabricated figures")

    # --- 2. Real readings must pass. --------------------------------------
    faithful = [
        "The price is 222.82 and the RSI is 97.78.",
        "The 50-day average sits at 206.74, above the 200-day at 166.2.",
        "It trades on a P/E of 45.0.",
        "It is down 48.59% over the period.",       # sign carried by the word
        "The reading was 97.78 against a P/E of 45.",  # 45 vs 45.0
    ]
    for text in faithful:
        if not grounded(text):
            fail(f"a correctly grounded rationale was scored as fabricated: {text!r}")
    print(f"accepted {len(faithful)}/{len(faithful)} faithful rationales")

    # --- 3. Domain vocabulary is not a reading. ---------------------------
    # These name an indicator or a standard threshold. None is a fetched value,
    # so none can be ungrounded. This is the false positive that produced a
    # wrong figure before it was fixed.
    vocabulary = [
        "Price is above its 200-day average, a longer-term uptrend.",
        "The 50-day average crossed above the 200-day average.",
        "Wait for the RSI to normalise below 70 before buying.",
        "An RSI above 30 would end the oversold reading.",
    ]
    for text in vocabulary:
        if not grounded(text):
            fail(
                "indicator vocabulary was mistaken for a data reading, which "
                f"would understate groundedness: {text!r}"
            )
    print(f"treated {len(vocabulary)}/{len(vocabulary)} vocabulary phrases as vocabulary")

    # --- 4. The stripper must be narrow, not a blanket filter. ------------
    # If stripping removed real readings too, check 1 would still pass while the
    # measure quietly became meaningless. Prove the readings survive stripping.
    survives = {
        "the 50-day SMA is at 206.74": 206.74,
        "RSI(14) is 97.78": 97.78,
        "it fell 48.59% over 6mo": 48.59,
    }
    for text, expected in survives.items():
        found = {v for v in numbers_in(strip_domain_vocabulary(text)) if abs(v) >= 10}
        if expected not in found:
            fail(f"stripping removed a real reading: {text!r} lost {expected}")
    print(f"preserved {len(survives)}/{len(survives)} readings through vocabulary stripping")

    # --- 4b. Stripping must never bite a number in half. ------------------
    # Regression control. An earlier pattern consumed the "93" from "RSI 93.93"
    # and left ".93" behind, which then matched nothing and scored a correct
    # rationale as fabricated. Any half-eaten decimal shows up as a value the
    # text never contained.
    partial_cases = {
        "overbought (RSI 93.93)": 93.93,
        "RSI 76.89 is high": 76.89,
        "oversold (RSI 23.83)": 23.83,
        "SMA50 sits at 206.74": 206.74,
    }
    for text, expected in partial_cases.items():
        stripped = strip_domain_vocabulary(text)
        found = {v for v in numbers_in(stripped) if abs(v) >= 10}
        if expected not in found:
            fail(
                "vocabulary stripping mangled a decimal reading: "
                f"{text!r} -> {stripped!r} gave {sorted(found)}, expected {expected}"
            )
        stray = found - {expected}
        if stray:
            fail(
                "vocabulary stripping invented a figure by splitting a decimal: "
                f"{text!r} -> {stripped!r} produced {sorted(stray)}"
            )
    print(f"kept {len(partial_cases)}/{len(partial_cases)} decimals intact through stripping")

    # --- 5. A rationale mixing vocabulary and a fabrication still fails. ---
    mixed = "Price is above its 200-day average and the RSI of 55.55 is neutral."
    if grounded(mixed):
        fail("a fabricated figure hid behind legitimate vocabulary")
    print("caught a fabrication mixed with legitimate vocabulary")

    print("SCORER VERIFICATION PASSED")


if __name__ == "__main__":
    main()
