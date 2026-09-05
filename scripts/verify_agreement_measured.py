"""Verify the comparative study was measured with the corrected scorer.

An early version of the study ran under a scorer that counted indicator names
and rounded figures as fabrications, and its numbers were quarantined rather
than quoted. This confirms the results file holds a real comparison, that the
discredited figures are not present as live results, and that the model which
produced it is recorded so the report can name it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "report" / "data" / "evaluation-offline.json"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not DATA.exists():
        fail(f"{DATA.name} does not exist")
    d = json.loads(DATA.read_text(encoding="utf-8"))

    for key in ("llm", "llm_rows", "agreement"):
        if key not in d:
            fail(f"the results file has no '{key}' - the study has not been run")

    quarantined = [k for k in d if "INVALID" in k]
    if quarantined:
        fail(f"discredited results are still present: {quarantined}")

    if not d.get("llm_model"):
        fail("the model used for the comparison is not recorded")

    rows = d["llm_rows"]
    if len(rows) != d["question_count"]:
        fail(f"{len(rows)} LLM rows for {d['question_count']} questions")

    if not any(r.get("observations") for r in rows):
        fail("runs did not store observations, so results cannot be re-scored locally")

    agreement = d["agreement"]
    if agreement["compared"] < 10:
        fail(f"only {agreement['compared']} verdicts compared; too few to report")

    print(f"model: {d['llm_model']} via {d.get('llm_provider', 'unknown')}")
    print(f"questions: {len(rows)} | verdicts compared: {agreement['compared']}")
    print(f"groundedness: rule {d['rule']['grounded_pct']}%, llm {d['llm']['grounded_pct']}%")
    print("AGREEMENT STUDY VERIFICATION PASSED")


if __name__ == "__main__":
    main()
