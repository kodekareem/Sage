"""Unit tests for the tool library.

Each tool is checked for the correct return *structure* on known synthetic
input, plus a few behavioural checks (math, error handling).
"""

from __future__ import annotations

import pytest

from sage import data_layer
from sage import tools


def test_get_quote_structure():
    out = tools.get_quote("AAPL")
    assert out["ok"] is True
    assert out["ticker"] == "AAPL"
    assert isinstance(out["price"], float)
    assert {"change", "change_pct", "previous_close", "as_of"} <= out.keys()


def test_get_price_history_structure():
    out = tools.get_price_history("AAPL", period="6mo")
    assert out["ok"] is True
    assert out["start_price"] < out["end_price"]  # AAPL fixture is an uptrend
    assert out["num_days"] > 0
    assert {"high", "low", "period_return_pct"} <= out.keys()


def test_calculate_technical_indicators_structure_and_signals():
    out = tools.calculate_technical_indicators("AAPL")
    assert out["ok"] is True
    assert 0 <= out["rsi"] <= 100
    assert out["sma50"] is not None and out["sma200"] is not None
    # Strong uptrend -> price above the 200-day average and a golden cross.
    assert out["price_above_sma200"] is True
    assert out["crossover_signal"] == "golden_cross"


def test_technical_indicators_downtrend_is_death_cross():
    out = tools.calculate_technical_indicators("TSLA")
    assert out["crossover_signal"] == "death_cross"
    assert out["price_above_sma200"] is False


def test_get_fundamentals_structure():
    out = tools.get_fundamentals("AAPL")
    assert out["ok"] is True
    assert out["sector"] == "Technology"
    assert out["trailing_pe"] == 28.0
    # yfinance returns dividend yield already as a percentage; reported as-is.
    assert out["dividend_yield_pct"] == 0.5


def test_compare_tickers_structure():
    out = tools.compare_tickers(["AAPL", "MSFT"])
    assert out["ok"] is True
    assert len(out["rows"]) == 2
    tickers = {row["ticker"] for row in out["rows"]}
    assert tickers == {"AAPL", "MSFT"}
    for row in out["rows"]:
        assert {"price", "trailing_pe", "rsi", "crossover_signal"} <= row.keys()


def test_compare_tickers_requires_two():
    out = tools.compare_tickers(["AAPL"])
    assert out["ok"] is False


def test_estimate_position_size_math():
    out = tools.estimate_position_size(account_size=10_000, risk_pct=2, entry=100, stop=90)
    assert out["ok"] is True
    assert out["risk_amount"] == 200.0     # 2% of 10,000
    assert out["per_share_risk"] == 10.0   # |100 - 90|
    assert out["shares"] == 20             # 200 / 10
    assert out["position_value"] == 2000.0


def test_estimate_position_size_zero_risk():
    out = tools.estimate_position_size(account_size=10_000, risk_pct=2, entry=100, stop=100)
    assert out["ok"] is False


def test_estimate_position_size_rejects_negative_risk():
    out = tools.estimate_position_size(account_size=10_000, risk_pct=-2, entry=100, stop=90)
    assert out["ok"] is False


def test_invalid_ticker_is_structured_error(monkeypatch):
    def boom(ticker, period="1y"):
        raise data_layer.InvalidTickerError("bad symbol")

    monkeypatch.setattr(data_layer, "fetch_history", boom)
    out = tools.get_quote("ZZZZ")
    assert out["ok"] is False
    assert "error" in out


def test_run_tool_unknown_tool():
    out = tools.run_tool("does_not_exist", {})
    assert out["ok"] is False


def test_run_tool_bad_arguments():
    # estimate_position_size requires several args; passing none is a TypeError
    # that should surface as a structured error, not an exception.
    out = tools.run_tool("estimate_position_size", {})
    assert out["ok"] is False


def test_registry_has_all_expected_tools():
    expected = {
        "get_quote",
        "get_price_history",
        "calculate_technical_indicators",
        "get_fundamentals",
        "compare_tickers",
        "estimate_position_size",
    }
    assert expected <= set(tools.TOOL_REGISTRY)
