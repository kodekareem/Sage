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
    # Sizing questions name one ticker but are not buy/sell/hold questions.
    assert detect_intent(
        "I have $10000, risk 2% on AAPL at 150 stop 140. How many shares?", ["AAPL"]
    ) == "size"
    # "risk" without any numbers is not a sizing request.
    assert detect_intent("is AAPL a risky stock?", ["AAPL"]) == "single"


# --------------------------------------------------------------------------- #
# Rule engine
# --------------------------------------------------------------------------- #
def test_rule_engine_single_produces_valid_trace():
    result = RuleEngine().run("Should I buy AAPL right now?")
    assert result.engine == "rule"
    assert result.error is None
    # Four scripted tool steps: quote, history, indicators, fundamentals.
    assert len(result.steps) == 4
    assert [s.action.tool for s in result.steps] == [
        "get_quote",
        "get_price_history",
        "calculate_technical_indicators",
        "get_fundamentals",
    ]
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
    # A comparison ends in either a preference or an explicit tie.
    assert result.final.recommendation.startswith(("PREFER", "TOO CLOSE TO CALL"))


def test_rule_engine_comparison_picks_a_clear_winner():
    """A genuinely stronger candidate is still named, not hidden behind a tie."""
    # The TSLA fixture is a downtrend on a rich P/E; AAPL is a clean uptrend.
    result = RuleEngine().run("Compare AAPL and TSLA for a long-term hold")
    assert result.error is None
    assert result.final.recommendation == "PREFER AAPL"


def test_comparison_tie_is_declared_not_broken_silently():
    """Equal scores must be reported as a tie rather than resolved arbitrarily."""
    rows = [
        {"ticker": "AAA", "crossover_signal": "golden_cross", "rsi": 50, "trailing_pe": 30},
        {"ticker": "BBB", "crossover_signal": "golden_cross", "rsi": 50, "trailing_pe": 30},
    ]
    verdict, scores = RuleEngine._comparison_verdict(rows)
    assert scores["AAA"] == scores["BBB"]
    assert verdict.recommendation.startswith("TOO CLOSE TO CALL")
    assert "AAA" in verdict.recommendation and "BBB" in verdict.recommendation
    assert verdict.confidence == "low"


def test_comparison_verdict_is_order_independent():
    """The same evidence must yield the same verdict whichever order it arrives in."""
    rows = [
        {"ticker": "AAA", "crossover_signal": "golden_cross", "rsi": 50, "trailing_pe": 30},
        {"ticker": "BBB", "crossover_signal": "golden_cross", "rsi": 50, "trailing_pe": 30},
    ]
    forward, _ = RuleEngine._comparison_verdict(rows)
    reverse, _ = RuleEngine._comparison_verdict(list(reversed(rows)))
    assert forward.recommendation == reverse.recommendation
    assert forward.confidence == reverse.confidence

    # And the same must hold when there is a real winner.
    decided = [
        {"ticker": "AAA", "crossover_signal": "death_cross", "rsi": 75, "trailing_pe": 60},
        {"ticker": "BBB", "crossover_signal": "golden_cross", "rsi": 25, "trailing_pe": 20},
    ]
    fwd, _ = RuleEngine._comparison_verdict(decided)
    rev, _ = RuleEngine._comparison_verdict(list(reversed(decided)))
    assert fwd.recommendation == rev.recommendation == "PREFER BBB"


# --------------------------------------------------------------------------- #
# Position sizing path (makes estimate_position_size reachable by the agent)
# --------------------------------------------------------------------------- #
def test_position_size_question_uses_the_sizing_tool():
    result = RuleEngine().run(
        "I have a $10000 account, risk 2% buying AAPL at 150 with a stop at 140. "
        "How many shares should I take?"
    )
    assert result.error is None
    assert result.final is not None
    tools_called = [s.action.tool for s in result.steps if s.action]
    assert "estimate_position_size" in tools_called
    # 2% of 10000 = 200 risk budget; 10 per share => 20 shares.
    assert result.final.recommendation == "20 shares"
    observation = result.steps[-1].observation
    assert observation["shares"] == 20
    assert observation["risk_amount"] == 200.0


def test_position_size_reads_a_labelled_stop_not_just_position():
    """'stop at 200' must be read as the stop even when the entry is unstated.

    Reading numbers purely by position mistook the stop for the entry price and
    then complained that no stop was given.
    """
    result = RuleEngine().run(
        "I have $10000 and want to risk 2% on AAPL with a stop at 90. How many shares?"
    )
    assert result.error is None, result.error
    sizing = [s for s in result.steps if s.action and s.action.tool == "estimate_position_size"]
    assert len(sizing) == 1
    args = sizing[0].action.tool_input
    assert args["stop"] == 90
    assert args["account_size"] == 10000
    assert args["risk_pct"] == 2
    # The entry was not stated, so it must have come from a live quote step.
    assert any(s.action and s.action.tool == "get_quote" for s in result.steps)


def test_position_size_singular_share_grammar():
    """One share reads as '1 share', not '1 shares'."""
    result = RuleEngine().run(
        "I have $1000, risk 1% on AAPL at 150 with a stop at 140. How many shares?"
    )
    assert result.final is not None
    # 1% of 1000 = 10 budget; 10 per share => exactly 1 share.
    assert result.final.recommendation == "1 share"


def test_position_size_zero_shares_is_explained():
    """A trade that cannot fit the risk budget is explained, not reported as 0."""
    result = RuleEngine().run(
        "I have $100, risk 1% on AAPL at 150 with a stop at 100. How many shares?"
    )
    assert result.final is not None
    assert result.final.recommendation.startswith("0 shares")
    assert "risk limit" in result.final.recommendation
    assert "exceed the risk budget" in result.final.rationale


def test_position_size_rationale_has_no_trailing_zeros():
    """Figures read back cleanly (10000, not 10000.0)."""
    result = RuleEngine().run(
        "I have $10000, risk 2% on AAPL at 150 with a stop at 140. How many shares?"
    )
    assert "10000.0" not in result.final.rationale
    assert "2.0%" not in result.final.rationale


def test_position_size_without_stop_reports_the_gap():
    """A missing stop is reported honestly rather than invented."""
    result = RuleEngine().run(
        "I have a $10000 account and want to risk 2% on AAPL. How many shares?"
    )
    assert result.final is None
    assert result.error is not None
    assert "stop" in result.error.lower()


def test_price_history_informs_the_single_stock_verdict():
    """The history observation is actually used, not merely fetched."""
    result = RuleEngine().run("Should I buy AAPL right now?")
    history_steps = [s for s in result.steps if s.action and s.action.tool == "get_price_history"]
    assert len(history_steps) == 1
    assert history_steps[0].observation["ok"] is True
    # The AAPL fixture doubles over the window, so the rationale must say so.
    assert "over the last" in result.final.rationale


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
