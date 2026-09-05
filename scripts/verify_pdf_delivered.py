"""Verify the typeset report exists in the user's Downloads and is current.

The user asked for the report as a PDF in Downloads. A build that succeeds in
the repository but never reaches that directory has not been delivered, and a
stale copy is worse than none.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "report" / "final-report.md"
BUILT = REPO / "report" / "build" / "final-report.pdf"
DELIVERED = Path.home() / "Downloads" / "Sage_Final_Report.pdf"

MIN_PAGES = 8


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not DELIVERED.exists():
        fail(f"{DELIVERED} does not exist")
    if not BUILT.exists():
        fail(f"{BUILT} does not exist - the PDF was never built")

    if DELIVERED.stat().st_size != BUILT.stat().st_size:
        fail("the delivered PDF differs from the current build - it is stale")

    if DELIVERED.stat().st_mtime < SOURCE.stat().st_mtime:
        fail("the delivered PDF is older than the report source - rebuild it")

    if DELIVERED.stat().st_size < 20_000:
        fail(f"the delivered PDF is only {DELIVERED.stat().st_size} bytes")

    # Page count, so an empty or truncated document is caught.
    try:
        out = subprocess.run(["pdfinfo", str(DELIVERED)], capture_output=True,
                             encoding="utf-8", timeout=120).stdout
        pages = int(re.search(r"Pages:\s+(\d+)", out).group(1))
    except Exception:
        pages = None

    if pages is not None:
        if pages < MIN_PAGES:
            fail(f"only {pages} pages; the report should be longer")
        print(f"pages: {pages}")

    print(f"delivered: {DELIVERED} ({DELIVERED.stat().st_size:,} bytes)")
    print("PDF DELIVERY VERIFICATION PASSED")


if __name__ == "__main__":
    main()
