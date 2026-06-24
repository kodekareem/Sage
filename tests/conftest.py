"""Shared pytest fixtures.

The whole suite runs **offline**: an autouse fixture monkeypatches the data
layer's ``fetch_history`` / ``fetch_info`` with deterministic synthetic data, so
no test ever touches the Yahoo Finance network. The synthetic series are crafted
so the indicators and the rule-engine verdicts are predictable:

* AAPL — strong uptrend  (price above SMA200, golden cross)
* MSFT — mild uptrend
* TSLA — downtrend        (price below SMA200, death cross)
* NVDA — strong uptrend
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from sage import data_layer


def _build_series(n: int, start: float, end: float, amp: float = 3.0) -> pd.DataFrame:
    """Build an OHLCV frame: a linear trend from ``start`` to ``end`` plus a small
    deterministic oscillation so RSI has both gains and losses to work with.
    """
    dates = pd.date_range(end="2024-12-31", periods=n, freq="B")
    closes = []
    for i in range(n):
        trend = start + (end - start) * (i / (n - 1))
        wobble = amp * math.sin(i / 4.0)  # deterministic up/down oscillation
        closes.append(round(trend + wobble, 2))
    close = pd.Series(closes, index=dates)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": [1_000_000] * n,
        },
        index=dates,
    )


# Pre-built price histories, keyed by ticker. ~260 business days (>1 year) so the
# 200-day SMA is always computable.
_HISTORIES = {
    "AAPL": _build_series(260, 100, 200),  # strong uptrend
    "MSFT": _build_series(260, 100, 120),  # mild uptrend
    "TSLA": _build_series(260, 200, 100),  # downtrend
    "NVDA": _build_series(260, 80, 220),   # strong uptrend
}

# Synthetic fundamentals, keyed by ticker.
_INFOS = {
    "AAPL": {"shortName": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics",
             "marketCap": 3_000_000_000_000, "trailingPE": 28.0, "forwardPE": 26.0,
             "dividendYield": 0.5, "beta": 1.2, "fiftyTwoWeekHigh": 210, "fiftyTwoWeekLow": 90},
    "MSFT": {"shortName": "Microsoft Corp.", "sector": "Technology", "industry": "Software",
             "marketCap": 2_500_000_000_000, "trailingPE": 35.0, "forwardPE": 30.0,
             "dividendYield": 0.8, "beta": 0.9, "fiftyTwoWeekHigh": 130, "fiftyTwoWeekLow": 95},
    "TSLA": {"shortName": "Tesla Inc.", "sector": "Consumer Cyclical", "industry": "Auto",
             "marketCap": 700_000_000_000, "trailingPE": 60.0, "forwardPE": 50.0,
             "dividendYield": None, "beta": 2.0, "fiftyTwoWeekHigh": 210, "fiftyTwoWeekLow": 95},
    "NVDA": {"shortName": "NVIDIA Corp.", "sector": "Technology", "industry": "Semiconductors",
             "marketCap": 2_000_000_000_000, "trailingPE": 45.0, "forwardPE": 35.0,
             "dividendYield": 0.0003, "beta": 1.7, "fiftyTwoWeekHigh": 230, "fiftyTwoWeekLow": 70},
}


def _fake_fetch_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    df = _HISTORIES.get(ticker.upper())
    if df is None:
        raise data_layer.InvalidTickerError(f"No synthetic data for {ticker!r}.")
    return df


def _fake_fetch_info(ticker: str) -> dict:
    info = _INFOS.get(ticker.upper())
    if info is None:
        raise data_layer.InvalidTickerError(f"No synthetic fundamentals for {ticker!r}.")
    return info


@pytest.fixture(autouse=True)
def patch_data(monkeypatch):
    """Replace the network-backed data layer with the synthetic fixtures."""
    monkeypatch.setattr(data_layer, "fetch_history", _fake_fetch_history)
    monkeypatch.setattr(data_layer, "fetch_info", _fake_fetch_info)
    data_layer.clear_cache()
    yield
