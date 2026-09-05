"""Integration tests for the LLM engine's real network path.

The tests in ``test_agent.py`` drive the ReAct loop through a subclass whose
``complete()`` returns canned strings. That proves the loop's control flow, but
it bypasses everything between the loop and a model: the HTTP request, the JSON
envelope, and the parser meeting text that arrives over a socket.

These tests close that gap by running ``OllamaEngine`` against a real local HTTP
server that speaks Ollama's ``/api/chat`` protocol. Sockets, HTTP, JSON encoding
and the parser are all genuinely exercised.

What this is not
----------------
This is **not** a substitute for running against a real language model. The
served replies are fixed, so no model intelligence is under test. Verifying the
loop against an actual served model is done by
``scripts/verify_llm_engine.py``, which requires Ollama or an API key and fails
loudly when neither is present. The distinction is deliberate: these tests prove
the plumbing, that script proves the claim.
"""

from __future__ import annotations

import pandas as pd
import pytest

from sage import data_layer
from sage.agent import OllamaEngine

from .mock_model_server import serve

PORT = 11598


@pytest.fixture
def model_server():
    """Run the mock model server for the duration of a test."""
    from . import mock_model_server

    mock_model_server.Handler.index = 0  # replies are served in order
    server = serve(PORT)
    yield f"http://127.0.0.1:{PORT}"
    server.shutdown()


@pytest.fixture
def stub_prices(monkeypatch):
    """Keep the tools offline so only the LLM path is under test."""
    dates = pd.date_range(end="2024-12-31", periods=260, freq="B")
    closes = [100 + i * 0.4 for i in range(260)]
    frame = pd.DataFrame(
        {
            "Open": closes,
            "High": [c + 1 for c in closes],
            "Low": [c - 1 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * 260,
        },
        index=dates,
    )
    monkeypatch.setattr(data_layer, "fetch_history", lambda t, period="1y": frame)
    monkeypatch.setattr(
        data_layer,
        "fetch_info",
        lambda t: {"shortName": "X", "sector": "Tech", "marketCap": 1, "trailingPE": 20.0},
    )
    data_layer.clear_cache()


def test_llm_loop_over_real_http(model_server, stub_prices):
    """The loop completes against a served endpoint, over real sockets."""
    engine = OllamaEngine(model="mock-model", url=model_server)
    result = engine.run("Should I buy NVDA right now?")

    assert result.error is None
    assert result.final is not None
    assert result.final.recommendation == "BUY"
    assert result.final.confidence == "medium"
    assert result.final.rationale.strip()


def test_llm_loop_executes_tools_over_http(model_server, stub_prices):
    """Tool calls parsed from served text are actually executed with observations."""
    engine = OllamaEngine(model="mock-model", url=model_server)
    result = engine.run("Should I buy NVDA right now?")

    tool_steps = [s for s in result.steps if s.action is not None]
    assert [s.action.tool for s in tool_steps] == [
        "get_quote",
        "calculate_technical_indicators",
    ]
    for step in tool_steps:
        assert step.observation is not None
        assert step.observation["ok"] is True


def test_llm_loop_recovers_from_malformed_output_over_http(model_server, stub_prices):
    """A malformed turn is recorded honestly and the run still completes.

    The mock server's second reply is unparseable prose, mimicking what a small
    local model does in practice. The trace must say so rather than hide it.
    """
    engine = OllamaEngine(model="mock-model", url=model_server)
    result = engine.run("Should I buy NVDA right now?")

    noted = [s for s in result.steps if s.note]
    assert noted, "the malformed turn was not recorded in the trace"
    assert "malformed" in noted[0].note.lower()
    # Despite the bad turn, the run still reached a conclusion.
    assert result.final is not None


def test_llm_engine_reports_a_dead_server(stub_prices):
    """An unreachable model server fails cleanly instead of raising."""
    engine = OllamaEngine(model="mock-model", url="http://127.0.0.1:1")
    result = engine.run("Should I buy NVDA right now?")

    assert result.final is None
    assert result.error is not None
    assert "LLM call failed" in result.error
