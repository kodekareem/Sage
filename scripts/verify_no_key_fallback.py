"""Verify Sage works with no API keys at all, as the deployed demo will.

The project's deployment story is that it runs on Streamlit Community Cloud with
no secrets configured: every LLM engine falls back to the deterministic ``rule``
engine so the demo always works. That promise is easy to break by accident — a
new engine that raises instead of falling back, or a config lookup that assumes
a key exists — and it would break in front of a grader, not on this machine
where keys happen to be set.

This check runs Sage in a child process with every credential stripped from the
environment, so a key set in this shell cannot mask a regression.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Every credential Sage might pick up, removed from the child's environment.
KEY_VARS = ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")

CHILD = r"""
import sys
sys.path.insert(0, r"{repo}")

from sage import config
from sage.agent import create_engine

problems = []

# 1. Nothing may report itself as available without a key.
if config.groq_available():
    problems.append("groq reports available with no GROQ_API_KEY")
if config.claude_available():
    problems.append("claude reports available with no ANTHROPIC_API_KEY")

# 2. Every engine name must resolve to something runnable.
for name in config.ENGINES:
    resolved = config.resolve_engine(name)
    if resolved not in config.ENGINES:
        problems.append(f"resolve_engine({{name!r}}) returned {{resolved!r}}")
    # With no keys and (presumably) no Ollama, anything but rule must fall back.
    if name in ("groq", "claude") and resolved != "rule":
        problems.append(f"{{name}} did not fall back to rule (got {{resolved!r}})")

# 3. An unknown engine name must still resolve to a working engine.
if config.resolve_engine("nonsense-engine") != "rule":
    problems.append("an unknown engine name did not fall back to rule")
if config.resolve_engine(None) != "rule":
    problems.append("no preference did not fall back to rule")

# 4. Asking for an unavailable engine explicitly must raise a clear error
#    rather than crash with an AttributeError or hang.
for name in ("groq", "claude"):
    try:
        create_engine(name)
        problems.append(f"create_engine({{name!r}}) succeeded without a key")
    except RuntimeError:
        pass  # the documented, helpful failure
    except Exception as exc:
        problems.append(f"create_engine({{name!r}}) raised {{type(exc).__name__}}: {{exc}}")

# 5. The resolved default engine must actually answer a question offline.
import pandas as pd
from sage import data_layer

dates = pd.date_range(end="2024-12-31", periods=260, freq="B")
closes = [100 + i * 0.4 for i in range(260)]
frame = pd.DataFrame({{"Open": closes, "High": [c + 1 for c in closes],
                      "Low": [c - 1 for c in closes], "Close": closes,
                      "Volume": [1_000_000] * 260}}, index=dates)
data_layer.fetch_history = lambda t, period="1y": frame
data_layer.fetch_info = lambda t: {{"shortName": "X", "sector": "Tech",
                                   "marketCap": 1, "trailingPE": 20.0}}

engine = create_engine(config.resolve_engine("claude"))
result = engine.run("Should I buy NVDA right now?")
if result.error:
    problems.append(f"the fallback engine errored: {{result.error}}")
if result.final is None:
    problems.append("the fallback engine produced no recommendation")
if not result.steps:
    problems.append("the fallback engine produced no reasoning steps")

if problems:
    for p in problems:
        print("PROBLEM:", p)
    sys.exit(1)

print("engine:", result.engine)
print("verdict:", result.final.recommendation)
print("CHILD OK")
"""


def main() -> None:
    env = {k: v for k, v in os.environ.items() if k not in KEY_VARS}
    # Point Ollama at a dead port so a locally-running server cannot mask a
    # missing fallback; the deployed app has no Ollama either.
    env["OLLAMA_URL"] = "http://127.0.0.1:1"

    stripped = [k for k in KEY_VARS if k in os.environ]
    print(f"stripped from child environment: {stripped or 'none were set'}")

    proc = subprocess.run(
        [sys.executable, "-c", CHILD.format(repo=str(REPO))],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )

    output = (proc.stdout or "") + (proc.stderr or "")
    print(output.strip())

    if proc.returncode != 0 or "CHILD OK" not in output:
        print("FAIL: Sage does not work cleanly with no API keys set")
        sys.exit(1)

    print("NO-KEY FALLBACK VERIFICATION PASSED")


if __name__ == "__main__":
    main()
