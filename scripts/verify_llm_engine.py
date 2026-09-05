"""Prove the LLM ReAct loop works against a real served model over HTTP.

Why this exists
---------------
The unit tests drive the LLM loop through a subclass whose ``complete()``
returns canned strings. That proves the *loop logic*, but it never exercises the
real path: an actual HTTP request to a model server, a real model's free-form
text, and the parser meeting output nobody scripted. The report should not claim
the loop "works across all three engines" on the strength of a stub.

Usage
-----
    python scripts/verify_llm_engine.py              # auto-detect a backend
    python scripts/verify_llm_engine.py --engine ollama
    python scripts/verify_llm_engine.py --engine claude

Requires one of:
  * Ollama running locally  (`ollama serve` + `ollama pull llama3.2`)
  * ANTHROPIC_API_KEY set in the environment

Exits non-zero — loudly — when no backend is reachable, rather than skipping
quietly, so a green result can never mean "nothing was tested".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sage import config
from sage.agent import ClaudeEngine, GroqEngine, OllamaEngine

QUESTION = "Should I buy NVDA right now?"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def is_rate_limit(error: str) -> bool:
    """True when an error string describes a provider throughput cap.

    Deliberately narrow: an authentication failure must NOT match, or the
    script would tell someone with a dead key to simply wait.
    """
    text = (error or "").lower()
    if any(w in text for w in ("invalid api key", "unauthorized", "authentication", "401")):
        return False
    return "rate-limiting" in text or "rate limit" in text or "429" in text


def pick_engine(requested: str | None):
    """Return a live engine instance, or exit if none is reachable."""
    if requested in (None, "groq") and config.groq_available():
        print(f"backend: groq ({config.GROQ_MODEL} at {config.GROQ_URL})")
        return GroqEngine()
    if requested in (None, "ollama") and config.ollama_available():
        print(f"backend: ollama ({config.OLLAMA_MODEL} at {config.OLLAMA_URL})")
        return OllamaEngine()
    if requested in (None, "claude") and config.claude_available():
        print(f"backend: claude ({config.CLAUDE_MODEL})")
        return ClaudeEngine()

    fail(
        f"no LLM backend is reachable (requested: {requested or 'any'}).\n"
        "  For Groq:    set GROQ_API_KEY (free key at https://console.groq.com)\n"
        "  For Ollama:  install it, run `ollama serve`, then `ollama pull llama3.2`\n"
        "  For Claude:  set ANTHROPIC_API_KEY in your environment\n"
        "This check deliberately fails rather than skipping, so that a passing\n"
        "result always means a real model was exercised."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("groq", "ollama", "claude"), default=None)
    args = parser.parse_args()

    engine = pick_engine(args.engine)
    result = engine.run(QUESTION)

    print(f"question: {QUESTION}")
    print(f"engine:   {result.engine}")
    print(f"steps:    {len(result.steps)}")

    for step in result.steps:
        tool = step.action.tool if step.action else "(no tool)"
        note = f"  [{step.note}]" if step.note else ""
        print(f"  step {step.index}: {tool}{note}")
        print(f"    thought: {(step.thought or '')[:100]}")

    if result.error:
        # A throughput cap is not a broken key or a broken loop, and reporting
        # it as a flat failure sends the reader hunting for the wrong problem.
        if is_rate_limit(result.error):
            print(
                "\nRATE LIMITED — this is NOT a bad key and NOT a code fault.\n"
                f"  {result.error}\n"
                "  The loop already retried with backoff and the cap was still\n"
                "  in force. Free tiers cap tokens per minute, and each ReAct\n"
                "  step resends the whole conversation, so a long trace can\n"
                "  exhaust the window. Wait ~60s and re-run, pick a smaller\n"
                "  model via GROQ_MODEL, or demo the `rule` engine, which needs\n"
                "  no key at all."
            )
            sys.exit(2)  # distinct from 1, so callers can tell the cases apart
        fail(f"the live LLM run errored: {result.error}")

    if not result.steps:
        fail("the live LLM run produced no reasoning steps")

    # The whole point is tool use: the model must have actually called a tool
    # against real data, not just talked its way to an answer.
    tool_calls = [s for s in result.steps if s.action is not None]
    if not tool_calls:
        fail("the model never called a tool — the ReAct loop did not engage")

    for step in tool_calls:
        if step.observation is None:
            fail(f"step {step.index} called {step.action.tool} but recorded no observation")

    if result.final is None:
        fail("the live LLM run produced no final answer")
    if not result.final.rationale.strip():
        fail("the live LLM run produced an empty rationale")

    print(f"verdict:  {result.final.recommendation} ({result.final.confidence})")
    print(f"tool calls executed: {[s.action.tool for s in tool_calls]}")
    print("LLM ENGINE VERIFICATION PASSED")


if __name__ == "__main__":
    main()
