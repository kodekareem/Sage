"""Verify each chapter title states its own measured word count.

The submission form requires the count in the title, for example
"1. Introduction (783/1000 words)". This checks three things: that every chapter
carries a stamp, that the stated count matches a fresh measurement of that
chapter's body, and that the stated limit is the one the brief sets.

The count is re-measured here rather than trusted, so a title that was accurate
when written and stale after an edit is caught.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from verify_report_limits import CHAPTER_LIMITS, count_words  # noqa: E402

REPORT = REPO / "report" / "final-report.md"
STAMP = re.compile(r"\((\d[\d,]*)/(\d[\d,]*)\s*words\)\s*$")


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not REPORT.exists():
        fail(f"{REPORT} does not exist")
    lines = REPORT.read_text(encoding="utf-8").splitlines()

    chapters: list[tuple[str, str, list[str]]] = []   # name, heading, body
    current: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+(?!#)", line):
            title = re.sub(r"^##\s+(?:\d+\.?\s*)?", "", line).strip()
            bare = STAMP.sub("", title).strip()
            match = next((k for k in CHAPTER_LIMITS if k.lower() in bare.lower()), None)
            if match:
                chapters.append((match, line, []))
                current = len(chapters) - 1
            else:
                current = None
            continue
        if current is not None:
            chapters[current][2].append(line)

    if len(chapters) != len(CHAPTER_LIMITS):
        fail(f"found {len(chapters)} chapters, expected {len(CHAPTER_LIMITS)}")

    problems: list[str] = []
    for name, heading, body in chapters:
        stamp = STAMP.search(heading)
        if not stamp:
            problems.append(f"{name}: title states no word count")
            continue

        stated = int(stamp.group(1).replace(",", ""))
        stated_limit = int(stamp.group(2).replace(",", ""))
        measured = count_words(body)
        limit = CHAPTER_LIMITS[name]

        if stated_limit != limit:
            problems.append(f"{name}: title says limit {stated_limit}, the brief sets {limit}")
        if stated != measured:
            problems.append(
                f"{name}: title says {stated} words, the body measures {measured}"
            )
        if measured > limit:
            problems.append(f"{name}: {measured} words exceeds its {limit} limit")
        print(f"  {name:22} {measured:>5}/{limit}  stated {stated}")

    # The front matter states a total. It is typed rather than generated, which
    # is exactly the drift these checks exist to catch, so verify it too.
    text = REPORT.read_text(encoding="utf-8")
    measured_total = sum(count_words(body) for _, _, body in chapters)
    declared = re.search(r"Total word count:\*{0,2}\s*([\d,]+)\s*of\s*([\d,]+)", text)
    if not declared:
        fail("the report does not state a total word count")

    stated_total = int(declared.group(1).replace(",", ""))
    stated_cap = int(declared.group(2).replace(",", ""))
    if stated_total != measured_total:
        fail(f"stated total {stated_total} but the chapters measure {measured_total}")
    if stated_cap != 10_500:
        fail(f"stated cap {stated_cap}, the brief sets 10500")
    if measured_total > 10_500:
        fail(f"total {measured_total} exceeds the 10500 limit")
    print(f"  {'TOTAL':22} {measured_total:>5}/10500  stated {stated_total}")

    if problems:
        fail("; ".join(problems))

    print("CHAPTER COUNT VERIFICATION PASSED")


if __name__ == "__main__":
    main()
