"""Shared data structures for the ReAct reasoning trace.

These types are the contract between the *engines* (``agent.py``) and the
*presentation layer* (``display.py`` / the Streamlit app). All three engines —
``rule``, ``ollama`` and ``claude`` — must produce the SAME ``ReActResult``
shape, so the UI and the report never need to special-case an engine.

A run is a list of :class:`ReActStep` objects followed by a :class:`FinalAnswer`.
Each step records:

    Thought      — why the agent is doing what it does next (plain language)
    Action       — which tool it chose and the arguments it passed
    Observation  — the structured result the tool returned

This makes the whole reasoning process inspectable, which is the core feature
being demonstrated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Action:
    """A tool call chosen by the agent."""

    tool: str
    tool_input: dict

    def to_dict(self) -> dict:
        return {"tool": self.tool, "tool_input": self.tool_input}


@dataclass
class ReActStep:
    """One Thought -> Action -> Observation cycle of the loop."""

    index: int
    thought: str
    action: Optional[Action] = None
    observation: Optional[Any] = None
    # Free-text note used to record problems (e.g. malformed LLM output) so the
    # trace stays honest about what happened.
    note: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "thought": self.thought,
            "action": self.action.to_dict() if self.action else None,
            "observation": self.observation,
            "note": self.note,
        }


@dataclass
class FinalAnswer:
    """The agent's recommendation, with a confidence level and a rationale."""

    recommendation: str  # e.g. "BUY", "HOLD", "SELL", or a comparison verdict
    confidence: str      # "low" | "medium" | "high"
    rationale: str

    def to_dict(self) -> dict:
        return {
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


@dataclass
class ReActResult:
    """The complete, auditable output of a single agent run."""

    question: str
    engine: str
    steps: list[ReActStep] = field(default_factory=list)
    final: Optional[FinalAnswer] = None
    # Populated when the run could not complete (e.g. no tickers found, or the
    # LLM produced unusable output repeatedly).
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "engine": self.engine,
            "steps": [s.to_dict() for s in self.steps],
            "final": self.final.to_dict() if self.final else None,
            "error": self.error,
        }
