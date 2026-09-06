"""Verify the spoken claims in the video script match the measured data.

The script is narrated aloud on a recording that cannot be quietly corrected
later. If the evaluation is re-run and a percentage moves, a script saying
"eighty three percent" becomes a false statement delivered in the author's own
voice, on the record.

Every numeric claim in a SAY: line is checked against its source: the evaluation
results file for the measured percentages and the question count, and the live
code for the tool and engine counts. Spoken numbers are written as words, so
they are mapped back to digits before comparison.

Checks accuracy only. verify_video_script.py covers runtime and constraints.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SCRIPT = REPO / "report" / "video-script.md"
DATA = REPO / "report" / "data" / "evaluation-offline.json"

WORD_NUMBERS = {
    "one hundred": 100, "ninety": 90, "eighty three": 83, "eighty-three": 83,
    "eighty": 80, "seventy": 70, "sixty": 60, "fifty": 50, "forty": 40,
    "thirty": 30, "twenty five": 25, "twenty": 20, "fifteen": 15,
    "fourteen": 14, "twelve": 12, "ten": 10, "eight": 8, "seven": 7,
    "six": 6, "five": 5, "four": 4, "three": 3, "two": 2, "one": 1,
}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def spoken_text() -> str:
    t = SCRIPT.read_text(encoding="utf-8")
    passages = re.findall(
        r"^[ \t]*SAY:[ \t]*(.+?)(?=\n[ \t]*\n|\n[ \t]*(?:SAY|SHOW|#|-)|\Z)",
        t, re.MULTILINE | re.DOTALL,
    )
    if not passages:
        fail("no spoken passages found")
    return " ".join(" ".join(p.split()) for p in passages)


def says(blob: str, phrase: str) -> bool:
    """True when the script contains this spoken phrase, digits or words."""
    return re.search(re.escape(phrase), blob, re.IGNORECASE) is not None


def main() -> None:
    if not SCRIPT.exists():
        fail(f"{SCRIPT.name} does not exist")
    if not DATA.exists():
        fail(f"{DATA.name} does not exist - run the evaluation first")

    blob = spoken_text()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    rule, llm = data["rule"], data["llm"]

    def as_words(value: float) -> str:
        """Render a measured figure the way the script would say it."""
        n = int(round(value))
        for word, number in WORD_NUMBERS.items():
            if number == n:
                return word
        return str(n)

    problems: list[str] = []

    # --- the measured percentages the script quotes ------------------------
    claims = [
        ("rule engine, all four measures", 100.0,
         all(rule[k] == 100.0 for k in
             ("trace_valid_pct", "grounded_pct", "tools_appropriate_pct",
              "answered_correctly_pct"))),
        ("language model groundedness", llm["grounded_pct"], None),
        ("language model behaviour", llm["answered_correctly_pct"], None),
    ]

    # "one hundred percent on all four" is only true if all four really are 100.
    if not claims[0][2]:
        problems.append(
            "the script says the rule engine scores one hundred percent on all "
            f"four measures, but the data shows "
            f"{rule['trace_valid_pct']}/{rule['grounded_pct']}/"
            f"{rule['tools_appropriate_pct']}/{rule['answered_correctly_pct']}"
        )
    elif not says(blob, "one hundred percent"):
        problems.append("the script no longer states the rule engine's measured 100%")

    for label, value, _ in claims[1:]:
        spoken = as_words(value)
        if not (says(blob, f"{spoken} percent") or says(blob, f"{value:g} percent")):
            problems.append(
                f"{label} measures {value}%, which the script does not say "
                f"(expected '{spoken} percent')"
            )
        else:
            print(f"  {label}: {value}% stated correctly")

    # --- the question count ------------------------------------------------
    questions = data["question_count"]
    if not (says(blob, f"{as_words(questions)} fixed questions")
            or says(blob, f"{questions} fixed questions")):
        problems.append(f"the study covers {questions} questions; the script disagrees")
    else:
        print(f"  question count: {questions} stated correctly")

    # --- counts that come from the code, not the data ----------------------
    from sage import config
    from sage.tools import TOOL_REGISTRY

    tools = len(TOOL_REGISTRY)
    if not (says(blob, f"{as_words(tools)} tools") or says(blob, f"{tools} tools")):
        problems.append(f"the code registers {tools} tools; the script disagrees")
    else:
        print(f"  tool count: {tools} stated correctly")

    engines = len(config.ENGINES)
    if not (says(blob, f"{as_words(engines)} engines") or says(blob, f"{engines} engines")):
        problems.append(f"the code has {engines} engines; the script disagrees")
    else:
        print(f"  engine count: {engines} stated correctly")

    # --- the script must not name an engine that no longer exists ----------
    for stale in ("groq engine", "`groq`"):
        if says(blob, stale):
            problems.append(f"the script names {stale!r}, which no longer exists")

    if problems:
        fail("spoken claims disagree with the measured data:\n  " + "\n  ".join(problems))

    print("VIDEO CLAIMS VERIFICATION PASSED")


if __name__ == "__main__":
    main()
