"""Verify the documents describe the interface the app actually presents.

The report, the README and the video script all describe what a viewer sees.
When the UI changes, those descriptions go stale silently: the prose still
reads well, and nothing fails. That happened when the sidebar stopped showing
availability markers and started hiding unreachable engines instead, and it
matters most in the video script, where a stale stage direction is read aloud
over footage that contradicts it.

Every element a document tells the reader to look at must exist in app.py, and
descriptions of behaviour the app no longer has are rejected.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "app.py"
DOCS = {
    "report": REPO / "report" / "final-report.md",
    "video script": REPO / "report" / "video-script.md",
    "README": REPO / "README.md",
}

# UI text a document may direct a reader to. Each must exist in the app.
ELEMENTS = [
    "Reasoning engine", "Tool library", "Max reasoning steps",
    "Clear data cache", "Analyse", "Recommendation", "Reasoning trace",
]

# Descriptions that were true of an earlier interface and are not true now.
# Each is a phrase, the reason it is stale, and the docs it must not appear in.
STALE = [
    (r"showing the four options and their\s+availability markers",
     "the sidebar no longer shows availability markers; it hides unreachable engines"),
    (r"shows which engines are available",
     "the sidebar offers only available engines rather than marking them"),
    (r"four options",
     "the sidebar offers only the engines that can run, which is not always four"),
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    app = APP.read_text(encoding="utf-8")

    missing = [e for e in ELEMENTS if e not in app]
    if missing:
        fail(f"app.py no longer contains UI text the documents reference: {missing}")
    print(f"all {len(ELEMENTS)} referenced UI elements exist in app.py")

    problems: list[str] = []
    for label, path in DOCS.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, why in STALE:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                line = text[: m.start()].count("\n") + 1
                problems.append(f"{label} line {line}: {why} ({m.group(0)[:48]!r})")

    if problems:
        fail("documents describe an interface the app no longer presents:\n  "
             + "\n  ".join(problems))
    print(f"no stale interface descriptions in {len(DOCS)} documents")

    # The sidebar's own explanation must exist, since two documents now promise
    # the viewer will see it.
    if "hidden here" not in app:
        fail("the app no longer explains which engines it hid, but the documents say it does")
    print("the caption the documents promise is present in the app")

    print("UI DESCRIPTION VERIFICATION PASSED")


if __name__ == "__main__":
    main()
