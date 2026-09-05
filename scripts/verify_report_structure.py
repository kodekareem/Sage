"""Verify the report has the structure the brief requires.

Checks the six chapters are present and in order, that the project template
number is stated (the brief asks for it explicitly), that the public repository
link is included, and that every reference in the list is actually cited in the
body. An uncited reference is padding; a citation with no reference is a
dangling claim. Both cost marks under "proper citation and referencing".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "report" / "final-report.md"

REQUIRED_ORDER = [
    "Introduction", "Literature Review", "Design",
    "Implementation", "Evaluation", "Conclusion",
]
REPO_URL = "github.com/kodekareem/Sage"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not REPORT.exists():
        fail(f"{REPORT.relative_to(REPO)} does not exist")
    text = REPORT.read_text(encoding="utf-8")

    # --- chapters present and in order ---------------------------------
    headings = re.findall(r"^##\s+(?:\d+\.?\s*)?(.+?)\s*$", text, re.MULTILINE)
    found = [h for h in headings if any(r.lower() in h.lower() for r in REQUIRED_ORDER)]
    seen = []
    for h in found:
        for r in REQUIRED_ORDER:
            if r.lower() in h.lower() and r not in seen:
                seen.append(r)
    if seen != REQUIRED_ORDER:
        fail(f"chapters wrong or out of order.\n  expected {REQUIRED_ORDER}\n  found    {seen}")
    print(f"all {len(REQUIRED_ORDER)} chapters present, in order")

    # --- the brief asks for the template number explicitly --------------
    if not re.search(r"project\s+(?:idea|number|template)\s*:?\s*2\b", text, re.IGNORECASE):
        fail("the project template number (Project Idea 2) is not stated")
    print("project template number stated")

    # --- public repository link ----------------------------------------
    if REPO_URL not in text:
        fail(f"the public repository link ({REPO_URL}) is missing")
    print("repository link present")

    # --- references ------------------------------------------------------
    ref_match = re.search(r"^##\s+References\s*$(.+)", text, re.MULTILINE | re.DOTALL)
    if not ref_match:
        fail("no References section")
    body = text[: ref_match.start()]
    refs = re.findall(r"^-\s*([A-Z][A-Za-z\-']+)", ref_match.group(1), re.MULTILINE)
    if len(refs) < 6:
        fail(f"only {len(refs)} references; a literature review needs more")

    uncited = [r for r in refs if r not in body]
    if uncited:
        fail(f"references never cited in the body: {sorted(set(uncited))}")
    print(f"{len(refs)} references, all cited in the body")

    # --- citations must resolve to a reference --------------------------
    cited = set(re.findall(r"\(([A-Z][A-Za-z\-']+)(?:\s+et\s+al\.)?,\s*\d{4}", body))
    dangling = sorted(c for c in cited if c not in refs)
    if dangling:
        fail(f"citations with no matching reference: {dangling}")
    print(f"{len(cited)} distinct citations, all resolve to a reference")

    print("REPORT STRUCTURE VERIFICATION PASSED")


if __name__ == "__main__":
    main()
