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
    if str(tests) not in text:
        fail(f"the report does not state the measured test count ({tests})")
    print(f"test count {tests}: stated correctly")

    # --- tool library ---------------------------------------------------
    from sage.tools import TOOL_REGISTRY
    tools = sorted(TOOL_REGISTRY)
    number_words = {6: "six", 7: "seven", 8: "eight"}
    spelled = number_words.get(len(tools), str(len(tools)))
    if str(len(tools)) not in text and spelled not in text.lower():
        fail(f"the report does not state the tool count ({len(tools)})")
    missing = [t for t in tools if t not in text]
    if missing:
        fail(f"tools that exist but are never named in the report: {missing}")
    print(f"{len(tools)} tools: all named")

    # --- engines --------------------------------------------------------
    from sage import config
    for engine in config.ENGINES:
        if engine not in text:
            fail(f"engine '{engine}' exists in the code but is not in the report")
    print(f"{len(config.ENGINES)} engines: all named ({', '.join(config.ENGINES)})")

    # --- the step cap ---------------------------------------------------
    if str(config.MAX_STEPS) not in text:
        fail(f"the report does not state the step cap ({config.MAX_STEPS})")
    print(f"step cap {config.MAX_STEPS}: stated")

    print("REPORT CLAIMS VERIFICATION PASSED")


if __name__ == "__main__":
    main()
