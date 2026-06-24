# Sage — a transparent, tool-using ReAct investment advisor for stocks

Sage is a single-agent conversational investment advisor for retail **stock**
investors. Its distinctive feature is a **transparent, tool-using ReAct
reasoning loop**: the agent answers an investment question by reasoning step by
step, calling a library of financial-analysis tools, observing the results, and
continuing until it can give a recommendation. **Every step of that reasoning —
the thought, the tool it chose, the inputs, and the observation — is surfaced to
the user**, so the advice is fully auditable rather than a black-box verdict.

> Academic feasibility prototype for CM3020 Artificial Intelligence
> (BSc Computer Science, University of London). The two core features being
> demonstrated are **(1) the explainable ReAct tool-calling loop** and
> **(2) the financial tool library** — not a memory/learning system.

---

## What it does

Ask a natural-language question such as:

- *“Should I buy NVIDIA right now?”* → a **buy / sell / hold** verdict
- *“Compare AAPL and MSFT for a long-term hold.”* → a **comparison verdict**

Sage runs an explicit loop and shows you the whole thing:

```
Thought      → what it needs to find out next
Action       → which tool it picked, and the inputs
Observation  → the structured result the tool returned
… repeat …
Final Answer → recommendation + confidence + plain-language rationale
```

---

## Architecture

```
sage/
  config.py        Engine selection, default tickers, secret handling
  data_layer.py    yfinance wrapper + in-memory cache + graceful errors
  tools.py         The 6-tool analysis library + a registry the agent is given
  react.py         The shared ReAct data structures (Step / Action / Trace / Result)
  agent.py         The three engines (rule / ollama / claude) behind one interface
  display.py       CLI rendering of a trace
app.py             Streamlit web app (the demo centerpiece)
run.py             CLI entry point
tests/             pytest suite (offline — synthetic data, no network)
```

### Component overview

| Component | What it does |
|---|---|
| **Data layer** (`data_layer.py`) | Pulls real OHLCV prices and fundamentals via `yfinance` (no API key). Caches per process; turns network/invalid-ticker failures into clear exceptions. |
| **Tool library** (`tools.py`) | Six clean tools, each a pure function returning a structured dict, held in a `TOOL_REGISTRY` with JSON-schema-style descriptions so adding a tool is trivial. |
| **ReAct agent** (`agent.py`) | One interface, three swappable engines, all emitting the **same** structured trace. |
| **Streamlit app** (`app.py`) | Chat-style input, expandable Thought/Action/Observation timeline, prominent final recommendation, engine + tool sidebar. |
| **CLI** (`run.py`) | `python run.py ask "..."` — same engine, for testing and the demo. |

### The tool library

| Tool | Purpose |
|---|---|
| `get_quote(ticker)` | Latest price and day change |
| `get_price_history(ticker, period)` | Summary of historical prices |
| `calculate_technical_indicators(ticker)` | RSI(14), SMA(50/200), MA-crossover signal (pure Python) |
| `get_fundamentals(ticker)` | P/E, market cap, sector, dividend yield, beta, 52-week range |
| `compare_tickers(tickers)` | Side-by-side key metrics for 2+ tickers |
| `estimate_position_size(account_size, risk_pct, entry, stop)` | Risk-based position sizing |

### The three engines (one interface)

All three produce the identical `ReActResult` shape, so the UI and report never
special-case an engine.

| Engine | Description | Needs |
|---|---|---|
| **`rule`** (default) | Deterministic, free, no-key. Scripts sensible thoughts, calls the **real** tools in a sensible order against **real** data, records every observation, and derives a transparent buy/sell/hold (or comparison) verdict via bull/bear point scoring. It genuinely walks the loop — it never shortcuts. This is what the deployed demo uses. | Nothing (only `yfinance` network) |
| **`ollama`** | A real **local** LLM via [Ollama](https://ollama.com) (e.g. `llama3.2`), prompted to emit Thought/Action/Action-Input that Sage parses and executes. For genuine LLM reasoning at no cost on a local machine. | Ollama running at `localhost:11434` |
| **`claude`** | The same hand-rolled loop backed by the Anthropic API. | `ANTHROPIC_API_KEY` |

The LLM loop is **hand-rolled** (no LangChain) — that's deliberate and keeps the
reasoning loop legible. It is capped at `MAX_STEPS` to prevent runaway cost and
infinite loops, and it handles malformed model output gracefully.

> **Engine selection:** if a requested LLM engine isn't available (no Ollama / no
> key), Sage automatically falls back to `rule`, so it always works out of the
> box and deploys cleanly to Streamlit Cloud.

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

### (Optional) enable the LLM engines

- **Ollama** (free, local): install Ollama, then `ollama pull llama3.2` and make
  sure `ollama serve` is running. Select the `ollama` engine.
- **Claude** (paid): set `ANTHROPIC_API_KEY` in your environment, or copy
  `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` for the app.

---

## Running it

### Streamlit web app (the demo)

```bash
streamlit run app.py
```

Pick the engine in the sidebar, type a question, and watch the expandable
Thought → Action → Observation timeline build, with the final recommendation up
top.

### Command line

```bash
# A single-stock buy/sell/hold:
python run.py ask "Should I buy NVDA right now?"

# A two-stock comparison:
python run.py ask "Compare AAPL and MSFT for a long-term hold" --engine rule

# List the available tools:
python run.py tools
```

`--engine` accepts `rule` (default), `ollama`, or `claude`. `--max-steps` caps
the reasoning loop.

---

## Tests

```bash
pytest
```

The suite runs **offline**: a fixture swaps the data layer for deterministic
synthetic prices, so no test touches the network. It covers:

- **Tool library** — each tool returns the correct structure on known input;
  indicator signals; position-sizing math; structured error handling.
- **LLM parser** — correctly parses Thought / Action / Action-Input and Final
  Answer (including JSON in code fences and free-text finals), and reports
  malformed output instead of crashing.
- **ReAct engine** — the rule engine produces a valid step-by-step trace and a
  sensible verdict; the LLM loop executes tools, **respects the step cap**, and
  recovers from malformed output.

---

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Create a new Streamlit app pointing at `app.py`.
3. Done — it runs on the `rule` engine with no secrets. (Optionally add
   `ANTHROPIC_API_KEY` in the app's Secrets to enable the `claude` engine; the
   `ollama` engine is local-only and won't run on the Cloud.)

---

## Honest evaluation — what's working, limited, and what I'd improve

**Working**
- The explainable ReAct loop and full structured trace work end-to-end across
  all three engines, with one shared data shape.
- The rule engine runs with zero keys and produces a genuine, inspectable,
  step-by-step trace from real market data — ideal for a reliable live demo.
- The tool library is clean, registry-driven, and easily extensible.
- Tests give real evidence: tools, parser, and engine loop (incl. step cap).

**Limited**
- The rule engine's verdict is a simple, transparent bull/bear point tally — it
  is explainable by design, not a sophisticated trading model.
- Indicators are a small classic set (RSI, SMA50/200); no MACD, Bollinger, etc.
- `yfinance` is an unofficial data source and can rate-limit or change shape;
  the live demo depends on it being up.
- LLM reasoning quality depends entirely on the chosen model; small local models
  can produce malformed steps (handled gracefully, but it shortens the trace).
- Not financial advice — no risk profiling, portfolio context, or backtesting.

**What I'd improve next**
- Add more indicators and a richer, weighted scoring model with backtest-derived
  weights.
- Cache to disk (with TTL) and add a resilient data-source fallback.
- Few-shot prompt the LLM engines and add self-correction to cut malformed steps.
- Evaluate trace quality systematically (e.g. an LLM-as-judge rubric over a fixed
  question set) and report agreement between the rule and LLM engines.
