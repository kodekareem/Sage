"""Write each chapter's measured word count into its own title.

The submission form requires the count in the chapter title, for example
"1. Introduction (783/1000 words)". Typing those by hand invites two failures:
a number that was right when written and wrong after an edit, and a number that
never matched the marker's own count.

So the counts are measured from the body text and stamped in. The count excludes
the title line itself, so adding the stamp cannot change the number it reports.
Run after any edit to the report; it is idempotent.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from verify_report_limits import CHAPTER_LIMITS, count_words  # noqa: E402

REPORT = REPO / "report" / "final-report.md"


def main() -> None:
    if not REPORT.exists():
        print(f"FAIL: {REPORT} does not exist")
        sys.exit(1)

    lines = REPORT.read_text(encoding="utf-8").splitlines()

    # Collect each chapter's body, keyed by the index of its heading line.
    bodies: dict[int, list[str]] = {}
    current: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+(?!#)", line):
            title = re.sub(r"^##\s+(?:\d+\.?\s*)?", "", line).strip()
            title = re.sub(r"\s*\(\d[\d,]*/\d[\d,]*\s*words\)\s*$", "", title)
            current = i if any(c.lower() in title.lower() for c in CHAPTER_LIMITS) else None
            if current is not None:
                bodies[current] = []
            continue
        if current is not None:
            bodies[current].append(line)

    if not bodies:
        print("FAIL: no chapters found")
        sys.exit(1)

    stamped = 0
    for index, body in bodies.items():
        heading = lines[index]
        # Strip any previous stamp so re-running does not accumulate them.
        base = re.sub(r"\s*\(\d[\d,]*/\d[\d,]*\s*words\)\s*$", "", heading).rstrip()
        name = re.sub(r"^##\s+(?:\d+\.?\s*)?", "", base).strip()
        limit = next(v for k, v in CHAPTER_LIMITS.items() if k.lower() in name.lower())
        words = count_words(body)
        lines[index] = f"{base} ({words}/{limit} words)"
        print(f"  {name:22} {words:>5}/{limit}")
        stamped += 1

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"stamped {stamped} chapter titles")


if __name__ == "__main__":
    main()
