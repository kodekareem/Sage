"""Data layer: a thin, cached wrapper around ``yfinance``.

Responsibilities:

* Fetch historical OHLCV price data and company fundamentals for any ticker.
* Cache results **in memory per process** so repeated tool calls within a single
  question (or session) don't hammer the Yahoo Finance endpoints.
* Translate the library's many failure modes into two clear exceptions
  (:class:`InvalidTickerError`, :class:`NetworkError`) so the tool library can
  report errors in a consistent, structured way.

The tools call the module-level functions (``fetch_history`` / ``fetch_info``),
which makes them trivial to monkeypatch in tests — the unit suite never touches
the network.
"""

from __future__ import annotations

import pandas as pd


class DataError(Exception):
    """Base class for all data-layer failures."""


class InvalidTickerError(DataError):
    """Raised when a ticker symbol returns no data (likely invalid/delisted)."""


class NetworkError(DataError):
    """Raised when the underlying request fails (offline, rate-limited, etc.)."""


# Simple in-memory caches. Keyed so the same ticker/period is only fetched once.
_history_cache: dict[tuple[str, str], pd.DataFrame] = {}
_info_cache: dict[str, dict] = {}


def clear_cache() -> None:
    """Empty both caches (used by the UI 'refresh' control and by tests)."""
    _history_cache.clear()
    _info_cache.clear()


def fetch_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Return a daily OHLCV ``DataFrame`` for ``ticker`` over ``period``.

    Parameters
    ----------
    ticker:
        Stock symbol, case-insensitive (e.g. ``"aapl"``).
    period:
        Any period string ``yfinance`` accepts (``"1mo"``, ``"6mo"``, ``"1y"``,
        ``"2y"`` ...). One year is enough to compute the 200-day moving average.

    Raises
    ------
    InvalidTickerError
        If no rows come back for the symbol.
    NetworkError
        If the request itself fails.
    """
    key = (ticker.upper(), period)
    if key in _history_cache:
        return _history_cache[key]

    try:
        import yfinance as yf

        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    except Exception as exc:  # network / parsing failures
        raise NetworkError(f"Could not fetch price history for {ticker!r}: {exc}") from exc

    if df is None or df.empty:
        raise InvalidTickerError(
            f"No price data for {ticker!r}. It may be an invalid or delisted symbol."
        )

    _history_cache[key] = df
    return df


def fetch_info(ticker: str) -> dict:
    """Return the ``yfinance`` ``.info`` dict (fundamentals) for ``ticker``.

    Raises
    ------
    InvalidTickerError
        If the info payload is empty or clearly unpopulated.
    NetworkError
        If the request itself fails.
    """
    key = ticker.upper()
    if key in _info_cache:
        return _info_cache[key]

    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
    except Exception as exc:
        raise NetworkError(f"Could not fetch fundamentals for {ticker!r}: {exc}") from exc

    # yfinance sometimes returns a near-empty dict for bad symbols.
    if not info or len(info) < 3:
        raise InvalidTickerError(
            f"No fundamentals for {ticker!r}. It may be an invalid or delisted symbol."
        )

    _info_cache[key] = info
    return info
