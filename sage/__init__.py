"""Sage — a transparent, tool-using ReAct investment advisor for retail stock investors.

The package is organised into small, single-purpose modules:

- ``config``      — engine selection, default tickers, and secret handling.
- ``data_layer``  — a thin, cached wrapper over ``yfinance`` with graceful errors.
- ``tools``       — the financial analysis tool library (a registry of pure functions).
- ``react``       — the shared data structures that describe a ReAct trace.
- ``agent``       — the three reasoning engines (rule / ollama / claude) behind one interface.
- ``display``     — helpers for rendering a trace in the CLI.

The headline feature is the *explainable ReAct loop*: every Thought, Action,
Observation and Final Answer is captured as structured data so the advice is
fully auditable rather than a black-box verdict.
"""

__version__ = "0.1.0"
