"""Evaluation harness: score Sage's reasoning traces over a fixed question set.

A passing unit-test suite shows the code does what it was built to do. It says
nothing about whether the *reasoning* is any good, which is the thing this
project actually claims. This harness measures that, over a fixed set of
questions, with rules stated up front so the scoring can be checked rather than
taken on trust.

Four measures, each chosen because it tests a specific claim the project makes:

1. Trace validity — does every step carry a thought, and does every action carry
   the observation it claims to have made? A trace with gaps is not auditable,
   which is the whole premise.

2. Groundedness — does every number quoted in the final rationale appear in a
   recorded observation? This is the anti-hallucination claim. A figure in the
   verdict that appears nowhere in the evidence is a fabrication, and finance is
   exactly where that matters.

3. Tool appropriateness — did the run call the tools the question needs? A
   comparison that never compares, or a sizing question that never sizes, has
   not reasoned about what was asked.

4. Engine agreement — do the rule engine and the LLM engine reach the same
   verdict on the same evidence? Neither is ground truth (there is no oracle for
   "should I buy NVDA"), so this measures consistency, not correctness, and the
   report says so.

Run offline (deterministic synthetic data, no network, no key) for a repeatable
result, or live to measure against real market data and a real model:

    python scripts/run_evaluation.py --offline --out report/data
    python scripts/run_evaluation.py --live --engine groq --out report/data
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402

from sage import config, data_layer  # noqa: E402
from sage.agent import RuleEngine, create_engine  # noqa: E402

# --------------------------------------------------------------------------- #
# The question set.
#
# Fixed in advance and kept small enough to inspect by hand. Each question
# carries the tools a competent answer needs, so "did it use the right tools"
# is decided by a rule written before the run rather than by reading the output
# afterwards and deciding it looks reasonable.
# --------------------------------------------------------------------------- #
QUESTIONS: list[dict] = [
    # --- single-stock judgements -----------------------------------------
    {"id": "S1", "q": "Should I buy NVDA right now?",
     "kind": "single", "needs": {"get_quote"}},
    {"id": "S2", "q": "Is AAPL a good buy today?",
     "kind": "single", "needs": {"get_quote"}},
    {"id": "S3", "q": "Should I sell my TSLA shares?",
     "kind": "single", "needs": {"get_quote"}},
    {"id": "S4", "q": "What do you think about MSFT as an investment?",
     "kind": "single", "needs": {"get_quote"}},
    {"id": "S5", "q": "Should I buy NVIDIA right now?",   # company name, not ticker
     "kind": "single", "needs": {"get_quote"}},
    {"id": "S6", "q": "Is Apple overvalued at the moment?",
     "kind": "single", "needs": {"get_quote"}},
    # --- comparisons ------------------------------------------------------
    {"id": "C1", "q": "Compare AAPL and MSFT for a long-term hold",
     "kind": "compare", "needs": {"compare_tickers"}},
    {"id": "C2", "q": "AAPL vs TSLA, which is the better buy?",
     "kind": "compare", "needs": {"compare_tickers"}},
    {"id": "C3", "q": "Which is stronger right now, NVDA or AMD?",
     "kind": "compare", "needs": {"compare_tickers"}},
    {"id": "C4", "q": "Compare Microsoft and Tesla as investments",
     "kind": "compare", "needs": {"compare_tickers"}},
    # --- position sizing --------------------------------------------------
    {"id": "P1", "q": "I have a $10000 account, risk 2% buying AAPL at 150 "
                      "with a stop at 140. How many shares should I take?",
     "kind": "size", "needs": {"estimate_position_size"}},
    {"id": "P2", "q": "With $5000 and 1% risk on MSFT at 100, stop at 95, "
                      "how many shares?",
     "kind": "size", "needs": {"estimate_position_size"}},
    # --- questions that SHOULD be refused, not answered -------------------
    # A system that answers these is guessing. Refusing is the correct result,
    # so these are scored on whether the refusal happens.
    {"id": "R1", "q": "What is a good investment strategy?",
     "kind": "refuse", "needs": set()},
    {"id": "R2", "q": "Is the market going up tomorrow?",
     "kind": "refuse", "needs": set()},
    {"id": "R3", "q": "Should I buy ZZZQQ right now?",   # invalid ticker
     "kind": "refuse_or_error", "needs": set()},
]


# --------------------------------------------------------------------------- #
# Offline fixtures — deterministic, so the reported numbers are reproducible.
# --------------------------------------------------------------------------- #
def _series(n: int, start: float, end: float, amp: float = 3.0) -> pd.DataFrame:
    import math
    dates = pd.date_range(end="2024-12-31", periods=n, freq="B")
    closes = [
        round(start + (end - start) * (i / (n - 1)) + amp * math.sin(i / 4.0), 2)
        for i in range(n)
    ]
    close = pd.Series(closes, index=dates)
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1,
         "Close": close, "Volume": [1_000_000] * n},
        index=dates,
    )


_HISTORIES = {
    "AAPL": _series(260, 100, 200),   # strong uptrend
    "MSFT": _series(260, 100, 120),   # mild uptrend
    "TSLA": _series(260, 200, 100),   # downtrend
    "NVDA": _series(260, 80, 220),    # strong uptrend
    "AMD":  _series(260, 120, 110),   # roughly flat
}

_INFOS = {
    "AAPL": {"shortName": "Apple Inc.", "sector": "Technology", "marketCap": 3e12,
             "trailingPE": 28.0, "forwardPE": 26.0, "dividendYield": 0.5, "beta": 1.2,
             "fiftyTwoWeekHigh": 210, "fiftyTwoWeekLow": 90},
    "MSFT": {"shortName": "Microsoft Corp.", "sector": "Technology", "marketCap": 2.5e12,
             "trailingPE": 35.0, "forwardPE": 30.0, "dividendYield": 0.8, "beta": 0.9,
             "fiftyTwoWeekHigh": 130, "fiftyTwoWeekLow": 95},
    "TSLA": {"shortName": "Tesla Inc.", "sector": "Consumer Cyclical", "marketCap": 7e11,
             "trailingPE": 60.0, "forwardPE": 50.0, "dividendYield": None, "beta": 2.0,
             "fiftyTwoWeekHigh": 210, "fiftyTwoWeekLow": 95},
    "NVDA": {"shortName": "NVIDIA Corp.", "sector": "Technology", "marketCap": 2e12,
             "trailingPE": 45.0, "forwardPE": 35.0, "dividendYield": 0.0003, "beta": 1.7,
             "fiftyTwoWeekHigh": 230, "fiftyTwoWeekLow": 70},
    "AMD":  {"shortName": "AMD Inc.", "sector": "Technology", "marketCap": 3e11,
             "trailingPE": 22.0, "forwardPE": 20.0, "dividendYield": None, "beta": 1.8,
             "fiftyTwoWeekHigh": 140, "fiftyTwoWeekLow": 95},
}


def install_offline_data() -> None:
    """Point the data layer at the fixtures above."""
    def fetch_history(ticker: str, period: str = "1y") -> pd.DataFrame:
        frame = _HISTORIES.get(ticker.upper())
        if frame is None:
            raise data_layer.InvalidTickerError(f"No data for {ticker!r}.")
        return frame

    def fetch_info(ticker: str) -> dict:
        info = _INFOS.get(ticker.upper())
        if info is None:
            raise data_layer.InvalidTickerError(f"No fundamentals for {ticker!r}.")
        return dict(info)

    data_layer.fetch_history = fetch_history      # type: ignore[assignment]
    data_layer.fetch_info = fetch_info            # type: ignore[assignment]
    data_layer.clear_cache()


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def numbers_in(text: str) -> set[float]:
    """Numeric values in ``text``, compared by value rather than by spelling.

    The tool layer records 10000.0 while the rationale writes 10000; both are
    the same reading. Comparing the strings would score that as a fabricated
    figure, so the comparison is done on the parsed value instead.
    """
    values: set[float] = set()
    for raw in re.findall(r"-?\d+(?:\.\d+)?", text or ""):
        try:
            values.add(float(raw))
        except ValueError:
            continue
    return values


#: Phrases whose numbers name an indicator or a textbook threshold rather than
#: report a reading. "The 200-day SMA" is the indicator's name; "RSI below 70"
#: is the standard overbought line. Neither is a figure fetched from a tool, so
#: neither can be ungrounded, and counting them would score correct financial
#: writing as fabrication. Removed before the figures are extracted.
#
# Every alternative below must consume a WHOLE number. An earlier version used
# ``rsi\s*\(?\s*\d{1,3}`` which chewed the "93" out of "RSI 93.93" and left
# ".93" behind, inventing figures that matched nothing and scoring correct
# output as fabricated. Each numeric run is therefore anchored with a trailing
# (?!\.?\d) so a decimal reading is never partially eaten.
_DOMAIN_VOCABULARY = re.compile(
    r"""
      \b\d{1,3}(?!\.?\d)\s*[-\s]?day\b              # 50-day, 200 day
    | \bsma\s*\(\s*\d{1,3}(?!\.?\d)\s*\)            # SMA(200)
    | \bsma\s*\d{1,3}(?!\.?\d)\b                    # SMA50
    | \brsi\s*\(\s*\d{1,3}(?!\.?\d)\s*\)            # RSI(14)
    | \b(?:above|below|under|over)\s+(?:30|70)(?!\.?\d)\b   # RSI thresholds
    | \b(?:30|70)(?!\.?\d)\s+(?:threshold|level|line)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def strip_domain_vocabulary(text: str) -> str:
    """Remove indicator names and standard thresholds before scoring figures."""
    return _DOMAIN_VOCABULARY.sub(" ", text or "")


def score_run(item: dict, result) -> dict:
    """Score one run against the four measures. Returns a plain dict."""
    tools_called = [s.action.tool for s in result.steps if s.action]
    expects_refusal = item["kind"] in ("refuse", "refuse_or_error")

    # --- Trace validity ---------------------------------------------------
    # Every step needs a thought; every action needs its observation.
    trace_problems: list[str] = []
    for step in result.steps:
        if not (step.thought or "").strip():
            trace_problems.append(f"step {step.index} has no thought")
        if step.action is not None and step.observation is None:
            trace_problems.append(f"step {step.index} recorded no observation")
    trace_valid = not trace_problems

    # --- Groundedness -----------------------------------------------------
    # Every multi-digit figure in the rationale must appear in an observation.
    # Single digits are excluded: they are almost always the bull/bear tally or
    # a step count, which are derived rather than read from a tool.
    grounded = None
    ungrounded: list[str] = []
    if result.final is not None:
        observed = numbers_in(
            json.dumps([s.observation for s in result.steps], default=str)
        )
        cited = {
            v for v in numbers_in(strip_domain_vocabulary(result.final.rationale))
            # Values under 10 are excluded: those are the bull/bear tallies and
            # step counts, which the engine derives rather than reads.
            if abs(v) >= 10
        }
        # Compare magnitudes, and round: the observation holds -48.59 while the
        # rationale writes "down 48.59%", carrying the sign in the word rather
        # than the digits. That is correct prose, not an invented figure, so
        # matching on the signed value would score good output as fabricated.
        observed_mag = {round(abs(v), 4) for v in observed}
        ungrounded = sorted(
            str(v) for v in cited if round(abs(v), 4) not in observed_mag
        )
        grounded = not ungrounded

    # --- Tool appropriateness --------------------------------------------
    missing = sorted(item["needs"] - set(tools_called))
    tools_ok = not missing

    # --- Did it behave as the question required? --------------------------
    if expects_refusal:
        # Correct behaviour is no recommendation: either a refusal or a
        # reported data error. Answering anyway is the failure.
        answered_correctly = result.final is None and result.error is not None
    else:
        answered_correctly = result.final is not None and result.error is None

    return {
        "id": item["id"],
        "question": item["q"],
        "kind": item["kind"],
        "engine": result.engine,
        "steps": len(result.steps),
        "tools_called": tools_called,
        "trace_valid": trace_valid,
        "trace_problems": trace_problems,
        "grounded": grounded,
        "ungrounded_figures": ungrounded,
        "tools_appropriate": tools_ok,
        "missing_tools": missing,
        "answered_correctly": answered_correctly,
        "verdict": result.final.recommendation if result.final else None,
        "confidence": result.final.confidence if result.final else None,
        # Kept so an ungrounded figure can be inspected in context rather than
        # taken on the scorer's word. Any groundedness number quoted in the
        # report has to be checkable against the text that produced it.
        "rationale": result.final.rationale if result.final else None,
        "error": result.error,
    }


def verdict_family(verdict: str | None) -> str | None:
    """Reduce a verdict to a comparable class.

    Two engines phrase themselves differently ("PREFER AAPL" vs "BUY AAPL"), so
    agreement is measured on the decision, not the wording.
    """
    if not verdict:
        return None
    v = verdict.strip().upper()
    if v.startswith("TOO CLOSE"):
        return "TIE"
    for word in ("BUY", "SELL", "HOLD"):
        if v.startswith(word):
            # "BUY MSFT" in a comparison is a preference, not a single-stock buy.
            rest = v[len(word):].strip()
            return f"PREFER:{rest}" if rest else word
    if v.startswith("PREFER"):
        return f"PREFER:{v[len('PREFER'):].strip()}"
    if re.match(r"^\d+\s+SHARES?", v):
        return "SIZE"
    return v


def summarise(rows: list[dict]) -> dict:
    """Aggregate per-question rows into the figures the report quotes."""
    scored = [r for r in rows if r["kind"] not in ("refuse", "refuse_or_error")]
    refusals = [r for r in rows if r["kind"] in ("refuse", "refuse_or_error")]
    with_final = [r for r in scored if r["verdict"] is not None]
    grounded_rows = [r for r in with_final if r["grounded"] is not None]

    def pct(n: int, d: int) -> float:
        return round(100.0 * n / d, 1) if d else 0.0

    trace_ok = sum(1 for r in rows if r["trace_valid"])
    grounded_ok = sum(1 for r in grounded_rows if r["grounded"])
    tools_ok = sum(1 for r in scored if r["tools_appropriate"])
    answered_ok = sum(1 for r in rows if r["answered_correctly"])
    steps = [r["steps"] for r in scored if r["steps"]]

    return {
        "questions": len(rows),
        "answerable": len(scored),
        "refusal_cases": len(refusals),
        "trace_valid": trace_ok,
        "trace_valid_pct": pct(trace_ok, len(rows)),
        "grounded": grounded_ok,
        "grounded_of": len(grounded_rows),
        "grounded_pct": pct(grounded_ok, len(grounded_rows)),
        "tools_appropriate": tools_ok,
        "tools_appropriate_pct": pct(tools_ok, len(scored)),
        "answered_correctly": answered_ok,
        "answered_correctly_pct": pct(answered_ok, len(rows)),
        "mean_steps": round(statistics.mean(steps), 2) if steps else 0.0,
    }


def compare_engines(rule_rows: list[dict], llm_rows: list[dict]) -> dict:
    """Measure how often two engines reach the same decision."""
    by_id = {r["id"]: r for r in llm_rows}
    compared, agreed, disagreements = 0, 0, []

    for row in rule_rows:
        other = by_id.get(row["id"])
        if other is None:
            continue
        a, b = verdict_family(row["verdict"]), verdict_family(other["verdict"])
        if a is None or b is None:
            continue
        compared += 1
        if a == b:
            agreed += 1
        else:
            disagreements.append(
                {"id": row["id"], "question": row["question"], "rule": a, "llm": b}
            )

    return {
        "compared": compared,
        "agreed": agreed,
        "agreement_pct": round(100.0 * agreed / compared, 1) if compared else 0.0,
        "disagreements": disagreements,
    }


# --------------------------------------------------------------------------- #
def run_engine(engine_name: str, max_steps: int) -> list[dict]:
    rows = []
    for item in QUESTIONS:
        engine = create_engine(engine_name, max_steps=max_steps) \
            if engine_name != "rule" else RuleEngine()
        try:
            result = engine.run(item["q"])
        except Exception as exc:  # a crash is a result worth recording
            print(f"  {item['id']}: CRASHED {type(exc).__name__}: {exc}")
            rows.append({
                "id": item["id"], "question": item["q"], "kind": item["kind"],
                "engine": engine_name, "steps": 0, "tools_called": [],
                "trace_valid": False, "trace_problems": [f"crashed: {exc}"],
                "grounded": None, "ungrounded_figures": [],
                "tools_appropriate": False, "missing_tools": sorted(item["needs"]),
                "answered_correctly": False, "verdict": None, "confidence": None,
                "error": f"crashed: {exc}",
            })
            continue
        row = score_run(item, result)
        rows.append(row)
        flag = "ok " if row["answered_correctly"] else "BAD"
        print(f"  {flag} {row['id']}: {row['steps']} steps -> {row['verdict'] or row['error']}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="use deterministic fixtures (default)")
    parser.add_argument("--live", action="store_true",
                        help="use real market data")
    parser.add_argument("--engine", default=None,
                        help="also run this LLM engine and measure agreement")
    parser.add_argument("--out", default="report/data",
                        help="directory to write results into")
    parser.add_argument("--max-steps", type=int, default=config.MAX_STEPS)
    args = parser.parse_args()

    offline = not args.live
    if offline:
        install_offline_data()

    print(f"Evaluation over {len(QUESTIONS)} questions "
          f"({'offline fixtures' if offline else 'live market data'})")

    print("\nrule engine:")
    rule_rows = run_engine("rule", args.max_steps)

    llm_rows: list[dict] = []
    agreement: dict = {}
    if args.engine:
        resolved = config.resolve_engine(args.engine)
        if resolved != args.engine:
            print(f"\n{args.engine} unavailable; skipping the agreement study.")
        else:
            print(f"\n{args.engine} engine:")
            llm_rows = run_engine(args.engine, args.max_steps)
            agreement = compare_engines(rule_rows, llm_rows)

    report = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "mode": "offline" if offline else "live",
        "question_count": len(QUESTIONS),
        "rule": summarise(rule_rows),
        "rule_rows": rule_rows,
    }
    if llm_rows:
        report["llm_engine"] = args.engine
        report["llm"] = summarise(llm_rows)
        report["llm_rows"] = llm_rows
        report["agreement"] = agreement

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "offline" if offline else "live"
    path = out_dir / f"evaluation-{suffix}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    s = report["rule"]
    print(f"\n--- rule engine over {s['questions']} questions ---")
    print(f"  trace validity      {s['trace_valid']}/{s['questions']}  ({s['trace_valid_pct']}%)")
    print(f"  groundedness        {s['grounded']}/{s['grounded_of']}  ({s['grounded_pct']}%)")
    print(f"  tool appropriateness {s['tools_appropriate']}/{s['answerable']}  ({s['tools_appropriate_pct']}%)")
    print(f"  behaved as required {s['answered_correctly']}/{s['questions']}  ({s['answered_correctly_pct']}%)")
    print(f"  mean steps          {s['mean_steps']}")
    if agreement:
        print(f"  engine agreement    {agreement['agreed']}/{agreement['compared']} "
              f"({agreement['agreement_pct']}%)")

    print(f"\nwritten to {path.relative_to(REPO)}")
    print("EVALUATION COMPLETE")


if __name__ == "__main__":
    main()
