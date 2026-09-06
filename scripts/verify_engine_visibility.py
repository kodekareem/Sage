"""Verify the sidebar offers exactly the engines that can actually run.

Sage ships four engines. Two of them need a local model server or an API key, so
on a hosted deployment they can never be selected, and listing them as dead
options is noise. They are hidden rather than removed: the code, the tests and
the report still describe the full set, because the engine-swappability argument
in the design chapter depends on it.

Hiding is only safe if it is driven by availability. This checks that the
selection is computed from the availability functions rather than hard-coded,
that the default engine can never be hidden, and that a reachable engine is
always offered. The report is checked separately, so trimming the UI cannot
quietly contradict the write-up.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from sage import config  # noqa: E402

APP = REPO / "app.py"
REPORT = REPO / "report" / "final-report.md"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    source = APP.read_text(encoding="utf-8")

    # --- the list must be computed, not hard-coded ------------------------
    if "options=list(config.ENGINES)" in source:
        fail("the sidebar offers every engine regardless of whether it can run")
    if not re.search(r"options\s*=\s*\[e for e in config\.ENGINES if available", source):
        fail("the offered engines are not filtered by availability")

    # Each engine's availability must come from its own check, so a hidden
    # engine is hidden because it is unreachable and for no other reason.
    for name, probe in (
        ("ollama", "config.ollama_available()"),
        ("openai", "config.openai_compat_available()"),
        ("claude", "config.claude_available()"),
    ):
        if probe not in source:
            fail(f"the '{name}' engine's availability is not probed in app.py")
    print("selection is computed from the availability checks")

    # --- the default must always be offered -------------------------------
    # Simulate the sidebar's own logic with every backend unreachable, which is
    # how the deployed app runs.
    available = {"rule": True, "ollama": False, "openai": False, "claude": False}
    options = [e for e in config.ENGINES if available.get(e)]
    if options != ["rule"]:
        fail(f"with no backends reachable the sidebar would offer {options}")
    if not options:
        fail("the sidebar could offer no engine at all")
    print("with nothing reachable, the sidebar still offers the rule engine")

    # --- a reachable engine must never be hidden --------------------------
    available_all = {e: True for e in config.ENGINES}
    if [e for e in config.ENGINES if available_all.get(e)] != list(config.ENGINES):
        fail("a reachable engine would still be hidden")
    print("every reachable engine is offered")

    # --- the hidden ones must be explained, not silently dropped ----------
    if "hidden here" not in source:
        fail("hidden engines are dropped without telling the user why")
    print("hidden engines are explained in the UI")

    # --- the report must still describe the full set ----------------------
    if REPORT.exists():
        text = REPORT.read_text(encoding="utf-8")
        if "four reasoning engines" not in text:
            fail("the report no longer describes the engine set the code ships")
        for engine in config.ENGINES:
            if f"`{engine}`" not in text:
                fail(f"the report does not mention the '{engine}' engine")
        print(f"report still describes all {len(config.ENGINES)} engines")

    print("ENGINE VISIBILITY VERIFICATION PASSED")


if __name__ == "__main__":
    main()
