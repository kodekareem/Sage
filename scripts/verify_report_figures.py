"""Verify every evaluation figure quoted in the report matches the measured data.

A report can drift from its evidence in two ways: a number gets typed by hand
and is wrong, or the data is re-measured and the prose is not updated. Both
produce a document that looks fine and is false. This checks the report's
numbers against report/data/evaluation-offline.json, which the harness writes.

It works on claims declared in REPORT_CLAIMS below: each names the value it
asserts and where that value lives in the results file. The check fails if the
report omits a declared claim, or states it with a different number.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "report" / "final-report.md"
DATA = REPO / "report" / "data" / "evaluation-offline.json"

# Each entry: a label, the path into the results file, and how the report writes
# it. The check confirms the report contains the measured value, so an edit to
# either side that breaks the match is caught.
REPORT_CLAIMS: list[tuple[str, list, str]] = [
    ("rule trace validity",      ["rule", "trace_valid_pct"], "percent"),
    ("rule groundedness",        ["rule", "grounded_pct"], "percent"),
    ("rule tool appropriateness", ["rule", "tools_appropriate_pct"], "percent"),
    ("rule behaviour",           ["rule", "answered_correctly_pct"], "percent"),
    ("rule mean steps",          ["rule", "mean_steps"], "number"),
    ("llm groundedness",         ["llm", "grounded_pct"], "percent"),
    ("llm tool appropriateness", ["llm", "tools_appropriate_pct"], "percent"),
    ("llm behaviour",            ["llm", "answered_correctly_pct"], "percent"),
    ("llm mean steps",           ["llm", "mean_steps"], "number"),
    ("agreement",                ["agreement", "agreement_pct"], "percent"),
    ("question count",           ["question_count"], "number"),
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def dig(data: dict, path: list):
    node = data
    for key in path:
        node = node[key]
    return node


def variants(value) -> list[str]:
    """The spellings a report might reasonably use for one measured value."""
    out = {str(value)}
    number = float(value)
    if number.is_integer():
        out.add(str(int(number)))
        out.add(f"{int(number)}.0")
    else:
        out.add(f"{number:g}")
        out.add(f"{number:.1f}")
        out.add(f"{number:.2f}")
    return sorted(out)


def main() -> None:
    if not REPORT.exists():
        fail(f"{REPORT.relative_to(REPO)} does not exist")
    if not DATA.exists():
        fail(f"{DATA.relative_to(REPO)} does not exist — run the evaluation first")

    data = json.loads(DATA.read_text(encoding="utf-8"))
    text = REPORT.read_text(encoding="utf-8")

    missing: list[str] = []
    for label, path, _kind in REPORT_CLAIMS:
        try:
            value = dig(data, path)
        except (KeyError, TypeError):
            fail(f"the results file has no value at {'.'.join(map(str, path))}")

        if not any(v in text for v in variants(value)):
            missing.append(f"{label}: measured {value}, not found in the report")

    if missing:
        fail(
            "the report does not state these measured figures (or states them "
            "with different numbers):\n  " + "\n  ".join(missing)
        )

    # The model that produced the comparison must be named, not left as "an LLM".
    model = data.get("llm_model")
    if model and model.split("/")[-1].split(":")[0] not in text:
        fail(f"the report does not name the model used for the comparison ({model})")

    # Guard against a stale figure surviving a re-measurement: the discredited
    # early readings must not appear as if they were results.
    for discredited in ("16.7", "41.7", "66.7", "33.3%"):
        if re.search(rf"\b{re.escape(discredited)}\s*%?\s*(?:groundedness|agreement)", text):
            fail(f"the report quotes a discredited early figure: {discredited}")

    print(f"checked {len(REPORT_CLAIMS)} measured figures against {DATA.name}")
    print("REPORT FIGURES VERIFICATION PASSED")


if __name__ == "__main__":
    main()
