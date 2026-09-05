"""Streamlit web app — the demo centerpiece.

The visual focus is the ReAct trace: each Thought, Action (tool + inputs) and
Observation is rendered as an expandable timeline, with the final recommendation
shown prominently. The sidebar lets you pick the engine and see the available
tools.

Designed to deploy cleanly on Streamlit Community Cloud:
* defaults to the ``rule`` engine (free, no key, no GPU),
* reads any API key from Streamlit secrets,
* never crashes when no keys are present (it falls back to ``rule``).

Run locally with:  ``streamlit run app.py``
"""

from __future__ import annotations

import json

import streamlit as st

from sage import config
from sage.agent import create_engine
from sage.data_layer import clear_cache
from sage.tools import TOOL_REGISTRY

st.set_page_config(page_title="Sage — Explainable Stock Advisor", page_icon="📈", layout="wide")


# --------------------------------------------------------------------------- #
# Sidebar: engine selection + tool catalogue
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("📈 Sage")
    st.caption("A transparent, tool-using ReAct investment advisor for stocks.")

    st.subheader("Reasoning engine")
    # Show availability so the choice is honest about what will actually run.
    ollama_ok = config.ollama_available()
    groq_ok = config.groq_available()
    claude_ok = config.claude_available()
    labels = {
        "rule": "rule — deterministic, free (default)",
        "ollama": f"ollama — local LLM {'✅' if ollama_ok else '✕ (not running)'}",
        "groq": f"groq — hosted open model {'✅' if groq_ok else '✕ (no key)'}",
        "claude": f"claude — Anthropic API {'✅' if claude_ok else '✕ (no key)'}",
    }
    chosen = st.radio(
        "Engine",
        options=list(config.ENGINES),
        format_func=lambda k: labels[k],
        index=0,
        label_visibility="collapsed",
    )

    max_steps = st.slider("Max reasoning steps", min_value=3, max_value=12, value=config.MAX_STEPS)

    if st.button("Clear data cache"):
        clear_cache()
        st.success("In-memory price/fundamentals cache cleared.")

    st.divider()
    st.subheader("Tool library")
    st.caption("The agent may call any of these:")
    for t in TOOL_REGISTRY.values():
        with st.expander(t.name):
            st.write(t.description)
            st.json(t.parameters)


# --------------------------------------------------------------------------- #
# Main panel: ask a question
# --------------------------------------------------------------------------- #
st.header("Ask an investment question")
st.caption(
    "Examples:  *“Should I buy NVIDIA right now?”*  ·  "
    "*“Compare AAPL and MSFT for a long-term hold.”*"
)

question = st.text_input(
    "Your question",
    value="Should I buy NVIDIA right now?",
    label_visibility="collapsed",
)
run = st.button("Analyse", type="primary")


def _render_observation(observation) -> None:
    """Render a tool observation, as a table for comparisons or JSON otherwise."""
    if isinstance(observation, dict) and observation.get("ok") and "rows" in observation:
        st.dataframe(observation["rows"], use_container_width=True)
    else:
        st.json(observation)


if run and question.strip():
    # Resolve the engine and warn if we had to fall back (keeps the demo honest).
    resolved = config.resolve_engine(chosen)
    if resolved != chosen:
        st.info(f"Engine **{chosen}** isn't available here — falling back to **{resolved}**.")

    with st.spinner(f"Reasoning with the **{resolved}** engine…"):
        try:
            result = create_engine(resolved, max_steps=max_steps).run(question)
        except Exception as exc:  # never crash the page
            st.error(f"Something went wrong: {exc}")
            st.stop()

    # ----- Final recommendation, shown prominently up top. -----
    if result.final:
        f = result.final
        # "PREFER X" and "TOO CLOSE TO CALL: ..." both fall through to the
        # neutral marker, which is the right reading for a comparison verdict.
        colour = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "TOO": "⚖️"}.get(
            f.recommendation.split()[0], "🔵"
        )
        st.subheader("Recommendation")
        c1, c2 = st.columns([1, 3])
        c1.metric(label="Verdict", value=f"{colour} {f.recommendation}")
        c2.metric(label="Confidence", value=f.confidence.capitalize())
        st.success(f.rationale)
    elif result.error:
        st.warning(result.error)

    # ----- The auditable ReAct trace — the visual centerpiece. -----
    st.subheader("Reasoning trace")
    st.caption(f"Engine: `{result.engine}` · {len(result.steps)} step(s)")
    for step in result.steps:
        action_label = f" → `{step.action.tool}`" if step.action else ""
        with st.expander(f"Step {step.index}{action_label}", expanded=True):
            st.markdown(f"**🟡 Thought**\n\n{step.thought}")
            if step.action:
                st.markdown(
                    f"**🟢 Action** — `{step.action.tool}`\n\n"
                    f"Inputs: `{json.dumps(step.action.tool_input)}`"
                )
            if step.observation is not None:
                st.markdown("**🔵 Observation**")
                _render_observation(step.observation)
            if step.note:
                st.markdown(f"**⚠️ Note** — {step.note}")

    with st.expander("Raw structured trace (JSON)"):
        st.json(result.to_dict())
