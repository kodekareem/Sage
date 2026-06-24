"""Command-line entry point for Sage.

Examples
--------
    python run.py ask "Should I buy NVDA right now?"
    python run.py ask "Compare AAPL and MSFT for a long-term hold" --engine rule
    python run.py tools          # list the available analysis tools

The CLI mirrors the Streamlit app and is handy for testing and for the demo if
the UI ever misbehaves.
"""

from __future__ import annotations

import argparse
import sys

from sage import config
from sage.agent import create_engine
from sage.display import render_trace
from sage.tools import TOOL_REGISTRY


def _cmd_ask(args: argparse.Namespace) -> int:
    # Resolve the requested engine, falling back to the always-available rule
    # engine if an LLM backend isn't reachable — and tell the user when we do.
    requested = args.engine
    resolved = config.resolve_engine(requested)
    if resolved != requested:
        print(
            f"[i] Engine '{requested}' is not available; falling back to '{resolved}'.\n",
            file=sys.stderr,
        )

    engine = create_engine(resolved, max_steps=args.max_steps)
    result = engine.run(args.question)
    render_trace(result)
    # Non-zero exit if we couldn't produce a recommendation, so scripts can tell.
    return 0 if result.final else 1


def _cmd_tools(_args: argparse.Namespace) -> int:
    print("Available analysis tools:\n")
    for t in TOOL_REGISTRY.values():
        params = ", ".join(t.parameters.keys())
        print(f"  {t.name}({params})\n      {t.description}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sage", description="Sage — explainable ReAct stock advisor")
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="Ask an investment question")
    ask.add_argument("question", help="Natural-language question, in quotes")
    ask.add_argument(
        "--engine",
        default="rule",
        choices=config.ENGINES,
        help="Reasoning engine (default: rule — free, no key, deploy-safe)",
    )
    ask.add_argument(
        "--max-steps",
        type=int,
        default=config.MAX_STEPS,
        help=f"Cap on reasoning steps (default: {config.MAX_STEPS})",
    )
    ask.set_defaults(func=_cmd_ask)

    tools = sub.add_parser("tools", help="List the available analysis tools")
    tools.set_defaults(func=_cmd_tools)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
