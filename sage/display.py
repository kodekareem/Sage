"""Rendering helpers for the command-line interface.

The Streamlit app renders the same :class:`~sage.react.ReActResult` with its own
widgets; this module is only for the CLI. It uses ``rich`` when available for a
nicer demo, and degrades gracefully to plain ``print`` otherwise.
"""

from __future__ import annotations

import json

from .react import ReActResult

try:  # rich is optional — the CLI still works without it.
    from rich.console import Console
    from rich.panel import Panel

    _console = Console()
    _HAVE_RICH = True
except Exception:  # pragma: no cover - exercised only when rich is missing
    _console = None
    _HAVE_RICH = False


def _fmt_obs(observation) -> str:
    """Pretty-print an observation dict for the trace."""
    if observation is None:
        return "—"
    return json.dumps(observation, indent=2, default=str)


def render_trace(result: ReActResult) -> None:
    """Print the full ReAct trace and final recommendation to the terminal."""
    if _HAVE_RICH:
        _render_rich(result)
    else:
        _render_plain(result)


def _render_rich(result: ReActResult) -> None:
    _console.rule(f"[bold]Sage[/bold] — engine: [cyan]{result.engine}[/cyan]")
    _console.print(f"[bold]Question:[/bold] {result.question}\n")

    for step in result.steps:
        body = [f"[yellow]Thought:[/yellow] {step.thought}"]
        if step.action:
            body.append(
                f"[green]Action:[/green] {step.action.tool}"
                f"  [dim]input={json.dumps(step.action.tool_input)}[/dim]"
            )
        if step.observation is not None:
            body.append(f"[blue]Observation:[/blue]\n{_fmt_obs(step.observation)}")
        if step.note:
            body.append(f"[red]Note:[/red] {step.note}")
        _console.print(Panel("\n".join(body), title=f"Step {step.index}", border_style="dim"))

    if result.error:
        _console.print(Panel(result.error, title="Could not complete", border_style="red"))
        return

    if result.final:
        f = result.final
        _console.print(
            Panel(
                f"[bold]{f.recommendation}[/bold]   "
                f"(confidence: [magenta]{f.confidence}[/magenta])\n\n{f.rationale}",
                title="Final recommendation",
                border_style="bold green",
            )
        )


def _render_plain(result: ReActResult) -> None:  # pragma: no cover - simple I/O
    print("=" * 70)
    print(f"Sage — engine: {result.engine}")
    print(f"Question: {result.question}")
    print("=" * 70)
    for step in result.steps:
        print(f"\n--- Step {step.index} ---")
        print(f"Thought: {step.thought}")
        if step.action:
            print(f"Action: {step.action.tool}  input={json.dumps(step.action.tool_input)}")
        if step.observation is not None:
            print(f"Observation:\n{_fmt_obs(step.observation)}")
        if step.note:
            print(f"Note: {step.note}")
    print()
    if result.error:
        print(f"[!] Could not complete: {result.error}")
        return
    if result.final:
        f = result.final
        print("=" * 70)
        print(f"FINAL RECOMMENDATION: {f.recommendation}  (confidence: {f.confidence})")
        print(f.rationale)
        print("=" * 70)
