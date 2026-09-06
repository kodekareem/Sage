"""Run every verification script and fail if any of them fails.

This exists because of a mistake made while building this project. A ledger
summary reported "ALL MET" three times while a check was already failing: adding
a gate invalidates stored approvals, and a re-verify in that state prints
"reverify not run" per gate while still printing a total. The summary line was
believed over the detail.

So this executes each script itself, in a fresh process, and reports each exit
code. It cannot report success while any check is failing, because success is
defined as every child exiting zero.

Scripts needing a credential or a network service are listed as conditional:
they are run, and a failure is reported as a skip only when the script says a
backend is unavailable rather than that a check failed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

SELF = Path(__file__).name

# These need a live backend. Missing credentials is a skip; anything else fails.
CONDITIONAL = {
    "verify_llm_engine.py": ("no LLM backend is reachable", "RATE LIMITED"),
    "check_quota.py": ("no API key", "WAITING"),
}

# Not verification checks: they produce artefacts rather than judging them.
NOT_CHECKS = {"run_evaluation.py", "build_report_pdf.py", "stamp_chapter_counts.py"}


def main() -> None:
    scripts = sorted(
        p for p in SCRIPTS.glob("*.py")
        if p.name != SELF and p.name not in NOT_CHECKS
    )
    if not scripts:
        print("FAIL: no verification scripts found")
        sys.exit(1)

    failed: list[str] = []
    skipped: list[str] = []
    passed = 0

    for script in scripts:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO), capture_output=True,
            encoding="utf-8", errors="replace", timeout=900,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        name = script.name

        if proc.returncode == 0:
            passed += 1
            print(f"  ok    {name}")
            continue

        reasons = CONDITIONAL.get(name)
        if reasons and any(r.lower() in output.lower() for r in reasons):
            skipped.append(name)
            print(f"  skip  {name}  (needs a live backend)")
            continue

        failed.append(name)
        last = [ln for ln in output.strip().splitlines() if ln.strip()]
        print(f"  FAIL  {name}  {last[-1][:90] if last else f'exit {proc.returncode}'}")

    print()
    print(f"ran {len(scripts)} scripts: {passed} passed, "
          f"{len(skipped)} skipped, {len(failed)} failed")

    if failed:
        print("FAIL: " + ", ".join(failed))
        sys.exit(1)

    print("ALL CHECKS VERIFICATION PASSED")


if __name__ == "__main__":
    main()
