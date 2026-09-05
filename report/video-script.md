# Sage: video script and shot list

**Target runtime: 4 minutes.** The brief allows 3 to 5.

**Constraints, from the brief.** Record this in your own voice. No AI generated
voices are permitted. Do not speed the recording up. The video does not need to
show you on camera, but it must have audio narration spoken by you.

**Before recording**

- Open a terminal in the project directory with the virtual environment active.
- Run `streamlit run app.py` and leave it open in a browser tab.
- Have a second terminal ready for the command line demonstration.
- Set the terminal font large enough to read at 1080p, roughly 16pt.
- Run through once without recording so the live data has loaded and cached.

Lines marked `SAY:` are spoken. Lines marked `SHOW:` are what is on screen at
that moment. Timings are cumulative and approximate.

---

## 1. What the problem is (0:00 to 0:35)

SHOW: The Streamlit app, at rest, with the question box visible.

SAY: This is Sage, a stock investment advisor built for CM3020, following
Project Idea 2, the Financial Advisor Bot. The problem it addresses is not that
investment analysis is unavailable, but that free analysis is impossible to
check. A chatbot will discuss a stock confidently, with no access to live
prices, inventing figures when it is unsure, and no way to see how it got there.

SAY: Sage takes the opposite approach. Every figure comes from a real tool call
against real market data, and it shows you the whole chain of reasoning.

---

## 2. The reasoning loop, live (0:35 to 1:35)

SHOW: Type "Should I buy NVIDIA right now?" into the app and press Analyse.

SAY: I am asking whether to buy NVIDIA. Watch what happens rather than just the
answer at the end.

SHOW: The recommendation appears at the top. Scroll slowly to the trace and
expand step one.

SAY: The recommendation comes first, with a confidence level. Underneath is the
part that matters. This is a ReAct loop, from Yao and colleagues. The agent
forms a thought, chooses a tool, and observes a structured result. Step one, it
needs the current price, calls the quote tool, and gets real data back.

SHOW: Expand steps two, three and four in turn, pausing on each observation.

SAY: Step two, six month price history for context. Step three, the technical
indicators, a fourteen period relative strength index and the fifty and two
hundred day moving averages. Step four, the fundamentals, including the price to
earnings ratio.

SHOW: Scroll back up to the rationale and highlight two figures in it, then
scroll down to the observations containing those same figures.

SAY: Now compare the rationale with the trace. Every number in this explanation
appears in one of those observations above it. The agent is not recalling
figures from training data. It is reading them from tools, and you can check
that by eye.

---

## 3. The tool library and the engines (1:35 to 2:15)

SHOW: The sidebar, expanding two or three tool entries to show their parameters.

SAY: Six tools: a quote, price history, technical indicators, fundamentals, a
comparison, and position sizing. They sit in a registry with machine readable
descriptions, so adding a tool means writing one function.

SHOW: The engine selector in the sidebar, showing the four options and their
availability markers.

SAY: Four engines drive the same loop. The default is a deterministic rule
engine that needs no API key. The other three drive real language models, one
local through Ollama and two hosted. All four produce an identical trace
structure, which is what let me compare them in the evaluation.

---

## 4. Handling failure honestly (2:15 to 2:55)

SHOW: Ask "Compare AAPL and MSFT for a long-term hold" and let the result render.

SAY: Notice this verdict says too close to call, rather than picking one. An
earlier version broke ties by whichever ticker was named first, so Apple versus
Microsoft gave a different answer from Microsoft versus Apple on identical
evidence. For a system claiming the trace justifies the verdict, that was
serious. It now reports a tie as a tie.

SHOW: Ask "What is a good investment strategy?" and let it refuse.

SAY: And here it refuses. There is no ticker in that question, so there is
nothing to analyse, and guessing would be worse than declining.

---

## 5. Evaluation (2:55 to 3:40)

SHOW: The terminal. Run `python scripts/run_evaluation.py --offline --out report/data`
and let the results table print.

SAY: Whether the reasoning is any good is a separate question, and a passing
test suite does not answer it. So I scored fifteen fixed questions on four
measures: step completeness, whether every figure traces to an observation,
whether the right tools were called, and whether it refused what it could not
answer.

SHOW: The summary lines with the percentages.

SAY: The rule engine scores one hundred percent on all four. The language model
matches it on trace structure but scores eighty three percent on groundedness
and eighty percent on behaviour, because it computes figures its tools never
returned and it answers questions it should refuse. That is the most useful
thing I found. Tool calling controls where the evidence comes from. It does not
control what the model does with the evidence afterwards.

---

## 6. Close (3:40 to 4:00)

SHOW: The app with a completed trace visible, then the GitHub repository page.

SAY: Sage is a feasibility prototype, not financial advice. It does no risk
profiling and runs no backtest. What it demonstrates is that grounding every
figure in an auditable tool call, and showing the user the whole chain of
reasoning, is both implementable and worth the constraint. The code and the full
evaluation are in the repository.

---

## Notes for the recording

- The trace scroll in section two is the most important shot. Move slowly enough
  that a viewer can read a thought and an observation.
- If a live call is slow, keep talking rather than cutting; the brief forbids
  speeding the video up.
- The evaluation run in section five takes a few seconds offline. Start speaking
  over it rather than waiting in silence.
- If the network is unavailable on the day, the offline evaluation still runs,
  and the app can be demonstrated on cached data from the rehearsal run.
