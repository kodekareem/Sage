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

# Groq serves open-weight models behind an OpenAI-compatible API. It is fast and
# has a free tier, which makes it the practical way to demonstrate the loop
# driving a *real* LLM without needing a local GPU or a paid key.
GROQ_URL = os.environ.get("GROQ_URL", "https://api.groq.com/openai/v1")
# Qwen follows the plain-text Thought/Action/Action-Input format reliably. Some
# other served models (notably the GPT-OSS family) reach for their built-in
# function-calling mechanism instead, which Sage deliberately does not use — the
# engine recovers from that, but a model that emits the text format is a better
# demonstration of the loop.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")

# Free-tier Groq keys cap *output* tokens per minute (1000 on the default
# model). A request asking for more than the cap is refused outright, however
# long you wait, so the per-call budget must sit under it. One ReAct turn is a
# short thought plus a small JSON action, so this is comfortably enough.
GROQ_MAX_TOKENS = int(os.environ.get("GROQ_MAX_TOKENS", "800"))

ENGINES = ("rule", "ollama", "groq", "claude")


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


def get_groq_key() -> str | None:
    """Return the Groq API key from the environment or Streamlit secrets.

    Mirrors :func:`get_anthropic_key`: the environment wins, Streamlit secrets
    are a fallback for the deployed app, and neither lookup may crash a CLI or
    test run.
    """
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    try:  # pragma: no cover - depends on Streamlit runtime
        import streamlit as st

        return st.secrets.get("GROQ_API_KEY")  # type: ignore[no-any-return]
    except Exception:
        return None


def groq_available() -> bool:
    """Return True if a Groq key is present and ``requests`` is importable."""
    if get_groq_key() is None:
        return False
    try:
        import requests  # noqa: F401

        return True
    except Exception:
        return False


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
    if preferred == "groq" and groq_available():
        return "groq"
    if preferred == "claude" and claude_available():
        return "claude"
    # "rule", an unavailable LLM engine, or no preference all land here.
    return "rule"
