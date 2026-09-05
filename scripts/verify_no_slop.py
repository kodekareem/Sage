"""Scan the report for the AI-slop vocabulary and sentence patterns.

The banned words and structures come from the no-ai-slop skill. They are worth
catching mechanically because they survive a read-through: "delve", "robust",
"it's worth noting" and the "not X, but Y" construction all look like ordinary
prose in isolation and only read as generated writing in aggregate.

A negative control runs the same matcher over a deliberately slop-laden sample
first. If that sample comes back clean the matcher is broken, and a clean report
would mean nothing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "report" / "final-report.md"

BANNED_WORDS = [
    "delve", "foster", "leverage", "utilize", "utilise", "facilitate",
    "empower", "streamline", "robust", "cutting-edge", "paradigm shift",
    "game changer", "tapestry", "realm", "beacon", "multifaceted",
    "meticulous", "intricate", "paramount", "transformative", "elevate",
    "embark", "supercharge", "harness", "ever-evolving",
]

BANNED_PHRASES = [
    "it's worth noting", "it is worth noting", "it's important to note",
    "it is important to note", "at the end of the day", "when it comes to",
    "at its core", "in today's world", "in the age of", "in the world of",
    "the reality is", "the truth is", "going forward", "in this article",
    "let's dive in", "this is huge", "this changes everything",
    "stands as a testament", "marks a pivotal moment", "plays a vital role",
    "solidifies its position", "underscores its significance",
    "experts agree", "studies show", "widely regarded as",
]

PATTERNS: list[tuple[str, str]] = [
    (r"\bit'?s not (?:just )?\w+[^.;]{0,40},? (?:it'?s|but) \w+",
     "binary contrast (\"it's not X, it's Y\") - state the point directly"),
    (r"\bthe question isn'?t\b", "binary contrast setup - state the point"),
    (r"\bhere'?s the thing\b", "throat-clearing opener"),
    (r"\bwhat most people (?:get wrong|miss)\b", "faux-insight setup"),
    (r"\bhere'?s what nobody tells you\b", "faux-insight setup"),
    (r"\bthe part everyone misses\b", "faux-insight setup"),
    (r"(?:highlight|underscor|showcas|reflect)ing (?:the|a|its|his|her|their)\b",
     "superficial -ing analysis clause"),
    (r"\bin conclusion\b", "summary-recap ending"),
    (r"\b(?:ultimately|overall),", "summary-recap opener"),
    # The banned pattern is the dramatic reveal: a short noun phrase standing
    # alone, a colon, then a lowercase punchline, used for fake weight. An
    # ordinary explanatory colon inside a full sentence is normal academic
    # prose, so the pattern requires the colon to follow a short fragment at the
    # start of a line rather than appearing mid-sentence.
    # A reveal is a short standalone fragment (at most four words, no verb of
    # its own doing work) followed by a colon and a lowercase punchline. The
    # length bound is what separates it from an ordinary explanatory colon,
    # which in academic prose follows a complete clause.
    (r"(?:^|\n)[ \t]*(?:[A-Z][a-z']*(?:[ \t]+[a-z']+){0,3}):[ \t]+[a-z][^.\n]{0,70}\.",
     "colon reveal (short fragment, colon, lowercase punchline)"),
]

CONTROL = """
    In today's world, it is important to note that this robust and cutting-edge
    system will empower users and streamline their workflow. It's not just a
    tool, it's a paradigm shift. Here's the thing: experts agree this
    transformative approach will elevate outcomes, highlighting the team's
    meticulous work. In conclusion, we must delve into the intricate realm.
"""


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def scan(text: str) -> list[str]:
    """Return every slop finding in ``text``, as human-readable lines."""
    findings: list[str] = []
    lowered = text.lower()

    for word in BANNED_WORDS:
        for match in re.finditer(rf"\b{re.escape(word)}\b", lowered):
            line = text[: match.start()].count("\n") + 1
            findings.append(f"line {line}: banned word '{word}'")

    for phrase in BANNED_PHRASES:
        for match in re.finditer(re.escape(phrase), lowered):
            line = text[: match.start()].count("\n") + 1
            findings.append(f"line {line}: empty phrase '{phrase}'")

    for pattern, why in PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            line = text[: match.start()].count("\n") + 1
            findings.append(f"line {line}: {why} - {match.group(0)[:60]!r}")

    return findings


def main() -> None:
    # --- Negative control: the matcher must catch obvious slop. -----------
    control_hits = scan(CONTROL)
    if len(control_hits) < 12:
        fail(
            f"the matcher found only {len(control_hits)} problems in a sample "
            "written to be full of them; a clean report would prove nothing"
        )
    print(f"negative control: {len(control_hits)} findings in the slop sample (matcher works)")

    if not REPORT.exists():
        fail(f"{REPORT.relative_to(REPO)} does not exist")

    text = REPORT.read_text(encoding="utf-8")
    findings = scan(text)

    if findings:
        fail(f"{len(findings)} slop findings in the report:\n  " + "\n  ".join(findings[:40]))

    # Em dashes: the skill allows one or two in a long piece, not a rhythm crutch.
    em_dashes = text.count("—")
    if em_dashes > 6:
        fail(f"{em_dashes} em dashes - they are being used as a rhythm crutch")

    words = len(text.split())
    print(f"scanned {words:,} words: no banned vocabulary or slop patterns")
    print(f"em dashes: {em_dashes}")
    print("SLOP SCAN PASSED")


if __name__ == "__main__":
    main()
