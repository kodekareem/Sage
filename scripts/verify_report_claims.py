"""Verify the report's claims about the codebase match the codebase.

A report is written once and the code keeps moving. Any figure stated in prose
(the test count, the number of tools, which engines exist) can quietly become
false. These are exactly the claims a marker can check in the repository, so a
mismatch is worse than saying nothing.

Every figure here is measured from the live code, not copied from the report.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "report" / "final-report.md"
sys.path.insert(0, str(REPO))


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not REPORT.exists():
        fail(f"{REPORT.relative_to(REPO)} does not exist")
    text = REPORT.read_text(encoding="utf-8")

    # --- test count, measured by running them --------------------------
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(REPO), capture_output=True, encoding="utf-8", errors="replace", timeout=600,
    )
    match = re.search(r"(\d+) passed", proc.stdout or "")
    if not match:
        fail(f"could not measure the test count:\n{(proc.stdout or '')[-400:]}")
    tests = int(match.group(1))
    if proc.returncode != 0:
        fail(f"the test suite does not pass ({tests} passed, exit {proc.returncode})")
    # Look at the sentences that actually make the claim, not the whole
    # document. A bare substring search passes on any incidental occurrence of
    # the number elsewhere (a word count, a line count), so a stale "85 tests"
    # survived it. Every phrase pairing a number with "test" must use the
    # measured figure.
    stated = re.findall(r"(\d[\d,]*)\s+tests?\b", text)
    if not stated:
        fail(f"the report never states a test count; it should state {tests}")
    wrong = sorted({s for s in stated if int(s.replace(",", "")) != tests})
    if wrong:
        fail(
            f"the report states {', '.join(wrong)} tests in "
            f"{len([s for s in stated if s in wrong])} place(s); the suite has {tests}"
        )
    print(f"test count {tests}: stated correctly in {len(stated)} place(s)")

    # --- tool library ---------------------------------------------------
    from sage.tools import TOOL_REGISTRY
    tools = sorted(TOOL_REGISTRY)
    number_words = {5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}
    spelled = number_words.get(len(tools), str(len(tools)))
    # Match the phrase that makes the claim, so an unrelated "6" elsewhere in
    # the document cannot stand in for a correct tool count.
    stated_tools = re.findall(
        r"\b(\d+|five|six|seven|eight|nine)\s+(?:financial\s+)?(?:analysis\s+)?tools\b",
        text, re.IGNORECASE,
    )
    if not stated_tools:
        fail(f"the report never states a tool count; it should state {len(tools)}")
    for claim in {s.lower() for s in stated_tools}:
        value = number_words.get(len(tools)) if not claim.isdigit() else str(len(tools))
        if claim != (spelled if not claim.isdigit() else str(len(tools))):
            fail(f"the report says '{claim} tools'; the registry holds {len(tools)}")
    missing = [t for t in tools if t not in text]
    if missing:
        fail(f"tools that exist but are never named in the report: {missing}")
    print(f"{len(tools)} tools: count and names both correct")

    # --- engines --------------------------------------------------------
    from sage import config
    for engine in config.ENGINES:
        if engine not in text:
            fail(f"engine '{engine}' exists in the code but is not in the report")
    print(f"{len(config.ENGINES)} engines: all named ({', '.join(config.ENGINES)})")

    # --- the step cap ---------------------------------------------------
    # Again matched in context: the report says the loop is "capped at eight
    # steps", and a bare "8" appearing anywhere would otherwise satisfy this.
    cap_words = {8: "eight", 10: "ten", 12: "twelve", 6: "six"}
    cap_spelled = cap_words.get(config.MAX_STEPS, str(config.MAX_STEPS))
    stated_caps = re.findall(
        r"capped at (?:a maximum of )?(\d+|six|eight|ten|twelve)\s+(?:reasoning )?steps",
        text, re.IGNORECASE,
    )
    if not stated_caps:
        fail(f"the report never states the step cap; it should state {config.MAX_STEPS}")
    for claim in {c.lower() for c in stated_caps}:
        ok = claim == str(config.MAX_STEPS) or claim == cap_spelled
        if not ok:
            fail(f"the report says the loop is capped at '{claim}' steps; "
                 f"MAX_STEPS is {config.MAX_STEPS}")
    print(f"step cap {config.MAX_STEPS}: stated correctly")

    print("REPORT CLAIMS VERIFICATION PASSED")


if __name__ == "__main__":
    main()
