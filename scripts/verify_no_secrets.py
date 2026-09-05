"""Fail if any API key or other credential is committed to the repository.

The submission requires a publicly viewable repository. A key pushed to a public
repo is compromised the moment it lands, and graders, classmates and scrapers
can all read it. This check scans the files git actually tracks — not the
working tree — because that is what gets published.

A negative control proves the scanner can see a key: a known-format fake key is
run through the same matcher and must be detected. Without that, an empty result
could mean "clean" or "the pattern is broken", and those look identical.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Credential shapes worth catching, with a label for the report.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Groq API key", re.compile(r"gsk_[A-Za-z0-9]{20,}")),
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI API key", re.compile(r"sk-(?!ant-)[A-Za-z0-9]{32,}")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# This scanner necessarily contains key-shaped text (patterns and the control),
# so it would otherwise flag itself.
SELF = "scripts/verify_no_secrets.py"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def tracked_files() -> list[str]:
    """Return the repository-relative paths git is tracking."""
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=str(REPO),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        fail(f"`git ls-files` failed: {proc.stderr.strip()}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def scan(text: str) -> list[str]:
    """Return the labels of every credential pattern found in ``text``."""
    return [label for label, pattern in PATTERNS if pattern.search(text)]


def main() -> None:
    # --- Negative control: the scanner must be able to find a key. ----------
    # Assembled at runtime so this literal is not itself a scannable key.
    control = "gsk_" + ("A" * 40)
    if "Groq API key" not in scan(control):
        fail(
            "the scanner did not detect a known-format control key — a clean "
            "result would be meaningless"
        )
    print("negative control detected (scanner works)")

    files = tracked_files()
    if not files:
        fail("git is tracking no files; nothing was actually scanned")

    findings: list[str] = []
    scanned = 0
    for rel in files:
        if rel.replace("\\", "/") == SELF:
            continue
        path = REPO / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue  # binary or unreadable; key text would not survive anyway
        scanned += 1
        for label in scan(text):
            findings.append(f"{rel}: {label}")

    if findings:
        fail("credentials found in tracked files:\n  " + "\n  ".join(findings))

    # The example secrets file must stay an example.
    example = REPO / ".streamlit" / "secrets.toml.example"
    if example.exists():
        text = example.read_text(encoding="utf-8", errors="ignore")
        if scan(text):
            fail(f"{example} contains a real-looking credential")

    # A real secrets.toml must never be tracked.
    if ".streamlit/secrets.toml" in [f.replace("\\", "/") for f in files]:
        fail(".streamlit/secrets.toml is tracked by git; it must be ignored")

    print(f"scanned {scanned} tracked file(s); no credentials found")
    print("SECRET SCAN PASSED")


if __name__ == "__main__":
    main()
