"""Configuration and engine-selection logic.

The guiding principle is *always work out of the box*: if no API keys and no
local Ollama server are available, Sage falls back to the deterministic ``rule``
engine, so the app deploys cleanly to Streamlit Community Cloud with zero setup.
"""

from __future__ import annotations

import os

# A handful of well-known, liquid tickers used as defaults / examples.
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA"]

# Cap on the number of Thought/Action/Observation cycles, to prevent runaway
# cost (LLM engines) and infinite loops.
MAX_STEPS = 8

# Local Ollama server (free, no key). Won't run on Streamlit Cloud — that's fine.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# Optional paid Anthropic backend. The spec asks for "claude-sonnet"; we pin the
# current Sonnet model id and allow an override via the environment.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

# The OpenAI-compatible engine. Many providers expose the same
# /chat/completions protocol — Groq, OpenRouter, Together, a local vLLM server —
# so the engine is named for the protocol it speaks rather than for one vendor.
# Point it anywhere by setting OPENAI_COMPAT_URL, _MODEL and _API_KEY.
#
# The GROQ_* names are still read as a fallback, because they were the original
# spelling and may be set in an existing environment or deployment.
def _setting(name: str, default: str) -> str:
    """Read OPENAI_COMPAT_<name>, falling back to the older GROQ_<name>."""
    return os.environ.get(f"OPENAI_COMPAT_{name}") or os.environ.get(
        f"GROQ_{name}", default
    )


# Defaults to OpenRouter, which is what the evaluation in the report was run
# against and which serves a range of free open-weight models.
OPENAI_COMPAT_URL = _setting("URL", "https://openrouter.ai/api/v1")

# minimax-m3 follows the plain-text Thought/Action/Action-Input format reliably.
# Some other served models (notably the GPT-OSS family) reach for their built-in
# function-calling mechanism instead, which Sage deliberately does not use. The
# engine recovers from that, but a model that emits the text format directly is
# a better demonstration of the loop.
OPENAI_COMPAT_MODEL = _setting("MODEL", "minimax/minimax-m3:free")

# Free tiers commonly cap *output* tokens per minute. A request asking for more
# than the cap is refused outright however long you wait, so the per-call budget
# must sit under it. One ReAct turn is a short thought plus a small JSON action,
# so this is comfortably enough.
OPENAI_COMPAT_MAX_TOKENS = int(_setting("MAX_TOKENS", "800"))

# Kept as aliases so existing code and configurations keep working.
GROQ_URL = OPENAI_COMPAT_URL
GROQ_MODEL = OPENAI_COMPAT_MODEL
GROQ_MAX_TOKENS = OPENAI_COMPAT_MAX_TOKENS

ENGINES = ("rule", "ollama", "openai", "claude")


def get_anthropic_key() -> str | None:
    """Return the Anthropic API key from the environment or Streamlit secrets.

    Reading secrets is wrapped in a try/except so that importing Streamlit (or
    the absence of a secrets file) can never crash a CLI or test run.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:  # pragma: no cover - depends on Streamlit runtime
        import streamlit as st

        return st.secrets.get("ANTHROPIC_API_KEY")  # type: ignore[no-any-return]
    except Exception:
        return None


def ollama_available(url: str = OLLAMA_URL, timeout: float = 0.5) -> bool:
    """Return True if a local Ollama server answers on ``url``."""
    try:
        import requests

        resp = requests.get(f"{url}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def get_openai_compat_key() -> str | None:
    """Return the OpenAI-compatible provider's API key.

    Mirrors :func:`get_anthropic_key`: the environment wins, Streamlit secrets
    are a fallback for the deployed app, and neither lookup may crash a CLI or
    test run. Both the current and the older ``GROQ_API_KEY`` spelling are
    accepted, so an environment configured before the rename keeps working.
    """
    for name in ("OPENAI_COMPAT_API_KEY", "GROQ_API_KEY"):
        key = os.environ.get(name)
        if key:
            return key
    try:  # pragma: no cover - depends on Streamlit runtime
        import streamlit as st

        for name in ("OPENAI_COMPAT_API_KEY", "GROQ_API_KEY"):
            key = st.secrets.get(name)
            if key:
                return key  # type: ignore[no-any-return]
    except Exception:
        return None
    return None


def openai_compat_available() -> bool:
    """Return True if a key is present and ``requests`` is importable."""
    if get_openai_compat_key() is None:
        return False
    try:
        import requests  # noqa: F401

        return True
    except Exception:
        return False


# Older names, kept so existing callers and tests keep working.
get_groq_key = get_openai_compat_key
groq_available = openai_compat_available


def claude_available() -> bool:
    """Return True if an Anthropic key is present and the SDK is importable."""
    if get_anthropic_key() is None:
        return False
    try:
        import anthropic  # noqa: F401

        return True
    except Exception:
        return False


def resolve_engine(preferred: str | None) -> str:
    """Pick an engine name, falling back to ``rule`` when a request can't be met.

    ``rule`` is always available. ``ollama`` and ``claude`` are only honoured
    when their backing service/key is actually reachable.
    """
    if preferred == "ollama" and ollama_available():
        return "ollama"
    # "groq" is accepted as the engine's former name.
    if preferred in ("openai", "groq") and openai_compat_available():
        return "openai"
    if preferred == "claude" and claude_available():
        return "claude"
    # "rule", an unavailable LLM engine, or no preference all land here.
    return "rule"
