"""Unit tests for the LLM output parser.

The parser is the bridge between free-form model text and the structured ReAct
trace, so it gets dedicated coverage: well-formed actions, well-formed final
answers, JSON in code fences, free-text finals, and malformed output.
"""

from __future__ import annotations

from sage.agent import parse_react_output


def test_parse_action():
    text = (
        "Thought: I should check the latest price.\n"
        "Action: get_quote\n"
        'Action Input: {"ticker": "AAPL"}'
    )
    parsed = parse_react_output(text)
    assert parsed["kind"] == "action"
    assert parsed["action"] == "get_quote"
    assert parsed["action_input"] == {"ticker": "AAPL"}
    assert "latest price" in parsed["thought"]


def test_parse_action_with_code_fence():
    text = (
        "Thought: compare them.\n"
        "Action: compare_tickers\n"
        "Action Input: ```json\n{\"tickers\": [\"AAPL\", \"MSFT\"]}\n```"
    )
    parsed = parse_react_output(text)
    assert parsed["kind"] == "action"
    assert parsed["action_input"] == {"tickers": ["AAPL", "MSFT"]}


def test_parse_final_answer_json():
    text = (
        "Thought: I have enough information.\n"
        'Final Answer: {"recommendation": "BUY", "confidence": "high", '
        '"rationale": "Strong uptrend and reasonable valuation."}'
    )
    parsed = parse_react_output(text)
    assert parsed["kind"] == "final"
    assert parsed["final"]["recommendation"] == "BUY"
    assert parsed["final"]["confidence"] == "high"
    assert "uptrend" in parsed["final"]["rationale"]


def test_parse_final_answer_freeform():
    # A final answer without valid JSON is still captured as a rationale.
    text = "Thought: done.\nFinal Answer: I would hold for now given the mixed signals."
    parsed = parse_react_output(text)
    assert parsed["kind"] == "final"
    assert "hold" in parsed["final"]["rationale"].lower()


def test_parse_final_answer_with_trailing_prose():
    # Models sometimes append commentary after the JSON; it must still parse.
    text = (
        "Thought: done.\n"
        'Final Answer: {"recommendation": "SELL", "confidence": "medium", '
        '"rationale": "Overbought."} Hope that helps!'
    )
    parsed = parse_react_output(text)
    assert parsed["kind"] == "final"
    assert parsed["final"]["recommendation"] == "SELL"
    assert parsed["final"]["confidence"] == "medium"


def test_parse_malformed():
    text = "I'm not following the format at all, just chatting."
    parsed = parse_react_output(text)
    assert parsed["kind"] == "malformed"


def test_parse_action_missing_input_defaults_to_empty():
    text = "Thought: try it.\nAction: get_quote"
    parsed = parse_react_output(text)
    assert parsed["kind"] == "action"
    assert parsed["action_input"] == {}


def test_final_answer_takes_precedence_over_action():
    # If both appear, a Final Answer should win so the loop stops.
    text = (
        "Thought: wrap up.\n"
        "Action: get_quote\n"
        'Final Answer: {"recommendation": "HOLD", "confidence": "low", "rationale": "x"}'
    )
    parsed = parse_react_output(text)
    assert parsed["kind"] == "final"
