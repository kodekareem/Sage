"""The financial analysis tool library — one of the two core deliverables.

Each tool is a clean Python function with a clear signature, a docstring, and a
**structured return value** (always a dict with an ``"ok"`` flag). Tools never
raise to the agent: a failed lookup comes back as ``{"ok": False, "error": ...}``
so the ReAct loop can observe the failure and reason about it.

Tools are registered in :data:`TOOL_REGISTRY`, a name -> :class:`Tool` mapping.
Each :class:`Tool` carries a JSON-schema-style ``parameters`` description, so the
agent can be handed a machine-readable catalogue and adding a new tool is just a
matter of writing a function and decorating it with :func:`tool`.

All indicators (RSI, SMA, crossover) are computed in pure Python via pandas —
no TA-Lib or other heavy dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from . import data_layer
from .data_layer import DataError


# --------------------------------------------------------------------------- #
# Registry plumbing
# --------------------------------------------------------------------------- #
@dataclass
class Tool:
    """A registered tool: the callable plus a JSON-schema-style description."""

    name: str
    description: str
    parameters: dict           # JSON-schema-style {name: {type, description}}
    func: Callable[..., dict]

    def __call__(self, **kwargs) -> dict:
        return self.func(**kwargs)


TOOL_REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, parameters: dict):
    """Decorator that registers a function as a tool in :data:`TOOL_REGISTRY`."""

    def decorator(func: Callable[..., dict]) -> Callable[..., dict]:
        TOOL_REGISTRY[name] = Tool(name, description, parameters, func)
        return func

    return decorator


def tool_catalogue() -> str:
    """Return a human/LLM-readable description of every registered tool."""
    lines = []
    for t in TOOL_REGISTRY.values():
        args = ", ".join(
            f"{k}: {v.get('type', 'any')}" for k, v in t.parameters.items()
        )
        lines.append(f"- {t.name}({args}) — {t.description}")
    return "\n".join(lines)


def run_tool(name: str, tool_input: dict) -> dict:
    """Execute a registered tool by name with a dict of arguments.

    Unknown tools and bad arguments are returned as structured errors rather
    than raised, so the agent can observe and recover from them.
    """
    tool_obj = TOOL_REGISTRY.get(name)
    if tool_obj is None:
        return {"ok": False, "error": f"Unknown tool {name!r}."}
    try:
        return tool_obj(**(tool_input or {}))
    except TypeError as exc:  # wrong / missing arguments
        return {"ok": False, "error": f"Bad arguments for {name!r}: {exc}"}


# --------------------------------------------------------------------------- #
# Pure-Python indicator helpers
# --------------------------------------------------------------------------- #
def _rsi(close: pd.Series, period: int = 14) -> float | None:
    """Wilder's Relative Strength Index for the latest bar (0-100)."""
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder smoothing == exponential moving average with alpha = 1/period.
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    last_gain = avg_gain.iloc[-1]
    last_loss = avg_loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = last_gain / last_loss
    return round(float(100 - (100 / (1 + rs))), 2)


def _sma(close: pd.Series, window: int) -> float | None:
    """Simple moving average over the last ``window`` bars."""
    if len(close) < window:
        return None
    value = close.rolling(window).mean().iloc[-1]
    if pd.isna(value):  # NaN must become None so the downstream guards work.
        return None
    return round(float(value), 2)


def _round(value, ndigits: int = 2):
    """Round numbers; pass non-numbers (e.g. None, strings) straight through."""
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return value


# --------------------------------------------------------------------------- #
# The tools
# --------------------------------------------------------------------------- #
@tool(
    name="get_quote",
    description="Latest price and the most recent day's change for a ticker.",
    parameters={"ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL"}},
)
def get_quote(ticker: str) -> dict:
    """Return the latest close and day-over-day change for ``ticker``."""
    try:
        df = data_layer.fetch_history(ticker, period="5d")
    except DataError as exc:
        return {"ok": False, "ticker": ticker.upper(), "error": str(exc)}

    close = df["Close"]
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else price
    change = price - prev
    change_pct = (change / prev * 100) if prev else 0.0
    return {
        "ok": True,
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "previous_close": round(prev, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "as_of": str(df.index[-1].date()),
    }


#: Period strings the data source accepts.
VALID_PERIODS = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")

#: Common near-misses an LLM produces, mapped to the real thing. Correcting an
#: obvious slip is friendlier than bouncing the whole reasoning step, and the
#: correction is reported in the observation so the trace stays honest.
_PERIOD_ALIASES = {
    "1m": "1mo", "3m": "3mo", "6m": "6mo", "12m": "1y",
    "1month": "1mo", "3months": "3mo", "6months": "6mo",
    "1week": "5d", "1w": "5d", "1year": "1y", "2year": "2y", "2years": "2y",
    "ytd.": "ytd", "year": "1y", "daily": "1d",
}


@tool(
    name="get_price_history",
    description="Summary of historical prices over a period (start/end/high/low/return).",
    parameters={
        "ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL"},
        "period": {
            "type": "string",
            "description": (
                "Look-back window. Must be exactly one of: 1d, 5d, 1mo, 3mo, "
                "6mo, 1y, 2y, 5y, 10y, ytd, max. Default 6mo."
            ),
        },
    },
)
def get_price_history(ticker: str, period: str = "6mo") -> dict:
    """Return a compact summary of price action over ``period``."""
    corrected = None
    if period not in VALID_PERIODS:
        candidate = _PERIOD_ALIASES.get(str(period).strip().lower())
        if candidate is None:
            return {
                "ok": False,
                "ticker": ticker.upper(),
                "error": (
                    f"Invalid period {period!r}. Use one of: "
                    f"{', '.join(VALID_PERIODS)}."
                ),
            }
        corrected, period = period, candidate

    try:
        df = data_layer.fetch_history(ticker, period=period)
    except DataError as exc:
        return {"ok": False, "ticker": ticker.upper(), "error": str(exc)}

    close = df["Close"]
    start = float(close.iloc[0])
    end = float(close.iloc[-1])
    result = {
        "ok": True,
        "ticker": ticker.upper(),
        "period": period,
        "start_price": round(start, 2),
        "end_price": round(end, 2),
        "high": round(float(close.max()), 2),
        "low": round(float(close.min()), 2),
        "period_return_pct": round((end - start) / start * 100, 2) if start else 0.0,
        "num_days": int(len(close)),
    }
    if corrected is not None:
        # Say so in the observation rather than silently changing the request.
        result["note"] = f"Interpreted period {corrected!r} as {period!r}."
    return result


@tool(
    name="calculate_technical_indicators",
    description="RSI(14), SMA(50), SMA(200) and a moving-average crossover signal.",
    parameters={"ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL"}},
)
def calculate_technical_indicators(ticker: str) -> dict:
    """Compute momentum/trend indicators in pure Python.

    Returns RSI(14), the 50- and 200-day simple moving averages, the latest
    price, and a derived ``crossover_signal`` describing the SMA50/SMA200
    relationship (the classic golden-cross / death-cross trend signal).
    """
    try:
        # ~1 year of data is the minimum needed for a 200-day SMA.
        df = data_layer.fetch_history(ticker, period="1y")
    except DataError as exc:
        return {"ok": False, "ticker": ticker.upper(), "error": str(exc)}

    close = df["Close"]
    price = round(float(close.iloc[-1]), 2)
    rsi = _rsi(close)
    sma50 = _sma(close, 50)
    sma200 = _sma(close, 200)

    # Trend signal from the 50/200 relationship.
    if sma50 is not None and sma200 is not None:
        if sma50 > sma200:
            crossover = "golden_cross"  # bullish: short-term avg above long-term
        elif sma50 < sma200:
            crossover = "death_cross"   # bearish: short-term avg below long-term
        else:
            crossover = "neutral"
    else:
        crossover = "insufficient_data"

    # Momentum reading from RSI.
    if rsi is None:
        rsi_signal = "insufficient_data"
    elif rsi >= 70:
        rsi_signal = "overbought"
    elif rsi <= 30:
        rsi_signal = "oversold"
    else:
        rsi_signal = "neutral"

    return {
        "ok": True,
        "ticker": ticker.upper(),
        "price": price,
        "rsi": rsi,
        "rsi_signal": rsi_signal,
        "sma50": sma50,
        "sma200": sma200,
        "price_above_sma200": (sma200 is not None and price > sma200),
        "crossover_signal": crossover,
    }


@tool(
    name="get_fundamentals",
    description="Valuation and company facts: P/E, market cap, sector, dividend yield, beta.",
    parameters={"ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL"}},
)
def get_fundamentals(ticker: str) -> dict:
    """Return key fundamentals from Yahoo Finance for ``ticker``."""
    try:
        info = data_layer.fetch_info(ticker)
    except DataError as exc:
        return {"ok": False, "ticker": ticker.upper(), "error": str(exc)}

    # Current yfinance (0.2.40+) returns dividendYield already as a percentage
    # number (e.g. 0.5 means 0.5%), so we report it as-is rather than scaling.
    div_yield = _round(info.get("dividendYield"))

    return {
        "ok": True,
        "ticker": ticker.upper(),
        "name": info.get("shortName") or info.get("longName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": _round(info.get("trailingPE")),
        "forward_pe": _round(info.get("forwardPE")),
        "dividend_yield_pct": div_yield,
        "beta": _round(info.get("beta")),
        "fifty_two_week_high": _round(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low": _round(info.get("fiftyTwoWeekLow")),
    }


@tool(
    name="compare_tickers",
    description="Side-by-side key metrics (price, P/E, market cap, RSI, trend) for 2+ tickers.",
    parameters={
        "tickers": {
            "type": "array",
            "description": "List of 2 or more stock symbols, e.g. ['AAPL', 'MSFT']",
        }
    },
)
def compare_tickers(tickers: list[str]) -> dict:
    """Return a comparison row for each ticker, reusing the other tools."""
    if not tickers or len(tickers) < 2:
        return {"ok": False, "error": "Provide at least two tickers to compare."}

    rows = []
    for tk in tickers:
        quote = get_quote(tk)
        fundamentals = get_fundamentals(tk)
        indicators = calculate_technical_indicators(tk)
        rows.append(
            {
                "ticker": tk.upper(),
                "price": quote.get("price") if quote.get("ok") else None,
                "change_pct": quote.get("change_pct") if quote.get("ok") else None,
                "trailing_pe": fundamentals.get("trailing_pe") if fundamentals.get("ok") else None,
                "market_cap": fundamentals.get("market_cap") if fundamentals.get("ok") else None,
                "dividend_yield_pct": fundamentals.get("dividend_yield_pct")
                if fundamentals.get("ok")
                else None,
                "rsi": indicators.get("rsi") if indicators.get("ok") else None,
                "crossover_signal": indicators.get("crossover_signal")
                if indicators.get("ok")
                else None,
                "error": None if quote.get("ok") else quote.get("error"),
            }
        )

    return {"ok": True, "tickers": [t.upper() for t in tickers], "rows": rows}


@tool(
    name="estimate_position_size",
    description="Risk-based position sizing from account size, risk %, entry and stop price.",
    parameters={
        "account_size": {"type": "number", "description": "Total account value, e.g. 10000"},
        "risk_pct": {"type": "number", "description": "Percent of account to risk, e.g. 2"},
        "entry": {"type": "number", "description": "Planned entry price per share"},
        "stop": {"type": "number", "description": "Stop-loss price per share"},
    },
)
def estimate_position_size(
    account_size: float, risk_pct: float, entry: float, stop: float
) -> dict:
    """Classic fixed-fractional position sizing.

    Risk amount = account_size * risk_pct%. Per-share risk = |entry - stop|.
    Shares = risk amount / per-share risk (rounded down to whole shares).
    """
    if entry <= 0 or account_size <= 0 or risk_pct <= 0:
        return {"ok": False, "error": "account_size, entry and risk_pct must be positive."}
    per_share_risk = abs(entry - stop)
    if per_share_risk == 0:
        return {"ok": False, "error": "Entry and stop cannot be equal (zero risk per share)."}

    risk_amount = account_size * (risk_pct / 100.0)
    shares = int(risk_amount // per_share_risk)
    position_value = round(shares * entry, 2)
    return {
        "ok": True,
        "account_size": account_size,
        "risk_pct": risk_pct,
        "entry": entry,
        "stop": stop,
        "risk_amount": round(risk_amount, 2),
        "per_share_risk": round(per_share_risk, 2),
        "shares": shares,
        "position_value": position_value,
        "position_pct_of_account": round(position_value / account_size * 100, 2),
    }
