"""Verify every registered tool is actually reachable by the rule engine.

The audit found that six tools were registered and advertised in the UI, but the
rule engine only ever called four: ``get_price_history`` and
``estimate_position_size`` were unreachable under the default engine. A marker
asking "does the agent use its tool library?" would find two tools decorative.

This script proves reachability by *observation, not inspection*: it runs real
questions through the engine with the data layer stubbed, and records which
tools the engine actually invoked, by wrapping ``run_tool`` at the module the
engine calls it through. A tool only counts as covered when a real run called it.

Exits non-zero if any registered tool is never invoked across the question set.
"""

from __future__ import annotations

import sys

import pandas as pd

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sage import agent as agent_module
from sage import data_layer
from sage.tools import TOOL_REGISTRY

# ---------------------------------------------------------------------------
# Offline stub data, so this check never depends on the network.
# ---------------------------------------------------------------------------
_DATES = pd.date_range(end="2024-12-31", periods=260, freq="B")
_CLOSES = [100 + i * 0.4 + (3.0 if i % 7 == 0 else 0.0) for i in range(260)]
_FRAME = pd.DataFrame(
    {
        "Open": _CLOSES,
        "High": [c + 1 for c in _CLOSES],
        "Low": [c - 1 for c in _CLOSES],
        "Close": _CLOSES,
        "Volume": [1_000_000] * 260,
    },
    index=_DATES,
)

_INFO = {
    "shortName": "Test Corp.",
    "sector": "Technology",
    "industry": "Software",
    "marketCap": 1_000_000_000_000,
    "trailingPE": 22.0,
    "forwardPE": 20.0,
    "dividendYield": 0.5,
    "beta": 1.1,
    "fiftyTwoWeekHigh": 220,
    "fiftyTwoWeekLow": 90,
}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    data_layer.fetch_history = lambda ticker, period="1y": _FRAME  # type: ignore[assignment]
    data_layer.fetch_info = lambda ticker: dict(_INFO)  # type: ignore[assignment]
    data_layer.clear_cache()

    called: list[str] = []
    real_run_tool = agent_module.run_tool

    def recording_run_tool(name: str, tool_input: dict) -> dict:
        called.append(name)
        return real_run_tool(name, tool_input)

    # The engine calls run_tool through its own module namespace.
    agent_module.run_tool = recording_run_tool  # type: ignore[assignment]

    # Questions chosen to exercise the engine's distinct reasoning paths.
    questions = [
        "Should I buy NVDA right now?",
        "Compare AAPL and MSFT for a long-term hold",
        "I have a $10000 account, risk 2% buying AAPL at 150 with a stop at 140. "
        "How many shares should I take?",
        "How has NVDA performed over the last 6 months?",
    ]

    for question in questions:
        result = agent_module.RuleEngine().run(question)
        if result.error:
            fail(f"question failed outright: {question!r} -> {result.error}")
        if not result.steps:
            fail(f"question produced no reasoning steps: {question!r}")
        # Every executed step must carry the observation it claims to have made,
        # otherwise "reachable" would not mean "actually used in the trace".
        for step in result.steps:
            if step.action is not None and step.observation is None:
                fail(f"step {step.index} of {question!r} recorded no observation")

    registered = set(TOOL_REGISTRY)
    invoked = set(called)

    unknown = invoked - registered
    if unknown:
        fail(f"engine invoked unregistered tools: {sorted(unknown)}")

    unreachable = registered - invoked
    if unreachable:
        fail(
            "these registered tools are never reachable by the rule engine: "
            f"{sorted(unreachable)}"
        )

    if len(registered) < 6:
        fail(f"expected at least 6 registered tools, found {len(registered)}")

    print(f"registered tools: {len(registered)}")
    for name in sorted(registered):
        print(f"  invoked: {name} x{called.count(name)}")
    print("TOOL COVERAGE VERIFICATION PASSED")


if __name__ == "__main__":
    main()
