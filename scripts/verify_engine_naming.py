"""Verify the OpenAI-compatible engine is named for its protocol, not a vendor.

The engine was originally called `groq`, but the evaluation reported in the
write-up was run through OpenRouter by overriding environment variables. A
reader comparing the report to the running app would have seen an engine called
`groq` described as an OpenRouter result, which looks like a mistake in one or
the other.

This checks that the code, the app and the report agree, and that the former
name still works so nothing already configured breaks.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from sage import config  # noqa: E402
from sage.agent import GroqEngine, OpenAICompatEngine, create_engine  # noqa: E402

REPORT = REPO / "report" / "final-report.md"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    # --- the engine list names the protocol, not the vendor ---------------
    if "openai" not in config.ENGINES:
        fail(f"'openai' is not a registered engine: {config.ENGINES}")
    if "groq" in config.ENGINES:
        fail("'groq' is still advertised as an engine name; it names one vendor")
    print(f"engines: {config.ENGINES}")

    # --- the default provider is the one the evaluation actually used -----
    if "openrouter" not in config.OPENAI_COMPAT_URL.lower():
        fail(
            "the default provider is not the one the reported evaluation ran "
            f"against: {config.OPENAI_COMPAT_URL}"
        )
    print(f"default provider: {config.OPENAI_COMPAT_URL}")
    print(f"default model:    {config.OPENAI_COMPAT_MODEL}")

    # --- the former name must keep working --------------------------------
    if GroqEngine is not OpenAICompatEngine:
        fail("the former class name GroqEngine no longer aliases the engine")

    import os
    os.environ.setdefault("OPENAI_COMPAT_API_KEY", "naming-check-placeholder")
    if config.resolve_engine("groq") != "openai":
        fail("the former engine name 'groq' no longer resolves")
    try:
        engine = create_engine("groq")
    except Exception as exc:
        fail(f"create_engine('groq') failed: {exc}")
    if engine.name != "openai":
        fail(f"the engine reports its name as {engine.name!r}, expected 'openai'")
    print("former name 'groq' still resolves, to the renamed engine")

    # --- the app must offer what the code registers -----------------------
    app = (REPO / "app.py").read_text(encoding="utf-8")
    for engine_name in config.ENGINES:
        if f'"{engine_name}"' not in app:
            fail(f"app.py has no sidebar label for the '{engine_name}' engine")
    print("app.py labels every registered engine")

    # --- every document must agree with the code --------------------------
    # The README was missed when the engine was first renamed, which is exactly
    # the drift this check exists to catch, so it is checked alongside the
    # report rather than trusted.
    for path in (REPORT, REPO / "README.md", REPO / "report" / "video-script.md"):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "`groq`" in text:
            fail(f"{path.name} still names a 'groq' engine, which no longer exists")
        # A bare mention of Groq as one provider among several is fine; naming
        # it as *the* engine or its environment variable is not.
        for stale in ("GROQ_API_KEY", "GROQ_MODEL", "GROQ_MAX_TOKENS", "--engine groq"):
            if stale in text and "GROQ_*" not in text:
                fail(f"{path.name} still instructs the reader to use {stale}")
        print(f"{path.name}: consistent with the engine's name")

    if REPORT.exists() and "OpenRouter" not in REPORT.read_text(encoding="utf-8"):
        fail("the report does not name the provider the evaluation used")

    print("ENGINE NAMING VERIFICATION PASSED")


if __name__ == "__main__":
    main()
