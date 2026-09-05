"""Verify the CLI emits non-ASCII characters intact on a legacy cp1252 console.

The audit caught the CLI printing ``Sage <?> engine: rule`` — the em-dash in the
banner was being replaced because Windows hands Python a cp1252 stdout that
cannot encode it. Any CLI footage in the submission video would show the
mangling.

This script runs the *real* ``run.py`` in a child process whose I/O encoding is
forced to cp1252, reproducing the original failure condition rather than
simulating it, and asserts the em-dash survives the round trip.

The child is run with ``PYTHONIOENCODING=cp1252``. If the fix works only because
the developer's terminal happens to be UTF-8, this check still fails — which is
the point.

A negative control confirms the harness can actually observe the defect: a child
that does *not* apply the fix must fail to emit the character cleanly. Without
that control, a check that merely looked for absence of the replacement
character could pass for the wrong reason (e.g. the process crashing early).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EM_DASH = "—"
REPLACEMENT_MARKERS = ("�", "?")


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def run_child(code: str) -> subprocess.CompletedProcess:
    """Run ``code`` in a child Python forced to a cp1252 console."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        # Decode as UTF-8 so we see exactly what bytes the child emitted; if the
        # child wrote cp1252 replacement bytes, they show up as mangled here.
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def main() -> None:
    # --- Negative control: prove this harness can see the defect. -----------
    # A plain cp1252 stdout must NOT be able to emit the em-dash cleanly.
    control = run_child(
        "import sys; sys.stdout.write('BANNER ' + chr(0x2014) + ' end\\n')"
    )
    if EM_DASH in control.stdout:
        fail(
            "negative control did not reproduce the cp1252 defect — this check "
            "cannot distinguish a fix from an already-UTF-8 environment"
        )
    print("negative control reproduced the cp1252 mangling (as expected)")

    # --- The real CLI must survive the same hostile console. ----------------
    # `--help` renders the argparse description and engine help, both of which
    # contain em-dashes, and it is offline and deterministic (no network).
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    proc = subprocess.run(
        [sys.executable, "run.py", "ask", "--help"],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )

    if proc.returncode != 0:
        fail(f"`run.py ask --help` exited {proc.returncode}\n{proc.stdout}\n{proc.stderr}")

    combined = proc.stdout + proc.stderr

    # The engine help text contains an em-dash; it must arrive intact.
    if EM_DASH not in combined:
        fail(
            "the CLI produced no intact em-dash on a cp1252 console; "
            f"output began: {combined[:400]!r}"
        )

    if "�" in combined:
        fail(f"the CLI emitted a replacement character: {combined[:400]!r}")

    # --- The trace renderer is the part seen in the video. ------------------
    # Render a real ReActResult containing non-ASCII text through display.py.
    trace_code = (
        "import run\n"  # importing run.py applies the CLI's encoding fix
        "from sage.react import ReActResult, ReActStep, Action, FinalAnswer\n"
        "from sage.display import render_trace\n"
        "r = ReActResult(question='Compare AAPL \\u2014 MSFT', engine='rule')\n"
        "r.steps.append(ReActStep(index=1, thought='Checking \\u2014 the price',\n"
        "    action=Action(tool='get_quote', tool_input={'ticker': 'AAPL'}),\n"
        "    observation={'ok': True, 'price': 1.0}))\n"
        "r.final = FinalAnswer('HOLD', 'low', 'Evidence \\u2014 balanced.')\n"
        "render_trace(r)\n"
    )
    trace = run_child(trace_code)

    if trace.returncode != 0:
        fail(f"rendering a trace failed on cp1252\n{trace.stdout}\n{trace.stderr}")

    trace_out = trace.stdout + trace.stderr
    if EM_DASH not in trace_out:
        fail(f"the rendered trace lost its em-dash: {trace_out[:400]!r}")
    if "�" in trace_out:
        fail(f"the rendered trace emitted a replacement character: {trace_out[:400]!r}")

    print("`run.py ask --help` and the trace renderer both kept their em-dashes")
    print("ENCODING VERIFICATION PASSED")


if __name__ == "__main__":
    main()
