"""Verify the report is inside every word limit the brief sets.

The brief caps each chapter and the whole report, and says submissions over the
limit are penalised. It also excludes references, figure and table captions and
chapter titles from the count, so a naive word count would report a number the
marker would not recognise.

Counted as body prose:      ordinary paragraphs and list items
Excluded, per the brief:    chapter and section headings, the reference list,
                            figure and table captions, and fenced code blocks,
                            which are not prose either

Prints a per-chapter table so the headroom is visible, and fails if any single
chapter or the whole report exceeds its cap.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "report" / "final-report.md"

TOTAL_LIMIT = 10_500
CHAPTER_LIMITS = {
    "Introduction": 1000,
    "Literature Review": 2500,
    "Design": 2000,
    "Implementation": 2500,
    "Evaluation": 2500,
    "Conclusion": 1000,
}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def count_words(lines: list[str]) -> int:
    """Count body prose, excluding the things the brief excludes."""
    total = 0
    in_code = False
    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):          # headings
            continue
        if stripped.startswith(("Figure ", "Table ")):   # captions
            continue
        if stripped.startswith("|") or set(stripped) <= set("|-: "):  # tables
            continue
        if stripped.startswith(">"):          # block quotes used for notes
            stripped = stripped.lstrip("> ")

        # Strip markdown emphasis and links so syntax is not counted as words.
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", stripped)
        text = re.sub(r"[*_`]", "", text)
        text = re.sub(r"^[-*+]\s+", "", text)
        total += len([w for w in text.split() if any(c.isalnum() for c in w)])
    return total


def main() -> None:
    if not REPORT.exists():
        fail(f"{REPORT.relative_to(REPO)} does not exist")

    lines = REPORT.read_text(encoding="utf-8").splitlines()

    # Split on chapter headings ("## 1. Introduction" and similar).
    chapters: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        heading = re.match(r"^##\s+(?:\d+\.?\s*)?(.+?)\s*$", line)
        if heading and not line.startswith("###"):
            title = heading.group(1).strip()
            # The reference list is excluded from the word count entirely.
            current = None if title.lower().startswith("reference") else title
            if current:
                chapters[current] = []
            continue
        if current:
            chapters[current].append(line)

    if not chapters:
        fail("no chapters found — expected headings like '## 1. Introduction'")

    counts = {name: count_words(body) for name, body in chapters.items()}

    print(f"{'chapter':24} {'words':>7} {'limit':>7}  headroom")
    problems: list[str] = []
    for name, limit in CHAPTER_LIMITS.items():
        match = next((k for k in counts if name.lower() in k.lower()), None)
        if match is None:
            problems.append(f"chapter missing from the report: {name}")
            continue
        words = counts[match]
        state = "OVER" if words > limit else f"{limit - words:>8}"
        print(f"  {match[:22]:22} {words:>7} {limit:>7}  {state}")
        if words > limit:
            problems.append(f"{name}: {words} words exceeds its {limit} limit")

    total = sum(counts.values())
    print(f"\n  {'TOTAL':22} {total:>7} {TOTAL_LIMIT:>7}  "
          f"{'OVER' if total > TOTAL_LIMIT else total and TOTAL_LIMIT - total}")

    if total > TOTAL_LIMIT:
        problems.append(f"total {total} words exceeds the {TOTAL_LIMIT} limit")

    if problems:
        fail("; ".join(problems))

    print("\nWORD LIMIT VERIFICATION PASSED")


if __name__ == "__main__":
    main()
