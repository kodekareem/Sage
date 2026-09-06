"""Verify the report's quoted evidence appears verbatim in the stored results.

The report quotes phrases from engine rationales to support specific claims:
that the model computed a drawdown rather than reading one, and that a sign
carried by a word tripped the early scorer. Those quotes are the evidence for
the argument around them. If a re-run changes what an engine said, the quote
becomes something the report attributes to a system that never produced it.

verify_report_figures.py covers the declared summary statistics. This covers the
quoted text and the specific figures embedded in the narrative, which nothing
else checks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "report" / "final-report.md"
DATA = REPO / "report" / "data" / "evaluation-offline.json"

# Each entry: the phrase the report quotes, which engine's rows it must appear
# in, and a short label for the failure message.
QUOTED_EVIDENCE = [
    ("51% off the 52-week high", "llm_rows",
     "the model's computed drawdown, cited as a derived figure"),
    ("50-60", "llm_rows",
     "the model's invented advisory range"),
    ("48.59", "rule_rows",
     "the observation whose sign was carried by a word"),
]


def norm_text(s: str) -> str:
    """Letters and digits only, so a line break inside a quote does not matter."""
    return "".join(c for c in s.lower() if c.isalnum())


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not REPORT.exists():
        fail(f"{REPORT.name} does not exist")
    if not DATA.exists():
        fail(f"{DATA.name} does not exist")

    report = REPORT.read_text(encoding="utf-8")
    data = json.loads(DATA.read_text(encoding="utf-8"))

    problems: list[str] = []
    for phrase, rows_key, label in QUOTED_EVIDENCE:
        if norm_text(phrase) not in norm_text(report):
            # Skipping here would make the check toothless: altering a quoted
            # figure removes the phrase, and "absent" would then read as "fine".
            # A quote the report is expected to carry must actually be there.
            problems.append(
                f"the report no longer quotes {phrase!r} ({label}). Either the "
                "quote was altered, in which case it no longer matches the "
                "evidence, or the claim was dropped and this expectation is "
                "stale and should be removed deliberately."
            )
            continue

        rows = data.get(rows_key) or []
        blob = " ".join(
            (r.get("rationale") or "") + " " + json.dumps(r.get("observations", []), default=str)
            for r in rows
        )
        # Compare on digits and letters only, so quoting across a line break or
        # with different spacing does not read as a mismatch.
        if norm_text(phrase) not in norm_text(blob):
            problems.append(
                f"the report quotes {phrase!r} as {label}, but no {rows_key} entry "
                "contains it - the quote no longer matches what the system produced"
            )
        else:
            print(f"  verified in {rows_key}: {phrase!r}")

    # The narrative in 5.5 recounts figures an earlier scorer produced. Those are
    # deliberately historical, so they must be presented as superseded rather
    # than as findings. Guard against them being read as current results.
    # 75.0 is deliberately excluded: it is the measured disagreement share in
    # Table 2, not a discredited reading, and flagging it was a false positive.
    for old in ("16.7", "66.7"):
        if old in report:
            window_start = max(0, report.find(old) - 400)
            context = report[window_start:report.find(old) + 200].lower()
            if not any(w in context for w in
                       ("before it was correct", "early", "wrong", "corrected",
                        "first reported", "would have")):
                problems.append(
                    f"the discredited figure {old} appears without being marked "
                    "as a superseded reading"
                )

    if problems:
        fail("\n  ".join(problems))

    print("REPORT QUOTES VERIFICATION PASSED")


if __name__ == "__main__":
    main()
