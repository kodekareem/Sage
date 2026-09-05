"""The ReAct reasoning agent — the headline feature.

A single agent answers a natural-language investment question by running an
explicit Thought -> Action -> Observation loop, then emitting a Final Answer.
Three interchangeable *engines* implement that loop behind one interface:

``rule``    A deterministic, free, no-key engine. It scripts sensible thoughts,
            selects the appropriate real tools in a sensible order, calls them
            against real data, records every observation, and derives a verdict
            from the tool outputs. It genuinely walks the loop step by step — it
            never shortcuts — because the visible trace is the point.

``ollama``  A real local LLM (via Ollama) prompted to emit Thought/Action/Action
            Input we parse and execute, feeding observations back until it
            produces a Final Answer.

``claude``  The same hand-rolled loop, backed by the Anthropic API.

The two LLM engines share :class:`LLMEngine`; only the "call the model" step
differs. No agent framework (LangChain etc.) is used — hand-rolling the loop is
deliberate and keeps it legible for the report.

Every engine returns a :class:`~sage.react.ReActResult` with the identical
structured shape, so the UI and the report never special-case an engine.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from . import config
from .react import Action, FinalAnswer, ReActResult, ReActStep
from .tools import TOOL_REGISTRY, run_tool, tool_catalogue


# --------------------------------------------------------------------------- #
# Natural-language question parsing (shared by all engines for ticker hints)
# --------------------------------------------------------------------------- #
# Common company names -> tickers, so "Should I buy NVIDIA?" resolves cleanly.
_NAME_TO_TICKER = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "amd": "AMD",
    "intel": "INTC",
}

# Words that look like tickers (all-caps) but should be ignored.
_STOPWORDS = {"I", "A", "THE", "BUY", "SELL", "HOLD", "VS", "OR", "AND", "FOR", "ON", "ETF"}


def extract_tickers(question: str) -> list[str]:
    """Best-effort extraction of ticker symbols from a free-text question.

    Looks for ``$TICKER`` tags, bare 1-5 letter all-caps words, and known
    company names. Order is preserved and duplicates are removed.
    """
    found: list[str] = []

    def add(sym: str) -> None:
        sym = sym.upper()
        if sym not in found:
            found.append(sym)

    # 1) $-prefixed symbols, e.g. $AAPL
    for m in re.findall(r"\$([A-Za-z]{1,5})", question):
        add(m)

    # 2) Known company names (case-insensitive).
    lowered = question.lower()
    for name, ticker in _NAME_TO_TICKER.items():
        if re.search(rf"\b{name}\b", lowered):
            add(ticker)

    # 3) Bare all-caps tokens that aren't common English/stop words.
    for token in re.findall(r"\b([A-Z]{1,5})\b", question):
        if token not in _STOPWORDS:
            add(token)

    return found


def detect_intent(question: str, tickers: list[str]) -> str:
    """Return the reasoning path a question calls for.

    ``"size"``     — a risk/position-sizing question ("how many shares...")
    ``"compare"``  — two or more candidates weighed against each other
    ``"single"``   — a buy/sell/hold judgement on one stock
    """
    q = question.lower()
    # Sizing is checked first: "how many shares of AAPL" names one ticker but is
    # not a buy/sell/hold question.
    if re.search(r"\b(position size|how many shares|risk|stop[- ]?loss)\b", q):
        # Only treat it as sizing when there are numbers to size with.
        if re.search(r"\d", q):
            return "size"
    if len(tickers) >= 2 or " vs " in q or "compare" in q or "versus" in q:
        return "compare"
    return "single"


def extract_money(question: str) -> list[float]:
    """Pull numeric quantities out of a question, ignoring ticker-like tokens.

    Handles ``$10,000``, ``10000``, ``2%`` and ``150.50`` alike, preserving the
    order they appear so the caller can map them onto expected arguments.
    """
    values: list[float] = []
    for raw in re.findall(r"\$?\d[\d,]*(?:\.\d+)?", question):
        try:
            values.append(float(raw.replace("$", "").replace(",", "")))
        except ValueError:
            continue
    return values


# --------------------------------------------------------------------------- #
# RULE ENGINE — deterministic, free, but a *genuine* step-by-step ReAct trace
# --------------------------------------------------------------------------- #
class RuleEngine:
    """A scripted but real ReAct loop.

    It does not shortcut: for each question it walks Thought -> Action ->
    Observation across real tool calls, then reasons over the collected
    observations to produce a verdict. The thoughts are scripted, but the tool
    calls, observations and final rationale are all derived from live data.
    """

    name = "rule"

    def run(self, question: str) -> ReActResult:
        result = ReActResult(question=question, engine=self.name)
        tickers = extract_tickers(question)

        if not tickers:
            result.error = (
                "I couldn't identify a stock ticker in your question. "
                "Try naming a company (e.g. 'NVIDIA') or a symbol (e.g. 'NVDA')."
            )
            return result

        intent = detect_intent(question, tickers)
        if intent == "size":
            return self._run_position_size(question, tickers[0], result)
        if intent == "compare":
            return self._run_comparison(question, tickers, result)
        return self._run_single(question, tickers[0], result)

    # -- risk-based position sizing ---------------------------------------- #
    def _run_position_size(self, question: str, ticker: str, result: ReActResult) -> ReActResult:
        """Answer "how many shares should I buy?" with explicit risk arithmetic.

        The numbers are read from the question in the order a user states them
        (account size, risk percent, entry, stop). When the entry price is not
        given, the agent looks it up with ``get_quote`` first — which is itself a
        visible reasoning step rather than a hidden default.
        """
        # Read the labelled values first — a stop or entry named in words is far
        # more reliable than the order the numbers happen to appear in.
        def labelled(pattern: str) -> float | None:
            match = re.search(pattern, question, re.IGNORECASE)
            if not match:
                return None
            try:
                return float(match.group(1).replace("$", "").replace(",", ""))
            except ValueError:
                return None

        # A risk percentage is the value written with a % sign, if present.
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", question)
        risk_pct = float(pct_match.group(1)) if pct_match else None

        stop = labelled(r"stop(?:[- ]?loss)?\s*(?:price\s*)?(?:at|of|is|:)?\s*\$?([\d,]+(?:\.\d+)?)")
        entry = labelled(r"(?:entry|buying|buy|enter(?:ing)?)\s*(?:at|price|of)?\s*\$?([\d,]+(?:\.\d+)?)")
        account = labelled(
            r"(?:account|portfolio|capital|have|balance)\s*(?:of|is|size|:)?\s*\$?([\d,]+(?:\.\d+)?)"
        )

        # Fall back to positional reading only for values not named explicitly,
        # skipping any number already claimed by a label.
        claimed = {v for v in (risk_pct, stop, entry, account) if v is not None}
        remaining = [n for n in extract_money(question) if n not in claimed]
        if account is None and remaining:
            account = remaining.pop(0)
        if entry is None and remaining:
            entry = remaining.pop(0)
        if stop is None and remaining:
            stop = remaining.pop(0)

        step_index = 1

        # If no entry price was quoted, fetch the live one — visibly.
        if entry is None:
            thought = (
                f"To size a position in {ticker} I need an entry price, and the "
                "question doesn't state one. I'll use the current market price."
            )
            obs = run_tool("get_quote", {"ticker": ticker})
            result.steps.append(
                ReActStep(
                    index=step_index,
                    thought=thought,
                    action=Action(tool="get_quote", tool_input={"ticker": ticker}),
                    observation=obs,
                )
            )
            step_index += 1
            if not obs.get("ok"):
                result.error = obs.get("error", "Could not fetch a price to size against.")
                return result
            entry = obs.get("price")

        if account is None or risk_pct is None or entry is None:
            result.error = (
                "To size a position I need an account size, a risk percentage, and "
                "a stop price — for example: 'I have $10,000, risking 2% on AAPL "
                "at 150 with a stop at 140.'"
            )
            return result

        # A missing stop is a real gap, not something to invent: say so.
        if stop is None:
            result.error = (
                "I need a stop-loss price to work out the risk per share. "
                "Add one, for example '... with a stop at 140'."
            )
            return result

        tool_input = {
            "account_size": account,
            "risk_pct": risk_pct,
            "entry": entry,
            "stop": stop,
        }
        thought = (
            f"Now I can size the {ticker} position: risking {risk_pct}% of "
            f"{account} with an entry at {entry} and a stop at {stop}."
        )
        obs = run_tool("estimate_position_size", tool_input)
        result.steps.append(
            ReActStep(
                index=step_index,
                thought=thought,
                action=Action(tool="estimate_position_size", tool_input=tool_input),
                observation=obs,
            )
        )

        if not obs.get("ok"):
            result.error = obs.get("error", "Could not compute a position size.")
            return result

        def money(value) -> str:
            """Render a number without a pointless trailing '.0'."""
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)

        shares = obs["shares"]
        unit = "share" if shares == 1 else "shares"

        # Zero shares is a real answer, not an error: the stop is too wide for
        # the risk budget. Say so plainly instead of returning "0 shares".
        if shares == 0:
            rationale = (
                f"Risking {money(risk_pct)}% of a {money(account)} account allows "
                f"{money(obs['risk_amount'])} of loss, but with an entry at "
                f"{money(entry)} and a stop at {money(stop)}, a single share "
                f"already risks {money(obs['per_share_risk'])}. Even one share "
                "would exceed the risk budget, so this trade does not fit the "
                "stated limit — widen the budget, or use a tighter stop."
            )
            result.final = FinalAnswer(
                recommendation="0 shares — trade does not fit your risk limit",
                confidence="high",
                rationale=rationale,
            )
            return result

        rationale = (
            f"Risking {money(risk_pct)}% of a {money(account)} account is "
            f"{money(obs['risk_amount'])}. With an entry at {money(entry)} and a "
            f"stop at {money(stop)}, each share risks "
            f"{money(obs['per_share_risk'])}, so {shares} {unit} keeps the loss "
            f"within that budget if the stop is hit. That position is worth "
            f"{money(obs['position_value'])}, or {obs['position_pct_of_account']}% "
            "of the account. This is position sizing only — it is not a view on "
            f"whether {ticker} is worth buying."
        )
        result.final = FinalAnswer(
            recommendation=f"{shares} {unit}",
            confidence="high",  # arithmetic, not judgement
            rationale=rationale,
        )
        return result

    # -- single-stock buy/sell/hold ---------------------------------------- #
    def _run_single(self, question: str, ticker: str, result: ReActResult) -> ReActResult:
        steps_plan = [
            (
                f"To advise on {ticker}, I should first check the current price and "
                "how it moved most recently.",
                "get_quote",
                {"ticker": ticker},
            ),
            (
                "A single day says little on its own, so I'll look at how the stock "
                "has performed over the last six months for context.",
                "get_price_history",
                {"ticker": ticker, "period": "6mo"},
            ),
            (
                "Next I want the trend and momentum picture: RSI and the 50/200-day "
                "moving-average crossover.",
                "calculate_technical_indicators",
                {"ticker": ticker},
            ),
            (
                "Finally I should look at valuation and company fundamentals to sanity-"
                "check the technical picture.",
                "get_fundamentals",
                {"ticker": ticker},
            ),
        ]

        observations: dict[str, dict] = {}
        for i, (thought, tool_name, tool_input) in enumerate(steps_plan, start=1):
            obs = run_tool(tool_name, tool_input)
            observations[tool_name] = obs
            result.steps.append(
                ReActStep(
                    index=i,
                    thought=thought,
                    action=Action(tool=tool_name, tool_input=tool_input),
                    observation=obs,
                )
            )

        # If the very first lookup failed, the ticker is probably invalid.
        if not observations["get_quote"].get("ok"):
            result.error = observations["get_quote"].get("error", "Could not fetch data.")
            return result

        result.final = self._single_verdict(ticker, observations)
        return result

    @staticmethod
    def _single_verdict(ticker: str, obs: dict[str, dict]) -> FinalAnswer:
        """Derive a transparent buy/hold/sell verdict from the observations.

        We tally bullish vs bearish points across trend, momentum and valuation,
        and build the rationale from the very same readings the trace shows — so
        the conclusion is fully traceable.
        """
        tech = obs.get("calculate_technical_indicators", {})
        fund = obs.get("get_fundamentals", {})
        quote = obs.get("get_quote", {})
        history = obs.get("get_price_history", {})

        bull, bear, reasons = 0, 0, []

        # Medium-term performance: a six-month return is context the day's move
        # cannot give. Only a decisive move counts, so noise doesn't sway it.
        if history.get("ok"):
            period_return = history.get("period_return_pct")
            period = history.get("period", "6mo")
            if isinstance(period_return, (int, float)):
                if period_return >= 10:
                    bull += 1
                    reasons.append(f"it is up {period_return}% over the last {period}")
                elif period_return <= -10:
                    bear += 1
                    reasons.append(f"it is down {abs(period_return)}% over the last {period}")
                else:
                    reasons.append(f"it is broadly flat over the last {period} ({period_return}%)")

        # Trend: price vs 200-day SMA, and the 50/200 crossover.
        if tech.get("ok"):
            if tech.get("price_above_sma200"):
                bull += 1
                reasons.append("price is above its 200-day average (longer-term uptrend)")
            elif tech.get("sma200") is not None:
                bear += 1
                reasons.append("price is below its 200-day average (longer-term downtrend)")

            cross = tech.get("crossover_signal")
            if cross == "golden_cross":
                bull += 1
                reasons.append("the 50-day average is above the 200-day average (golden cross)")
            elif cross == "death_cross":
                bear += 1
                reasons.append("the 50-day average is below the 200-day average (death cross)")

            # Momentum via RSI.
            rsi, rsi_signal = tech.get("rsi"), tech.get("rsi_signal")
            if rsi_signal == "overbought":
                bear += 1
                reasons.append(f"RSI is {rsi} (overbought — extended in the short term)")
            elif rsi_signal == "oversold":
                bull += 1
                reasons.append(f"RSI is {rsi} (oversold — potentially due for a bounce)")
            elif rsi is not None:
                reasons.append(f"RSI is {rsi} (neutral momentum)")

        # Valuation via trailing P/E.
        if fund.get("ok"):
            pe = fund.get("trailing_pe")
            if isinstance(pe, (int, float)):
                if pe < 0:
                    bear += 1
                    reasons.append("the company is currently unprofitable (negative P/E)")
                elif pe > 40:
                    bear += 1
                    reasons.append(f"valuation looks rich (P/E of {pe})")
                elif pe < 25:
                    bull += 1
                    reasons.append(f"valuation looks reasonable (P/E of {pe})")
                else:
                    reasons.append(f"valuation is moderate (P/E of {pe})")

        # Map the tally to a recommendation and a confidence from the margin.
        net = bull - bear
        if net >= 2:
            recommendation = "BUY"
        elif net <= -2:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"

        margin = abs(net)
        confidence = "high" if margin >= 3 else "medium" if margin == 2 else "low"

        price = quote.get("price")
        rationale = (
            f"For {ticker} (last price {price}), the evidence weighs "
            f"{bull} bullish vs {bear} bearish signals. "
            + ("Specifically, " + "; ".join(reasons) + "." if reasons else "")
            + f" On balance this points to a {recommendation} with {confidence} confidence."
        )
        return FinalAnswer(recommendation=recommendation, confidence=confidence, rationale=rationale)

    # -- two-or-more-stock comparison -------------------------------------- #
    def _run_comparison(self, question: str, tickers: list[str], result: ReActResult) -> ReActResult:
        thought1 = (
            f"This is a comparison between {', '.join(tickers)}. I'll pull a side-by-side "
            "of price, valuation, momentum and trend for all of them at once."
        )
        action1 = Action(tool="compare_tickers", tool_input={"tickers": tickers})
        obs1 = run_tool("compare_tickers", {"tickers": tickers})
        result.steps.append(ReActStep(index=1, thought=thought1, action=action1, observation=obs1))

        if not obs1.get("ok"):
            result.error = obs1.get("error", "Could not compare the tickers.")
            return result

        thought2 = (
            "Now I'll score each stock on trend (golden vs death cross), momentum (RSI) "
            "and valuation (P/E) to decide which is the stronger candidate."
        )
        # The "scoring" is a second reasoning step over the same observation —
        # we record it explicitly so the trace shows the decision being made.
        verdict, scores = self._comparison_verdict(obs1["rows"])
        result.steps.append(
            ReActStep(
                index=2,
                thought=thought2,
                action=None,
                observation={"scores": scores},
                note="Composite scoring step (no external tool call needed).",
            )
        )
        result.final = verdict
        return result

    @staticmethod
    def _comparison_verdict(rows: list[dict]) -> tuple[FinalAnswer, dict]:
        """Score each row and pick a winner, explaining why."""
        scores: dict[str, int] = {}
        notes: dict[str, list[str]] = {}

        for row in rows:
            tk = row["ticker"]
            score, why = 0, []
            if row.get("crossover_signal") == "golden_cross":
                score += 1
                why.append("uptrend (golden cross)")
            elif row.get("crossover_signal") == "death_cross":
                score -= 1
                why.append("downtrend (death cross)")

            rsi = row.get("rsi")
            if isinstance(rsi, (int, float)):
                if rsi >= 70:
                    score -= 1
                    why.append(f"overbought (RSI {rsi})")
                elif rsi <= 30:
                    score += 1
                    why.append(f"oversold (RSI {rsi})")

            pe = row.get("trailing_pe")
            if isinstance(pe, (int, float)) and pe > 0:
                if pe < 25:
                    score += 1
                    why.append(f"reasonable valuation (P/E {pe})")
                elif pe > 40:
                    score -= 1
                    why.append(f"rich valuation (P/E {pe})")

            scores[tk] = score
            notes[tk] = why

        # Rank by score, breaking display order alphabetically so the trace is
        # deterministic regardless of the order the tickers were mentioned in.
        ordered = sorted(scores, key=lambda k: (-scores[k], k))
        top_score = scores[ordered[0]]
        # Every ticker sharing the top score is a genuine joint leader.
        leaders = [tk for tk in ordered if scores[tk] == top_score]
        runner_up = next((scores[tk] for tk in ordered if scores[tk] < top_score), None)
        margin = top_score - runner_up if runner_up is not None else 0

        detail = "; ".join(
            f"{tk}: {', '.join(notes[tk]) or 'no strong signals'} (score {scores[tk]})"
            for tk in ordered
        )

        # A dead heat must be reported as one. Silently picking a "winner" out of
        # equal scores would put a preference in the verdict that the visible
        # trace cannot justify — which would undermine the whole point of the
        # trace. Being honest about a tie is the more useful answer anyway.
        if len(leaders) > 1:
            joined = " and ".join(leaders)
            recommendation = f"TOO CLOSE TO CALL: {joined}"
            rationale = (
                f"Comparing the candidates — {detail}. "
                f"{joined} score equally on this composite ({top_score}), so the "
                "evidence gathered here does not separate them. Rather than pick "
                "one arbitrarily, Sage reports the tie: distinguishing them would "
                "need criteria beyond the trend, momentum and valuation signals "
                "checked above."
            )
            return (
                FinalAnswer(recommendation=recommendation, confidence="low", rationale=rationale),
                scores,
            )

        winner = leaders[0]
        confidence = "high" if margin >= 2 else "medium" if margin == 1 else "low"
        rationale = (
            f"Comparing the candidates — {detail}. "
            f"On this composite, {winner} screens strongest, so it is the preferred "
            f"pick of the group with {confidence} confidence."
        )
        return (
            FinalAnswer(recommendation=f"PREFER {winner}", confidence=confidence, rationale=rationale),
            scores,
        )


# --------------------------------------------------------------------------- #
# LLM OUTPUT PARSER (shared, and unit-tested in isolation)
# --------------------------------------------------------------------------- #
def parse_react_output(text: str) -> dict:
    """Parse a model's ReAct turn into a structured dict.

    Recognised shapes (case-insensitive labels)::

        Thought: ...
        Action: tool_name
        Action Input: {"ticker": "AAPL"}

    or::

        Thought: ...
        Final Answer: {"recommendation": "BUY", "confidence": "high", "rationale": "..."}

    Returns a dict with:
      - ``thought``: str | None
      - ``kind``: "action" | "final" | "malformed"
      - ``action``/``action_input``  (when kind == "action")
      - ``final`` (a dict) (when kind == "final")
      - ``raw``: the original text

    Malformed or unparseable output is reported as ``kind == "malformed"`` rather
    than raising, so the loop can recover gracefully.
    """
    out: dict = {"thought": None, "kind": "malformed", "raw": text}

    thought_match = re.search(r"Thought:\s*(.+?)(?=\n\s*(?:Action|Final Answer)\s*:|$)",
                              text, re.IGNORECASE | re.DOTALL)
    if thought_match:
        out["thought"] = thought_match.group(1).strip()

    # Final Answer branch takes precedence (the loop should stop).
    final_match = re.search(r"Final Answer:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if final_match:
        payload = _loads_loose(final_match.group(1))
        if isinstance(payload, dict):
            out["kind"] = "final"
            out["final"] = {
                "recommendation": str(payload.get("recommendation", "HOLD")),
                "confidence": str(payload.get("confidence", "low")),
                "rationale": str(payload.get("rationale", "")),
            }
        else:
            # Free-text final answer is still usable as a rationale.
            out["kind"] = "final"
            out["final"] = {
                "recommendation": "HOLD",
                "confidence": "low",
                "rationale": final_match.group(1).strip(),
            }
        return out

    action_match = re.search(r"Action:\s*([A-Za-z_][A-Za-z0-9_]*)", text, re.IGNORECASE)
    input_match = re.search(r"Action Input:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if action_match:
        out["kind"] = "action"
        out["action"] = action_match.group(1).strip()
        out["action_input"] = (
            _loads_loose(input_match.group(1)) if input_match else {}
        )
        if not isinstance(out["action_input"], dict):
            out["action_input"] = {}
        return out

    return out


def _loads_loose(text: str):
    """Parse the first JSON object/array in ``text`` (tolerant of surrounding prose).

    Uses ``raw_decode`` so trailing prose *after* a valid object is ignored, while
    still correctly handling nested objects (which a non-greedy regex would not).
    """
    text = text.strip()
    # Strip Markdown code fences if present.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    # Start at the first opening bracket/brace so leading prose is skipped.
    start = next((i for i, ch in enumerate(text) if ch in "{["), None)
    candidate = text[start:] if start is not None else text
    try:
        obj, _ = json.JSONDecoder().raw_decode(candidate)
        return obj
    except (json.JSONDecodeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# LLM ENGINE BASE — the hand-rolled ReAct loop for ollama and claude
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You are Sage, a transparent stock investment analyst. You answer
the user's question by reasoning step by step and calling analysis tools.

You have these tools:
{tools}

Respond in EACH turn with EXACTLY one of these two formats.

To call a tool:
Thought: <your reasoning about what to find out next>
Action: <one tool name from the list>
Action Input: <a JSON object of arguments, e.g. {{"ticker": "AAPL"}}>

When you have enough information to answer:
Thought: <your final reasoning>
Final Answer: <a JSON object: {{"recommendation": "BUY|SELL|HOLD or a comparison verdict", "confidence": "low|medium|high", "rationale": "<plain-language explanation>"}}>

Rules:
- Output ONLY the Thought and the Action/Action Input (or Final Answer). No extra prose.
- Use real tickers. Call tools before concluding. Do not invent numbers — read them from observations.
- Write the Action as PLAIN TEXT in exactly the format above. Do NOT use your
  built-in function/tool-calling mechanism and do NOT emit JSON of the form
  {{"name": ..., "arguments": ...}} — Sage parses your text itself, and a native
  tool call will be rejected.
"""


class LLMEngine:
    """Base class implementing the ReAct loop for any chat-style LLM backend.

    Subclasses implement :meth:`complete`, which takes the running message list
    and returns the model's text for the next turn.
    """

    name = "llm"

    def __init__(self, max_steps: int = config.MAX_STEPS):
        self.max_steps = max_steps

    # Subclasses override this.
    def complete(self, messages: list[dict]) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def run(self, question: str) -> ReActResult:
        result = ReActResult(question=question, engine=self.name)
        system = SYSTEM_PROMPT.format(tools=tool_catalogue())
        # We keep an OpenAI/Anthropic-style message list; the system prompt is
        # handled by each backend (passed separately or as the first message).
        messages: list[dict] = [{"role": "user", "content": question}]

        consecutive_malformed = 0
        for i in range(1, self.max_steps + 1):
            try:
                raw = self.complete([{"role": "system", "content": system}] + messages)
            except Exception as exc:  # network / API failure
                result.error = f"LLM call failed: {exc}"
                return result

            parsed = parse_react_output(raw)

            # --- Final answer: stop the loop. ---
            if parsed["kind"] == "final":
                result.steps.append(
                    ReActStep(index=i, thought=parsed.get("thought") or "(no thought given)")
                )
                f = parsed["final"]
                result.final = FinalAnswer(f["recommendation"], f["confidence"], f["rationale"])
                return result

            # --- Tool call: execute and feed back the observation. ---
            if parsed["kind"] == "action":
                consecutive_malformed = 0
                action = Action(tool=parsed["action"], tool_input=parsed["action_input"])
                observation = run_tool(action.tool, action.tool_input)
                result.steps.append(
                    ReActStep(
                        index=i,
                        thought=parsed.get("thought") or "(no thought given)",
                        action=action,
                        observation=observation,
                    )
                )
                # Echo the assistant turn and supply the observation as the next user turn.
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {"role": "user", "content": "Observation: " + json.dumps(observation)}
                )
                continue

            # --- Malformed output: record it and nudge the model to retry. ---
            consecutive_malformed += 1
            result.steps.append(
                ReActStep(
                    index=i,
                    thought=parsed.get("thought") or "(unparseable model output)",
                    note="Malformed model output — could not parse an Action or Final Answer.",
                )
            )
            if consecutive_malformed >= 2:
                result.error = "The model repeatedly produced output I couldn't parse."
                return result
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "I could not parse that. Reply using EXACTLY the required "
                        "format: either 'Action:' + 'Action Input:' or 'Final Answer:'."
                    ),
                }
            )

        # Hit the step cap without concluding.
        result.error = f"Reached the maximum of {self.max_steps} reasoning steps without a final answer."
        return result


class OllamaEngine(LLMEngine):
    """Drives a local Ollama model (free, no key) through the ReAct loop."""

    name = "ollama"

    def __init__(self, model: str = config.OLLAMA_MODEL, url: str = config.OLLAMA_URL,
                 max_steps: int = config.MAX_STEPS):
        super().__init__(max_steps=max_steps)
        self.model = model
        self.url = url

    def complete(self, messages: list[dict]) -> str:
        import requests

        resp = requests.post(
            f"{self.url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class GroqEngine(LLMEngine):
    """Drives an open-weight model on Groq through the same ReAct loop.

    Groq exposes an OpenAI-compatible ``/chat/completions`` endpoint, so the
    message list the loop already maintains — including the ``system`` role —
    can be posted unchanged. It runs open-weight models (Llama, Qwen, GPT-OSS)
    on a free tier, which makes it the practical way to demonstrate the loop
    driving a genuine LLM without a local GPU or a paid key.
    """

    name = "groq"

    def __init__(self, model: str = config.GROQ_MODEL, url: str = config.GROQ_URL,
                 max_steps: int = config.MAX_STEPS):
        super().__init__(max_steps=max_steps)
        self.model = model
        self.url = url
        self._key = config.get_groq_key()

    def complete(self, messages: list[dict]) -> str:
        import requests

        response = requests.post(
            f"{self.url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                # Low temperature: we want the model to follow the ReAct format
                # reliably, not to be creative about it.
                "temperature": 0.2,
                "max_tokens": 1024,
            },
            timeout=120,
        )

        # Sage parses tool calls out of the model's *text*, so no `tools` array
        # is declared. A model that reaches for its native function-calling
        # mechanism anyway is rejected by the API with a 400 that still carries
        # the attempted call in `failed_generation`. Rather than lose the turn,
        # translate that attempt back into the text format the loop expects.
        if response.status_code == 400:
            recovered = self._recover_native_tool_call(response)
            if recovered is not None:
                return recovered

        response.raise_for_status()
        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected Groq response shape: {payload}") from exc

    @staticmethod
    def _recover_native_tool_call(response) -> Optional[str]:
        """Turn a rejected native tool call into a plain-text ReAct action.

        Returns ``None`` when the error is anything else, so genuine failures
        still surface as errors instead of being silently swallowed.
        """
        try:
            error = response.json().get("error", {})
        except ValueError:
            return None

        if error.get("code") != "tool_use_failed":
            return None

        attempted = _loads_loose(error.get("failed_generation", "") or "")
        if not isinstance(attempted, dict):
            return None

        tool = attempted.get("name")
        arguments = attempted.get("arguments", {})
        if not isinstance(tool, str) or not tool:
            return None
        if isinstance(arguments, str):  # some models stringify the arguments
            arguments = _loads_loose(arguments) or {}
        if not isinstance(arguments, dict):
            arguments = {}

        return (
            "Thought: (recovered from a native tool call)\n"
            f"Action: {tool}\n"
            f"Action Input: {json.dumps(arguments)}"
        )


class ClaudeEngine(LLMEngine):
    """Drives the Anthropic API through the same hand-rolled ReAct loop."""

    name = "claude"

    def __init__(self, model: str = config.CLAUDE_MODEL, max_steps: int = config.MAX_STEPS):
        super().__init__(max_steps=max_steps)
        self.model = model
        import anthropic

        # Build the client once and reuse its connection pool across loop steps.
        self._client = anthropic.Anthropic(api_key=config.get_anthropic_key())

    def complete(self, messages: list[dict]) -> str:
        # The Anthropic Messages API takes the system prompt separately, not as a
        # message with role "system". Split it out.
        system = ""
        chat = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                chat.append({"role": m["role"], "content": m["content"]})
        response = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=chat,
        )
        # Concatenate the text blocks of the reply.
        return "".join(block.text for block in response.content if block.type == "text")


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def create_engine(name: str, max_steps: int = config.MAX_STEPS):
    """Instantiate an engine by name.

    Raises ``ValueError`` for an unknown name, or ``RuntimeError`` if a requested
    LLM engine is not actually available (no Ollama / no key). Callers that want
    a guaranteed-working engine should resolve the name with
    :func:`config.resolve_engine` first.
    """
    if name == "rule":
        return RuleEngine()
    if name == "ollama":
        if not config.ollama_available():
            raise RuntimeError(
                "Ollama is not reachable at "
                f"{config.OLLAMA_URL}. Start it with `ollama serve` and pull a model."
            )
        return OllamaEngine(max_steps=max_steps)
    if name == "groq":
        if not config.groq_available():
            raise RuntimeError(
                "The Groq engine needs GROQ_API_KEY set (get a free key at "
                "https://console.groq.com) and the `requests` package installed."
            )
        return GroqEngine(max_steps=max_steps)
    if name == "claude":
        if not config.claude_available():
            raise RuntimeError(
                "The Claude engine needs ANTHROPIC_API_KEY set and the `anthropic` package installed."
            )
        return ClaudeEngine(max_steps=max_steps)
    raise ValueError(f"Unknown engine {name!r}. Choose from {config.ENGINES}.")


def ask(question: str, engine: str = "rule", max_steps: int = config.MAX_STEPS) -> ReActResult:
    """Convenience entry point: build the engine and run the question."""
    return create_engine(engine, max_steps=max_steps).run(question)
