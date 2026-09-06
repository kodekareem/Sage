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
  (or an explicit *“too close to call”* when the evidence genuinely ties)
- *“I have $10,000, risking 2% on AAPL at 150 with a stop at 140 — how many
  shares?”* → a **risk-based position size**

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
  agent.py         The four engines (rule / ollama / openai / claude) behind one interface
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
| **ReAct agent** (`agent.py`) | One interface, four swappable engines, all emitting the **same** structured trace. |
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

### The four engines (one interface)

All four produce the identical `ReActResult` shape, so the UI and report never
special-case an engine.

| Engine | Description | Needs |
|---|---|---|
| **`rule`** (default) | Deterministic, free, no-key. Scripts sensible thoughts, calls the **real** tools in a sensible order against **real** data, records every observation, and derives a transparent buy/sell/hold (or comparison) verdict via bull/bear point scoring. Ties are reported as ties rather than broken arbitrarily. It genuinely walks the loop — it never shortcuts. This is the default, and the only engine that needs nothing at all. | Nothing (only `yfinance` network) |
| **`ollama`** | A real **local** LLM via [Ollama](https://ollama.com) (e.g. `llama3.2`), prompted to emit Thought/Action/Action-Input that Sage parses and executes. For genuine LLM reasoning at no cost on a local machine. | Ollama running at `localhost:11434` |
| **`openai`** | Any provider speaking the OpenAI chat-completions protocol — OpenRouter, Groq, Together, a local vLLM server. Defaults to OpenRouter with `minimax/minimax-m3:free`, which is what the reported evaluation used. Rate limits are retried with backoff. | `OPENAI_COMPAT_API_KEY` ([free](https://openrouter.ai)) |
| **`claude`** | The same hand-rolled loop backed by the Anthropic API. | `ANTHROPIC_API_KEY` |

The LLM loop is **hand-rolled** (no LangChain) — that's deliberate and keeps the
reasoning loop legible. It is capped at `MAX_STEPS` to prevent runaway cost and
infinite loops, and it handles malformed model output gracefully.

**Rate limits.** Free-tier providers cap throughput, and a ReAct loop resends the
whole conversation each turn, so a long trace can trip a cap part-way through.
A refused call (HTTP 429) is retried with exponential backoff — honouring the
provider's own `retry-after` when it sends one, with a floor so a near-zero
reset window can't cause a retry storm, and a cap so an absurd one can't stall
the run. If the limit still holds after retrying, Sage says so explicitly:
a throughput cap is reported as a throughput cap, never as a bad key, because
those need opposite responses from the user.

> Free tiers also cap *output* tokens per minute (Groq's is 1000 on some
> models), so `OPENAI_COMPAT_MAX_TOKENS` defaults to 800. Asking for more than
> the cap is refused on every request no matter how long you wait — a limit no
> retry can solve, and one worth knowing before a live demo.

> **Engine selection:** if a requested LLM engine isn't available (no Ollama, no
> key), Sage automatically falls back to `rule`, so it always works out of the
> box and deploys cleanly to Streamlit Cloud. This is verified by
> `scripts/verify_no_key_fallback.py`, which runs Sage with every credential
> stripped from the environment.

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

- **A hosted model** (free, easiest): get a key at
  [openrouter.ai](https://openrouter.ai), then
  `export OPENAI_COMPAT_API_KEY=...` (PowerShell: `$env:OPENAI_COMPAT_API_KEY="..."`).
  Select the `openai` engine. Point it at another provider with
  `OPENAI_COMPAT_URL` and `OPENAI_COMPAT_MODEL`. The older `GROQ_*` names are
  still read, so an existing setup keeps working.
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

`--engine` accepts `rule` (default), `ollama`, `openai`, or `claude`. `--max-steps` caps
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
- **Rate limiting** (`tests/test_rate_limit.py`) — a 429 is retried with
  exponential backoff and the run recovers; the provider's `retry-after` is
  honoured within a floor and a cap; a persistent limit is reported as a
  throughput cap rather than a bad key; and a genuine auth failure is *not*
  retried, since waiting would never fix it.
- **ReAct engine** — the rule engine produces a valid step-by-step trace and a
  sensible verdict; comparison verdicts are order-independent and declare ties
  honestly; position sizing handles labelled inputs and impossible trades; the
  LLM loop executes tools, **respects the step cap**, and recovers from
  malformed output.
- **LLM network path** (`tests/test_llm_http.py`) — the Ollama engine is driven
  against a real local HTTP server speaking Ollama's `/api/chat` protocol, so
  sockets, JSON and the parser are exercised, not just the loop's control flow.

### Verification scripts

Beyond `pytest`, `scripts/` holds checks that verify behaviour directly:

| Script | What it proves |
|---|---|
| `verify_ties.py` | Tied comparisons are declared, order-independent, and a real winner is still picked |
| `verify_encoding.py` | The CLI keeps its non-ASCII characters on a legacy cp1252 Windows console |
| `verify_tool_coverage.py` | Every registered tool is genuinely reachable by the engine |
| `verify_live.py` | Against **live** market data, every figure cited in the rationale traces back to a recorded observation |
| `verify_llm_engine.py` | The ReAct loop against a **real** served model — `--engine openai` (or `ollama`/`claude`); fails loudly rather than skipping when no backend is reachable |
| `verify_no_secrets.py` | No API key or credential is committed to the repo |
| `verify_no_key_fallback.py` | The app still works with every key stripped, as the deployed demo does |
| `verify_rate_limit_reporting.py` | A rate limit is reported as a rate limit and a bad key as a bad key (both directions checked) |

---

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Create a new Streamlit app pointing at `app.py`.
3. Done — with no secrets it runs on the `rule` engine, and the sidebar offers
   only that engine. (Optionally add
   `OPENAI_COMPAT_API_KEY` or `ANTHROPIC_API_KEY` in the app's Secrets to enable a real
   LLM engine; the `ollama` engine is local-only and won't run on the Cloud.)

---

## Honest evaluation — what's working, limited, and what I'd improve

**Working**
- The explainable ReAct loop and full structured trace share one data shape
  across all four engines, so the UI and tests never special-case an engine.
- The rule engine runs with zero keys and produces a genuine, inspectable,
  step-by-step trace from real market data — ideal for a reliable live demo. It
  is verified against **live** data, including that every figure quoted in a
  recommendation traces back to a recorded observation (`verify_live.py`).
- The tool library is clean, registry-driven, and easily extensible, and all
  six tools are genuinely reachable by the agent (`verify_tool_coverage.py`).
- Tests give real evidence: tools, parser, and engine loop (incl. step cap),
  plus the LLM engine's real HTTP path against a local model server.

**Verified to different depths — an honest distinction**
- The **`rule`** engine is verified end-to-end against live market data.
- The **LLM loop** is verified three ways: control flow (unit tests), its real
  network path against a local HTTP server (sockets, JSON, malformed-output
  recovery), and **end-to-end against a real served model** via OpenRouter
  (`python scripts/verify_llm_engine.py --engine openai`), where a live model
  chose tools, read real market data, recovered from a tool error, and produced
  a grounded verdict.
- What is still **not** measured is LLM reasoning *quality at scale*: there is
  no rubric-scored question set and no rule-vs-LLM agreement study. That is the
  main thing a fuller evaluation would add.

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
