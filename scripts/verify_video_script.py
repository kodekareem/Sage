"""Verify the video script fits the brief's constraints.

The brief caps the video at 3-5 minutes, requires the author's own spoken
narration, and forbids AI voices and speeding up. A script that reads long is a
penalty, so the runtime is estimated from the word count at a measured speaking
rate rather than guessed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "report" / "video-script.md"

# Unhurried delivery for a technical demo. Deliberately conservative: a script
# that only fits at 160 wpm would need rushing, which reads badly on camera.
WORDS_PER_MINUTE = 130
MIN_MINUTES, MAX_MINUTES = 3.0, 5.0


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not SCRIPT.exists():
        fail(f"{SCRIPT.relative_to(REPO)} does not exist")
    text = SCRIPT.read_text(encoding="utf-8")

    # Spoken passages are marked SAY: and wrap over several lines, running until
    # a blank line or the next directive. Counting only the first line of each
    # would badly underestimate the runtime.
    spoken = re.findall(
        r"^[ \t]*SAY:[ \t]*(.+?)(?=\n[ \t]*\n|\n[ \t]*(?:SAY|SHOW|#|-)|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not spoken:
        fail("no spoken passages found - mark narration with 'SAY:'")

    words = sum(len(passage.split()) for passage in spoken)
    minutes = words / WORDS_PER_MINUTE
    print(f"spoken words: {words}")
    print(f"estimated runtime at {WORDS_PER_MINUTE} wpm: {minutes:.1f} min")

    if minutes < MIN_MINUTES:
        fail(f"too short: {minutes:.1f} min, the brief requires at least {MIN_MINUTES}")
    if minutes > MAX_MINUTES:
        fail(f"too long: {minutes:.1f} min, the brief caps it at {MAX_MINUTES}")

    # The constraints must be recorded in the script itself, so they are in
    # front of whoever records it rather than in a chat message.
    lowered = text.lower()
    for needle, why in [
        ("no ai", "the no-AI-voice rule"),
        ("speed", "the no-speeding-up rule"),
        ("own voice", "the own-voice requirement"),
    ]:
        if needle not in lowered:
            fail(f"the script does not record {why}")
    print("records the no-AI-voice, no-speed-up and own-voice constraints")

    # Shot direction: a script with no visuals is a monologue.
    shots = re.findall(r"^\s*SHOW:\s*(.+)$", text, re.MULTILINE)
    if len(shots) < 6:
        fail(f"only {len(shots)} SHOW: directions - the brief asks for appropriate visuals")
    print(f"{len(shots)} shot directions")

    print("VIDEO SCRIPT VERIFICATION PASSED")


if __name__ == "__main__":
    main()
