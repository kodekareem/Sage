"""Unit tests for the ReAct engines.

Covers:
* question parsing (ticker extraction, intent detection),
* the rule engine producing a valid step-by-step trace and a sensible verdict,
* the LLM loop logic — using a fake model so no network is needed — including
  correct parsing of tool calls, the step cap, and malformed-output handling.
"""

from __future__ import annotations

from sage.agent import (
    LLMEngine,
    RuleEngine,
    detect_intent,
    extract_tickers,
)


# --------------------------------------------------------------------------- #
# Question parsing
# --------------------------------------------------------------------------- #
def test_extract_tickers_from_names_and_symbols():
    assert extract_tickers("Should I buy NVIDIA?") == ["NVDA"]
    assert extract_tickers("Compare AAPL and MSFT") == ["AAPL", "MSFT"]
    assert extract_tickers("thoughts on $TSLA") == ["TSLA"]


def test_extract_tickers_ignores_stopwords():
    # "I" and "BUY" are all-caps but must not be treated as tickers.
    assert extract_tickers("Should I BUY apple") == ["AAPL"]


def test_detect_intent():
    assert detect_intent("compare AAPL and MSFT", ["AAPL", "MSFT"]) == "compare"
    assert detect_intent("AAPL vs MSFT", ["AAPL", "MSFT"]) == "compare"
    assert detect_intent("should I buy AAPL", ["AAPL"]) == "single"


# --------------------------------------------------------------------------- #
# Rule engine
# --------------------------------------------------------------------------- #
def test_rule_engine_single_produces_valid_trace():
    result = RuleEngine().run("Should I buy AAPL right now?")
    assert result.engine == "rule"
    assert result.error is None
    # Three scripted tool steps: quote, indicators, fundamentals.
    assert len(result.steps) == 3
    for step in result.steps:
        assert step.thought  # every step has a thought
        assert step.action is not None
        assert step.observation is not None
        assert step.observation["ok"] is True
    # A verdict was produced.
    assert result.final is not None
    assert result.final.recommendation in {"BUY", "HOLD", "SELL"}
    assert result.final.confidence in {"low", "medium", "high"}


def test_rule_engine_uptrend_is_not_sell():
    # AAPL fixture is a clean uptrend with reasonable P/E -> should lean BUY/HOLD.
    result = RuleEngine().run("Should I buy AAPL?")
    assert result.final.recommendation in {"BUY", "HOLD"}


def test_rule_engine_comparison():
    result = RuleEngine().run("Compare AAPL and MSFT for a long-term hold")
    assert result.error is None
    assert len(result.steps) == 2
    assert result.steps[0].action.tool == "compare_tickers"
    assert result.final is not None
    assert result.final.recommendation.startswith("PREFER")


def test_rule_engine_no_ticker_sets_error():
    result = RuleEngine().run("What is a good investment strategy?")
    assert result.final is None
    assert result.error is not None


# --------------------------------------------------------------------------- #
# LLM loop logic (with a scripted fake model — no network)
# --------------------------------------------------------------------------- #
class ScriptedEngine(LLMEngine):
    """An LLM engine whose 'model' returns pre-canned strings in order."""

    name = "scripted"

    def __init__(self, replies, max_steps=8):
        super().__init__(max_steps=max_steps)
        self._replies = list(replies)
        self._i = 0

    def complete(self, messages):
        reply = self._replies[min(self._i, len(self._replies) - 1)]
        self._i += 1
        return reply


def test_llm_loop_executes_tool_then_finishes():
    replies = [
        'Thought: check price.\nAction: get_quote\nAction Input: {"ticker": "AAPL"}',
        'Thought: done.\nFinal Answer: {"recommendation": "BUY", "confidence": "high", "rationale": "ok"}',
    ]
    result = ScriptedEngine(replies).run("Should I buy AAPL?")
    assert result.error is None
    assert result.final.recommendation == "BUY"
    # First step actually called the tool and recorded a real observation.
    assert result.steps[0].action.tool == "get_quote"
    assert result.steps[0].observation["ok"] is True


def test_llm_loop_respects_step_cap():
    # A model that never finishes — always asks for another tool call.
    looping = 'Thought: again.\nAction: get_quote\nAction Input: {"ticker": "AAPL"}'
    result = ScriptedEngine([looping], max_steps=4).run("Should I buy AAPL?")
    assert result.final is None
    assert result.error is not None
    assert "maximum" in result.error.lower()
    assert len(result.steps) == 4  # exactly the cap, no more


def test_llm_loop_handles_malformed_output():
    # Two consecutive unparseable replies should abort gracefully.
    result = ScriptedEngine(["blah blah", "still nonsense"], max_steps=6).run("Should I buy AAPL?")
    assert result.final is None
    assert result.error is not None
    assert "parse" in result.error.lower()
    # The malformed steps are recorded honestly in the trace.
    assert any(step.note for step in result.steps)
