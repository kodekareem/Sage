# Sage: A Transparent, Tool-Using ReAct Investment Advisor for Stocks

**Final Project Report**

BSc Computer Science (Machine Learning), University of London
CM3020 Artificial Intelligence

**Code repository:** https://github.com/kodekareem/Sage (public)

**Total word count:** 8,007 of 10,500. Counts exclude chapter titles, table and
figure captions, and the reference list, as the brief permits.

---

## 1. Introduction (834/1000 words)

### Project concept

This project develops Sage, a single agent conversational investment advisor for
retail stock investors. A user asks an ordinary question, such as whether to buy
a particular share or how two companies compare for a long term hold, and Sage
answers with a recommendation and a clear rationale. What distinguishes it from
a chatbot that simply emits a verdict is its central feature: a transparent,
tool using ReAct reasoning loop. Sage works through each question one step at a
time. It forms a thought about what it needs to know, chooses a tool from a
library of financial analysis functions, observes the structured result, and
repeats until it can answer. Every one of these steps, the thought, the tool
chosen, the inputs, and the observation, is shown to the user. The advice is
therefore auditable. A person can read exactly how Sage reached its conclusion
rather than being asked to trust a number from a black box.

### Project template

This project follows Project Idea 2, the Financial Advisor Bot, from the CM3020
Artificial Intelligence template list. The brief asks for a bot that analyses
financial data, makes recommendations a non technical user can act on, and
presents its analysis with explanations. Sage targets the stock market and makes
the explanation itself the contribution. The two things being demonstrated are
the explainable ReAct tool calling loop and the financial tool library it draws
on. It is deliberately not a memory or learning system. The focus is the quality
and transparency of a single piece of reasoning, not adaptation over time.

### Motivation

Since 2020 tens of millions of people have opened retail brokerage accounts,
many of them new to investing. They face a market full of information and short
of trustworthy guidance. Professional advice is expensive, often a thousand to
several thousand dollars a year, which puts it out of reach for someone
investing modest sums. The free alternatives have a common weakness. Automated
robo advisors allocate money to funds from a risk questionnaire but cannot
reason about a specific company or explain a specific call. General purpose
chatbots can discuss a stock fluently, but they have no access to live prices,
they invent figures when unsure, and they offer no way to check how an answer
was reached. In each case the user is given a conclusion with no visible path to
it.

The problem Sage addresses is not only the absence of affordable analysis but
the absence of trustworthy, checkable analysis. An investment recommendation a
person cannot scrutinise is hard to trust and impossible to learn from. Sage is
built on the view that for a financial adviser, how an answer was reached
matters as much as the answer itself. By grounding every step in a real tool
call against real data, and by showing that whole chain of reasoning to the
user, Sage gives a recommendation a person can follow, question, and check.
This also has an educational benefit. A user who watches the agent gather a
price, read an indicator, and weigh a valuation learns something about how the
judgement is made, rather than collecting an opaque signal.

Sage is built as a feasibility prototype rather than a production system. The
aim is to show that a transparent tool using reasoning loop can be implemented,
can run on real market data, and can produce auditable advice, and to evaluate
that loop honestly, including where it falls short. The system uses a single
agent rather than several cooperating agents on purpose, so the effort and the
evaluation concentrate on the quality and clarity of one reasoning trace. Sage
is not financial advice and does no risk profiling or portfolio planning. The
report is explicit about this throughout.

### What changed since the preliminary report

Three things developed materially after the preliminary submission. First, the
system gained a fourth reasoning engine that drives any OpenAI compatible
endpoint, which is what made it possible to test the loop against a real hosted
language model rather than only a local one. Second, an audit against the
submission criteria found four defects in the prototype, described in Chapter 4,
which were fixed and covered by tests. Third, and most importantly for this
report, the evaluation was rebuilt. The preliminary report evaluated the system
with its unit test suite. That measures whether the code does what it was built
to do, but it says nothing about whether the reasoning is any good, which is
what the project actually claims. Chapter 5 replaces it with a scored study over
a fixed question set, run across two engines.

### Report structure

Chapter 2 reviews the relevant literature: domain specific financial language
models, the reasoning and tool use techniques the design builds on, and the
question of explainability that motivates the project, ending on the specific
gap Sage fills. Chapter 3 sets out the design. Chapter 4 describes the
implementation, the algorithms behind it, and the defects found and fixed
along the way. Chapter 5 presents the evaluation, its method, its results, and a
critique of the project as a whole. Chapter 6 concludes.

---

## 2. Literature Review (1527/2500 words)

Sage draws on three bodies of work: domain specific language models for finance,
the techniques that let language models reason step by step and use external
tools, and the broader concern with explainability in automated advice. This
chapter reviews each, evaluates the most relevant systems critically, and
identifies the gap Sage addresses.

### 2.1 Domain specific language models for finance

The best known attempt to specialise a language model for finance is
BloombergGPT (Wu et al., 2023), a fifty billion parameter model trained from
scratch on a very large corpus of financial text. On financial benchmarks it
outperformed comparably sized general models. As an engineering result it is
notable, but for the advisor Sage aims to be it has serious drawbacks. It is
closed: the model, weights, and training data are proprietary and access is tied
to Bloomberg's products. Its training cost, estimated in the millions of
dollars, puts reproduction out of reach. Most relevant here, it is a text model
rather than an agent. It has no built in way to fetch a live price, call an
analysis function, or show the working behind an answer. It can describe
finance, but it cannot act on current data or justify a recommendation step by
step, which is exactly what Sage sets out to do. Later analysis has questioned
whether its advantage over general models justifies its cost, noting that
smaller models reach similar results on many tasks (Aguda et al., 2024).

### 2.2 Open financial language models

FinGPT (Yang et al., 2023; Liu et al., 2023) is the leading open response to
BloombergGPT. Instead of training a giant model from scratch, it emphasises a
data centric pipeline, curating financial data and cheaply adapting open base
models. Its openness is a genuine contribution. For this project, though, FinGPT
is a research artifact rather than a usable advisor. It supplies adapted models
and benchmarks, not a system that holds a conversation, fetches current prices,
runs analysis tools, and explains its reasoning. To build the advisor described
in Chapter 1 on top of FinGPT, one would still have to add the data layer, the
tool library, and the reasoning loop, which is the substance of the work. FinGPT
is useful evidence that capable financial language modelling can be open and
cheap, but it does not provide the explainable, tool using behaviour Sage is
built to demonstrate.

A further point emerged from this project's own evaluation and is worth stating
here, because it bears on how these models should be judged. The comparative
study in Chapter 5 found that a competent general purpose open model, driven
through a well specified reasoning loop against real tools, produced traces that
were valid in structure and largely faithful to their evidence. The binding
constraint on answer quality was not the model's financial knowledge but the
discipline of the loop around it. That is an argument for investing in the
scaffolding rather than in domain specific pretraining, at least at the scale a
retail advice tool operates.

### 2.3 Reasoning step by step: chain of thought and ReAct

The techniques that make Sage possible come from the reasoning literature. Chain
of thought prompting (Wei et al., 2022) showed that prompting a model to produce
intermediate reasoning steps, rather than jumping to an answer, substantially
improves performance on multi step problems, and as a side effect makes the
reasoning legible. This is the conceptual root of Sage's visible reasoning. The
decisive extension is ReAct (Yao et al., 2022), which interleaves reasoning with
action. In ReAct a model alternates between a thought about what to do next and
an action that queries an external source, then observes the result and
continues. Yao et al. show that this both reduces hallucination, because the
model checks the world instead of guessing, and improves interpretability,
because the thought and action trace is human readable.

Sage is a direct application of the ReAct pattern to investment questions. The
agent reasons about what it needs, calls a financial tool, observes a real
result, and continues until it can recommend, with the full thought, action, and
observation sequence preserved and shown. The hallucination point matters in
finance specifically: because every figure Sage uses comes from a tool call
rather than from the model's memory, it cannot fabricate a price or an earnings
multiple, which is a common and dangerous failure of plain chatbot financial
advice.

It is worth being precise about what ReAct does and does not guarantee, because
this project's evaluation sharpened the distinction. Grounding the agent's
*inputs* in tool calls does not by itself guarantee that its *output* only
contains grounded figures. The measurements in Chapter 5 found that a language
model driving the loop still produced numbers that appeared in no observation,
not by inventing prices, but by computing derived quantities and stating them
with the same confidence as measured ones. The tool calling architecture
constrains where evidence comes from; it does not constrain what the model does
with that evidence afterwards. Yao et al. are careful to claim reduced
hallucination rather than eliminated hallucination, and this project's results
support that narrower reading.

### 2.4 Tool use in language models

ReAct relies on the model being able to use external tools well, and a parallel
line of work studies tool use directly. Toolformer (Schick et al., 2023) showed
that a language model can learn when and how to call external APIs, deciding for
itself which tool helps with which sub problem. This established tool use as a
first class capability rather than a workaround.

Sage applies the idea in a focused, transparent form. Rather than training a
model to embed tool calls, it exposes a small, clean library of financial tools
through a registry with machine readable descriptions, and lets the agent choose
among them within the ReAct loop. The tools are deterministic and return
structured results, so the agent's job is orchestration and interpretation, not
calculation. This division matters for the project's goals. Because the numbers
come from auditable functions and only the reasoning comes from the agent, the
system is both trustworthy, since the data is real, and explainable, since the
reasoning is visible.

Implementing this against several model providers exposed a practical wrinkle
the literature tends to gloss over. Modern hosted models increasingly ship their
own native function calling mechanism, and a model offered a list of tools in
its prompt may reach for that mechanism instead of the textual protocol the
surrounding system expects. Chapter 4 describes how Sage handles this. The
general point is that "tool use" is no longer a single technique but a
negotiation between a system's protocol and a model's built in habits, and
robustness work sits in that gap.

### 2.5 Explainability in automated financial advice

The motivation for all of this is explainability, which is a recognised problem
for machine learning in finance. Much of the strongest work on automated trading
uses methods that are effective but opaque. Deep reinforcement learning
approaches to portfolio management, for instance the influential framework of
Jiang et al. (2017), can learn profitable looking policies from historical data,
but those policies output an action with no human readable justification and are
known to transfer poorly from simulation to live markets. For a tool whose
purpose is to advise a non expert and earn their trust, opacity is a fundamental
limitation rather than a detail. A user cannot learn from, question, or sensibly
act on a recommendation they cannot inspect.

Sage takes the opposite stance. It accepts a deliberately simple and transparent
decision process in exchange for complete auditability. Every recommendation can
be traced, step by step, back to the specific tool readings that produced it.
The project's wager is that for a retail advice tool, an explanation a person
can follow is worth more than a marginally better but inscrutable verdict.

The evaluation in Chapter 5 gives this wager an empirical edge that the
preliminary report could not. Two engines answering the same fifteen questions
from identical evidence agreed on the verdict in only a quarter of cases. Under
an opaque system that divergence would be invisible; the user would receive one
verdict and have no way to know that a differently constructed reasoner would
have said something else. Because both engines emit the same structured trace,
the disagreements can be located and inspected, and most turn out to be
differences of threshold and emphasis rather than contradictions about the
facts. Transparency here is not only an ethical nicety. It is what makes the
system's own variability measurable.

### 2.6 Summary and gap

The literature provides the pieces but not the combination Sage needs.
BloombergGPT and FinGPT specialise language models for finance but are not
agents and cannot act on live data or explain a specific call. Chain of thought
and ReAct make reasoning legible and let a model act in the world, and
Toolformer makes tool use a first class capability, but these are general
techniques not applied to a transparent stock advisor. The reinforcement
learning trading literature learns from market data but produces opaque
policies, which is the opposite of what a trustworthy adviser needs. The gap
Sage fills is a stock advisor that answers an ordinary investment question by
reasoning step by step over a library of real analysis tools, and that exposes
the entire reasoning trace so the advice is auditable rather than a black box
verdict. The next chapter describes how this is designed.

---

## 3. Design (1356/2000 words)

Sage is organised as a small set of components, each with a single
responsibility, connected by one reasoning loop. This chapter describes the data
layer, the tool library, the ReAct loop that is the project's headline feature,
and the interchangeable engines that drive it, before explaining the user
interface and the choices made to support honest evaluation.

### 3.1 Overview

A single query flows through the system as follows. A user asks a natural
language question. The agent parses it to find the relevant tickers and the
intent, whether this is a single stock judgement, a comparison, or a position
sizing request. It then enters the ReAct loop: it forms a thought about what it
needs, selects a tool, runs it against real data, records the observation, and
repeats until it has enough to answer. It returns a final recommendation with a
confidence level and a rationale. Every thought, action, and observation is
captured in a shared data structure and shown to the user. The loop is
deliberately legible, because the legibility is the point.

### 3.2 Data layer

Market data is retrieved through the yfinance library, which provides historical
prices and company fundamentals without any API key. The data layer wraps
yfinance behind two cached functions, one for price history and one for company
information, with an in memory cache so repeated tool calls within a session do
not refetch. It translates every yfinance failure into one of two clear errors,
one for an invalid ticker and one for a network problem, so the rest of the
system never has to interpret a raw library exception. Exposing the data layer
as plain module level functions has a further benefit for testing, discussed in
3.7: the tests replace these functions with synthetic data, so the whole suite
runs offline.

### 3.3 Tool library

The tool library is the second of the two core deliverables. It is a set of six
financial analysis tools, each a clean function that returns a structured
dictionary with an explicit success flag. They are `get_quote`, a current quote
with the day's change; `get_price_history`, a price history summary over a
requested window; `calculate_technical_indicators`, computing a 14 period
Relative Strength Index with Wilder smoothing, the 50 and 200 period simple
moving averages, and a crossover signal; `get_fundamentals`, returning the price
to earnings ratio, market capitalisation, sector, dividend yield, and similar;
`compare_tickers`, which places two or more tickers side by side; and
`estimate_position_size`, which applies fixed fractional risk sizing.

The tools are held in a registry, each registered with a machine readable
description of its name, purpose, and parameters, so the agent receives a
catalogue it can reason over and so adding a tool is trivial. Tools never raise
an exception to the agent. An unknown tool or a bad argument returns a structured
error instead, which keeps the reasoning loop working when something fails. The
indicators are computed in plain Python rather than a specialised library, which
keeps the maths transparent and testable, appropriate for work that must be read
and assessed.

One design decision was revised during implementation. The tool descriptions
originally gave loose guidance on valid parameter values, and a live language
model duly requested a look back period the data source rejects. Since the
agent's only view of a tool is its description, an underspecified description is
a design fault rather than a model error. The descriptions now enumerate valid
values, and the tool corrects near misses while reporting the correction in its
observation, so the trace stays honest about what it did.

### 3.4 The ReAct loop and its data shape

The reasoning loop is the headline feature. Its design centres on a single
shared data structure so the trace is uniform regardless of which engine
produced it. A result holds the question, the engine used, an ordered list of
steps, and the final answer. Each step records its index, the thought, the
action taken if any, namely the tool and its input, and the observation
returned. The final answer holds the recommendation, a confidence level, and a
rationale. Because every engine emits this same shape, the user interface, the
tests, and this report never have to treat one engine differently from another.
This uniform trace is what makes the advice auditable, and it is also what made
the comparative evaluation in Chapter 5 possible: two very different reasoners
can be scored by the same code because they produce the same structure.

### 3.5 Four engines behind one interface

Sage provides four reasoning engines behind a single interface, named `rule`,
`ollama`, `openai` and `claude`, so the engine is a configuration choice rather
than a structural one. The third is named for the protocol it speaks rather than
for a vendor, because the provider behind it is itself a setting.

The default is the `rule` engine. It is deterministic, needs no key, and runs
anywhere, but crucially it still walks the full ReAct loop rather than
shortcutting to an answer. It scripts sensible thoughts, calls the real tools in
a sensible order against real data, records each observation, and derives a
verdict through a transparent tally of bullish and bearish points, for example
price relative to the long moving average, the crossover signal, whether the
relative strength index is overbought or oversold, and valuation bands. The
rationale is built from the same readings shown in the trace, so the conclusion
is fully traceable.

The second engine drives a local language model through Ollama. The third and
fourth drive hosted models: one speaks the OpenAI compatible chat completions
protocol, which covers a wide range of providers including OpenRouter, Groq and
Together, and one speaks the Anthropic API. All three language model engines share
one hand written loop: the model is prompted to emit a thought and either an
action with its input or a final answer, a standalone parser extracts that from
the model's text, the chosen tool is run, and the observation is fed back. The
loop is capped at a maximum of eight steps to prevent runaway cost and infinite
loops, and malformed model output is recorded honestly in the trace and
recovered from rather than crashing the run. No agent framework is used. The
loop is written by hand on purpose, because that keeps it legible for assessment
and gives full control over the trace.

An important robustness property follows from the engine design. If a requested
language model engine is unavailable, because Ollama is not running or no API
key is set, the system falls back to the rule based engine automatically. Sage
therefore always works out of the box and deploys cleanly to a free host with no
keys at all, while still offering richer reasoning when a model is available.

### 3.6 User interface

Two front ends sit over the same core. A command line interface answers a
question and prints the trace, which is convenient for development and testing.
For demonstration, a web application built with Streamlit is the centrepiece.
The user types a question and the application shows the final recommendation
prominently at the top, with its confidence and rationale, followed by the
reasoning trace as an expandable timeline of thoughts, actions, and
observations, with comparison results rendered as a table. A sidebar selects the
engine, shows which engines are available, and lists the tools. The web
application meets the brief's requirement that a non technical user be able to
interact with the advisor, and it makes the reasoning trace, the core feature,
the visual focus of the interface.

### 3.7 Design for evaluation

Three choices support honest evaluation. First, the data layer is built as
replaceable module level functions, so the test suite substitutes deterministic
synthetic data and runs entirely offline, which makes the tests reliable and
repeatable. Second, the uniform trace structure means the behaviour of any
engine can be inspected and compared directly. Third, and added since the
preliminary report, the evaluation script records the observations alongside
the verdict for every question it runs. This last choice was learned the hard
way, as Chapter 5 describes: when a scoring rule turns out to be wrong, stored
evidence lets the results be rescored locally instead of paying to re-run every
model call. The design does not conceal the simplicity of the rule based
verdict. It makes that reasoning visible so it can be judged on its merits.

---

## 4. Implementation (1684/2500 words)

The prototype implements every component described in Chapter 3. It is written
in Python, version controlled on GitHub, and runs against live market data. This
chapter describes the parts of the implementation that were technically
substantial, the algorithms behind them, and the defects found and fixed while
preparing the system for submission. The codebase is roughly 2,300 lines of
source across the package and its two front ends, with a further 1,400 lines of
tests and 3,000 lines of verification scripts.

### 4.1 The reasoning loop

The core of the system is the hand written ReAct loop shared by the three
language model engines. Each iteration sends the running conversation to the
model, parses the reply, and acts on it. A reply that names an action and its
input causes the named tool to run; the observation is appended to the
conversation as the next user turn and the loop continues. A reply carrying a
final answer ends the loop. A reply that parses as neither is recorded in the
trace with a note saying so, and the model is asked to retry in the required
format; two consecutive unparseable replies end the run with an honest error
rather than an invented answer. The loop is capped at eight steps.

The parser is deliberately separate from the loop and unit tested on its own,
because it is where real model output does the most damage. It accepts the
labelled thought, action, and action input format, tolerates JSON wrapped in
Markdown code fences, tolerates prose after a valid JSON object, and falls back
to treating a free text final answer as a rationale rather than discarding it.
Parsing uses a raw JSON decoder starting at the first opening brace, which
handles nested objects correctly where a non greedy regular expression would
not.

### 4.2 The rule engine's verdict

The rule engine answers a single stock question by calling four tools in
sequence: the quote, the six month price history, the technical indicators, and
the fundamentals. It then derives a verdict by tallying bullish and bearish
points across four dimensions. Medium term performance contributes a point in
either direction when the period return exceeds ten percent, so ordinary noise
does not sway it. Trend contributes a point for price above or below the 200 day
moving average and another for the 50/200 crossover. Momentum contributes a
point when the relative strength index is oversold or overbought. Valuation
contributes a point for a reasonable or a stretched price to earnings ratio, and
a negative multiple counts against. A net of two or more in either direction
gives a buy or a sell; anything closer gives a hold. Confidence is derived from
the margin, not asserted.

The rationale is assembled from the same readings that produced the tally, in
the order they were gathered, so every clause in the explanation corresponds to
something visible in the trace above it. This is the mechanism behind the
project's central claim, and Chapter 5 measures whether it holds.

### 4.3 Handling comparisons honestly

The comparison path scores each candidate on trend, momentum, and valuation, and
names the highest scorer. The original implementation selected the winner with a
maximum over a dictionary, which returns whichever key it encounters first. Two
equally scored candidates therefore produced a confident looking preference
whose direction depended on the order the tickers appeared in the question.
Asking Sage to compare AAPL and MSFT, and asking it to compare MSFT and AAPL,
gave different winners from identical evidence.

For most systems this would be a minor ranking bug. For this one it strikes at
the premise, because the trace showed a preference the trace could not justify.
The implementation now ranks deterministically, detects joint leaders, and reports a
tie as a tie, naming both candidates and stating that the evidence gathered does
not separate them. A less decisive answer is the more useful one when the
alternative is a preference invented by dictionary ordering.

### 4.4 Position sizing and natural language input

The position sizing path answers questions such as how many shares to buy given
an account size, a risk percentage, an entry, and a stop. Reading those four
numbers out of a sentence is the interesting part. The first implementation read
them positionally, which broke as soon as a user omitted one: "risk 2% on AAPL
with a stop at 200" was read with the stop as the entry price, and the system
then complained that no stop had been given. The implementation now reads
labelled values first, matching on the words around each number, and falls back
to positional reading only for values that no label claimed. When no entry price
is stated, the agent fetches the current price with a visible tool call rather
than assuming one, so the assumption appears in the trace.

Two edge cases are handled explicitly because silence would be misleading. A
missing stop is reported as a missing stop, since risk per share cannot be
computed without it and inventing one would be dangerous. A trade whose stop is
too wide for the risk budget yields zero shares, and rather than printing "0
shares" the system explains that the trade does not fit the stated limit and
suggests widening the budget or tightening the stop.

### 4.5 Driving real language models

Connecting the loop to real hosted models produced the most instructive
implementation work, because model behaviour in practice diverges from the clean
protocol the design assumes.

The first problem was native tool calling. Sage parses tool calls out of the
model's text and therefore declares no tools array in its request. Some models,
notably the GPT-OSS family, answer such a prompt by invoking their built in
function calling mechanism anyway, which the provider rejects with an error that
nonetheless carries the attempted call in its payload. Rather than lose the
turn, the engine translates that attempted call back into the textual format the
loop expects. A related wrinkle appeared once that worked: models namespace
their native calls, emitting names like `tool.get_quote` where the registry
holds `get_quote`. The recovery now strips the namespace when the remainder
names a registered tool, and leaves it intact when it does not, so a genuinely
unknown call is still reported rather than quietly rewritten into a different
tool.

The second problem was rate limiting. Free tier providers cap throughput, and a
ReAct loop resends the whole conversation each turn, so a long trace can trip a
cap part way through and lose the run. A refused call now raises a distinct
error and is retried with exponential backoff, honouring the provider's own
retry-after when it sends one, within a floor and a cap. The floor exists
because a live provider once reported a reset window of one millisecond, which
taken literally would fire an immediate retry into a still closed window.
Non rate limit failures are deliberately not retried: waiting does not fix an
invalid key, and pretending otherwise wastes the user's time. When a limit
persists, the system says explicitly that this is a throughput cap and that the
key is valid, because a bare failure message leaves a user unable to tell a
quota problem from a broken credential, and the two need opposite responses.

A third issue surfaced only against a hosted aggregator: it answers with HTTP
200 while carrying an upstream error in the body. That is now detected and
treated as a retryable throughput problem rather than an unexplained response
shape.

### 4.6 Presentation defects

Two defects affected only presentation, and both would have been visible in a
demonstration. The command line interface rendered its trace through a console
that Windows hands to Python as a legacy code page, so the box drawing and
dashes in the trace were replaced by question marks. Standard output is now
reconfigured to UTF-8 at entry, before the rendering library captures the
console encoding. The same fault later killed an evaluation run outright: a
model returned a verdict containing a non breaking hyphen, and the script died
on its final print after every question had been answered and paid for.

### 4.7 Test suite

The suite comprises 87 tests and runs entirely offline. An autouse fixture
replaces the data layer with deterministic synthetic price series and
fundamentals, crafted so that indicator signals and verdicts are predictable:
one ticker is a strong uptrend, one a mild uptrend, one a downtrend. No test
touches the network, so results are repeatable.

Coverage spans four areas. The tool library is tested for correct structure on
known input, correct indicator signals, correct position sizing arithmetic, and
structured errors for invalid tickers, unknown tools, and bad arguments. The
parser is tested against fenced JSON, trailing prose, and malformed output. The
engine is tested for a valid trace, sensible verdicts, order independent
comparisons, declared ties, and the position sizing edge cases. The language
model loop is tested for tool execution, the step cap, malformed output
recovery, rate limit retry and backoff behaviour, and the provider specific
failure modes described in 4.5.

One test file deserves particular mention because it closes a gap the
preliminary report left open. The loop's unit tests drive it through a stub that
returns canned strings, which proves the control flow but bypasses everything
between the loop and a real model. A separate integration test now runs the
engine against a real local HTTP server speaking the provider's protocol, so
sockets, JSON encoding, and the parser meeting text over a wire are all
genuinely exercised.

### 4.8 Verification scripts

Beyond the test suite, the repository holds a set of scripts that verify
properties the tests cannot express, each written so that it fails for the right
reason. They check that comparison ties are declared and order independent, that
the command line interface preserves its characters on a legacy console, that
every registered tool is genuinely reachable by the agent, that the live rule
engine's rationale cites only figures present in its observations, that no API
key is committed to what is a public repository, and that the whole system still
works with every credential removed from the environment, as the deployed
demonstration runs. Several carry negative controls: the secret scanner is run
against a known format fake key to prove it can still detect one, and the
encoding check reproduces the original fault before asserting the fix.

---

## 5. Evaluation (2032/2500 words)

### 5.1 What needed evaluating, and why the test suite was not enough

The preliminary report evaluated Sage with its unit test suite: the tests pass,
therefore the system works. That claim is true but narrow. A passing suite shows
the code does what it was built to do. It says nothing about whether the
reasoning is any good, which is what this project actually claims. A system
could pass every test while producing traces that skip steps, cite figures no
tool returned, or answer questions it has no evidence for.

The evaluation was therefore rebuilt around four measures, each chosen to test a
specific claim the project makes, applied to a fixed set of 15 questions.

**Trace validity** asks whether every step carries a thought and every action
carries the observation it claims to have made. A trace with gaps is not
auditable, which is the premise of the whole system.

**Groundedness** asks whether every figure quoted in the final rationale appears
in a recorded observation. This is the anti-hallucination claim from Chapter 2,
and finance is exactly where a fabricated number does damage.

**Tool appropriateness** asks whether the run called the tools the question
needs, judged against a rule written before the run rather than by reading the
output afterwards and deciding it looks reasonable.

**Correct behaviour** asks whether the system answered when it should have
answered and refused when it should have refused. Three of the fifteen questions
are unanswerable from market data, either because they name no ticker or because
the ticker does not exist. A system that answers these is guessing, so refusing
is the correct result and is scored as such.

The question set is fixed in advance and small enough to inspect by hand. It
covers six single stock judgements, including two phrased with company names
rather than tickers, four comparisons, two position sizing requests, and the
three refusal cases.

### 5.2 Method and its limits

The study runs against deterministic synthetic price data rather than live
market data. This is a deliberate trade. Live data would be more realistic but
would make the numbers unreproducible, since the market moves between runs and
the figures printed in this report could never be checked. Synthetic fixtures
make every result in this chapter reproducible by anyone who clones the
repository. The fixtures are constructed to exercise the range the system is
supposed to handle: a strong uptrend, a mild uptrend, a downtrend, and a roughly
flat series.

Two limits should be stated plainly. First, fifteen questions is a small sample.
It is large enough to expose systematic behaviour and too small to support
statistical claims, and no significance is claimed here. Second, and more
important, there is no ground truth for the underlying question. Nobody knows
whether buying a given stock today is correct, so this evaluation deliberately
does not attempt to measure whether Sage's advice is good investment advice. It
measures whether the reasoning is structurally sound, faithful to its evidence,
and appropriate to the question. Those are the properties the project claims,
and they are the properties that can be honestly assessed.

### 5.3 Results

The rule engine was scored over all fifteen questions, and the `openai` engine
was scored over the same fifteen questions driving minimax-m3, an open weight
model accessed through OpenRouter.

Table 1. Reasoning quality by engine, 15 questions, synthetic fixtures.

| Measure | Rule engine | Language model |
|---|---|---|
| Trace validity | 100.0% | 100.0% |
| Groundedness | 100.0% | 83.3% |
| Tool appropriateness | 100.0% | 91.7% |
| Correct behaviour | 100.0% | 80.0% |
| Mean steps per question | 2.83 | 3.08 |

The rule engine scores perfectly on all four measures. This is less impressive
than it appears and should be read carefully: the rule engine's thoughts are
scripted and its rationale is assembled from the readings it just gathered, so
perfect groundedness is close to structurally guaranteed. What the result
establishes is that the mechanism works as designed, that the tool selection
logic covers the question types, and that no defect breaks the chain between
evidence and explanation. It is a floor, not an achievement.

The language model results are the more informative half. Trace validity is also
perfect, which is a genuine result: across fifteen questions the model never
produced a step that broke the trace structure, and the malformed output
recovery described in Chapter 4 held throughout. The other three measures fall
short, and each gap has a distinct cause.

Groundedness at 83.3% means two rationales in twelve cited a figure that no
observation contained. Inspecting them shows neither is an invented price. In
one, the model computed a drawdown, stating the stock was "roughly 51% off the
52-week high" from an observed low of 95 and high of 210. The arithmetic is
correct, but the figure is derived rather than read, and it is presented with the
same confidence as the measured values around it. In the other, the model
offered an advisory range, suggesting the user wait for the relative strength
index to fall to "50-60", a threshold no tool produced. Both are reasonable
analyst behaviour and neither is a fabrication in the damaging sense. But both
illustrate the limit identified in Chapter 2: grounding a system's inputs in
tool calls does not constrain what the model does with those inputs afterwards.

Correct behaviour at 80.0% comes entirely from the three refusal cases. Asked
what a good investment strategy is, whether the market will rise tomorrow, and
about a non existent ticker, the language model produced a recommendation every
time, including a confident "HOLD" for a ticker that does not exist. The rule
engine refused all three cleanly, because it cannot proceed without a resolvable
ticker. This is the single clearest advantage of the deterministic engine and it
is worth being blunt about: a language model asked a question outside its
evidence will answer anyway, and the architecture around it has to stop that
rather than assume it will not happen.

Tool appropriateness at 91.7% reflects one comparison answered without calling
the comparison tool, the model instead assembling the comparison from individual
lookups. The answer was defensible; the route was not the one the question
called for.

### 5.4 Engine agreement

Because both engines emit the same trace structure, their verdicts can be
compared directly on identical evidence.

Table 2. Verdict agreement between the two engines, 12 answerable questions.

| Outcome | Count | Share |
|---|---|---|
| Same verdict | 3 | 25.0% |
| Different verdict | 9 | 75.0% |

Agreement of 25.0% looks alarming and requires care to interpret, because the
raw figure overstates the disagreement in two ways.

First, the comparison is on normalised verdict strings, and the two engines
phrase themselves differently. The rule engine returns "PREFER AAPL"; the model
returns "AAPL is the better buy". These are counted as disagreements by the
scoring code and are plainly the same decision. Of the nine disagreements, four
are of this kind.

Second, the two position sizing questions are counted as disagreements because
the rule engine returns a share count while the model returns a buy
recommendation that contains the same share count. Again the substance matches
and the form does not.

That leaves three disagreements that are real. On three single stock questions
the rule engine said BUY where the model said HOLD. Reading the traces, the
cause is consistent: the fixtures produce very high relative strength index
readings, and the model treats an extreme overbought reading as a reason to wait
regardless of trend strength, while the rule engine's tally lets a strong trend
and a reasonable valuation outweigh a single overbought signal. Neither is
wrong. They weight the same evidence differently, which is exactly what one
should expect from a fixed scoring rule versus a language model, and the fact
that the disagreement can be located and explained at all is a direct
consequence of both engines exposing their reasoning.

The honest conclusion is that the headline agreement figure of 25.0% mostly
measures the crudeness of the verdict normalisation rather than substantive
disagreement, and that a stricter reading puts real disagreement at three cases
in twelve. This is a limitation of the measure, and it is reported rather than
quietly corrected because the raw figure is what the scoring code produces.

### 5.5 The measurement problem

The most instructive part of this evaluation was not the results but what it
took to trust them. The groundedness scorer produced four different figures for
the same system before it was correct, and every one of them looked plausible
enough to publish.

It first reported 75% because it compared numbers as strings, so an observation
holding `10000.0` did not match a rationale saying `10000`. Corrected to compare
values, it reported a different figure because an observed `-48.59` did not match
a rationale saying "down 48.59%", where the sign is carried by the word. Corrected
to compare magnitudes, it reported 66.7% because it counted indicator names such
as "the 200-day average" and standard thresholds such as "RSI below 70" as data
readings requiring grounding. The fix for that introduced a fourth fault: the
pattern removing those phrases consumed the "93" from "RSI 93.93" and left ".93"
behind, inventing figures that matched nothing. Applied to the language model,
an early version of the scorer reported groundedness of 16.7%, a number that
would have appeared in this report as evidence of severe hallucination when it
was mostly evidence of the model rounding its figures in prose.

The lesson generalises beyond this project. An automated evaluation is itself a
program that can be wrong, and a wrong evaluation fails silently: it produces a
number, the number looks reasonable, and nothing in the process objects. The
scorer is now covered by its own verification with controls in both directions.
It must catch a fabricated figure, and it must accept a faithful one, including
rounded values, sign carried by words, and legitimate domain vocabulary. Without
the second half, a scorer that flagged everything would have looked rigorous.

### 5.6 Successes

The explainable reasoning loop works end to end and produces a uniform,
inspectable trace across four engines, which is the project's primary claim. The
rule engine runs with no credentials against real market data and produces
traces whose every figure is traceable to an observation, verified against live
data as well as fixtures. The tool library is clean and registry driven, and all
six tools are reachable by the agent. The system degrades sensibly: unavailable
engines fall back, rate limits are retried and then explained, malformed model
output is recorded and recovered from, and unanswerable questions are refused
rather than guessed at. The test suite of 87 tests runs offline and covers the
tools, the parser, the loop, and the provider specific failure modes.

### 5.7 Failures and limitations

The rule engine's verdict is a simple tally. It is explainable by design, not a
sophisticated trading model, and its conclusions should be read in that light.
The indicator set is small: the relative strength index and two moving averages,
without MACD, Bollinger bands, or volume analysis. The weights in the tally were
chosen by judgement rather than derived from any backtest, which means the
verdict is defensible as a transparent heuristic and not as an empirically
tuned model.

The language model engine answers questions it should refuse, which is the most
serious behavioural finding in this chapter. The refusal logic currently lives in
the rule engine's ticker extraction, not in the loop, so a model that decides to
answer anyway is not stopped.

yfinance is an unofficial data source that can rate limit or change shape, and
the live demonstration depends on it. During development its dividend yield
convention had already changed, which was detected and handled, but it
illustrates the fragility.

The evaluation itself has the limits set out in 5.2: fifteen questions, no
ground truth for investment quality, and synthetic data chosen for
reproducibility over realism. The agreement measure normalises verdicts crudely,
as 5.4 describes.

### 5.8 Extensions

The clearest next step follows from 5.7: move refusal into the loop, so that any
engine must ground a recommendation in at least one successful tool observation
before it can offer one. That single change would close the largest behavioural
gap found here and would apply to every engine at once.

Beyond that, the decision logic could be enriched with more indicators and a
weighted scoring model with backtest derived weights, which would improve the
verdict without sacrificing the visible trace. The data layer could gain a disk
cache with expiry and a fallback source to reduce reliance on a single unofficial
feed. Groundedness could be enforced at generation time rather than only measured
afterwards, by having the loop reject a final answer containing figures absent
from its observations. And the question set could be enlarged and scored by
multiple independent judges, which would turn the indicative numbers in this
chapter into something closer to a benchmark.

---

## 6. Conclusion (574/1000 words)

Sage set out to show that an investment advisor can reason step by step over
real financial tools and expose the whole of that reasoning to the user. That
was achieved. The system answers ordinary investment questions, whether to buy a
stock, how two compare, how many shares to size, by forming a thought, calling a
tool, observing a real result, and continuing until it can recommend, with every
step visible. Four interchangeable engines drive the same loop and emit the same
trace, so the reasoning can be inspected and compared regardless of what produced
it.

The evaluation supports the central claim with a caveat worth stating clearly.
The deterministic engine produced structurally valid, fully grounded traces on
every question in the study. The language model engine matched it on structure
but not on discipline: it cited derived figures alongside measured ones, and it
answered three questions it had no evidence for. That distinction is the most
useful thing this project found. Tool calling architecture constrains where a
system's evidence comes from; it does not constrain what a model does with that
evidence once it has it. The literature on ReAct claims reduced hallucination
rather than eliminated hallucination, and these results are a small piece of
concrete support for the narrower reading.

A second theme emerged from the process rather than the product. Evaluating
reasoning quality automatically means writing a program to judge another
program, and that judge can be wrong in ways that are invisible. The
groundedness scorer here reported four different figures for the same system
before it was right, and each intermediate figure was plausible enough to have
been published. Had the first number been trusted, this report would have stated
that a working system hallucinated in a quarter of its answers. The safeguard
that caught it was insisting the scorer prove itself in both directions, against
fabricated figures it must catch and faithful ones it must accept. Any automated
evaluation of a generative system needs that discipline, and it is not the
default.

The transparency argument also proved to have a practical dimension beyond
trust. Because both engines expose their reasoning in the same structure, their
disagreements could be located and explained rather than merely counted. Three
genuine disagreements turned out to rest on how much weight an overbought
momentum signal should carry against a strong trend, which is a legitimate
analytical difference rather than an error by either engine. An opaque system
would have presented one verdict and concealed that another reasonable process
disagreed. Visible reasoning makes a system's own variability measurable, which
matters for a tool meant to inform a decision rather than make it.

Sage remains a feasibility prototype and should not be mistaken for something
else. It does no risk profiling, holds no portfolio context, runs no backtest,
and its verdict is a transparent tally rather than a validated model. It is not
financial advice. What it demonstrates is narrower and, for the question this
project asked, sufficient: that grounding every figure in an auditable tool call
and showing the user the entire chain of reasoning is both implementable and
worth the constraint it imposes. The most valuable extension identified here
follows directly from the evaluation, which is to move the refusal rule into the
loop so that no engine can recommend without evidence. That the next step comes
out of a measurement rather than a guess is itself an argument for having built
the measurement.

---

## References

- Aguda, T., Siddiqui, S., Lopez-Lira, A., Shah, S. and Chava, S. (2024) *Large Language Model Adaptation for Financial Sentiment Analysis*. arXiv:2401.14777.
- Jiang, Z., Xu, D. and Liang, J. (2017) *A Deep Reinforcement Learning Framework for the Financial Portfolio Management Problem*. arXiv:1706.10059.
- Liu, X., Wang, G. and Zha, D. (2023) *FinGPT: Democratizing Internet-scale Data for Financial Large Language Models*. arXiv:2307.10485.
- Schick, T., Dwivedi-Yu, J., Dessi, R., Raileanu, R., Lomeli, M., Zettlemoyer, L., Cancedda, N. and Scialom, T. (2023) *Toolformer: Language Models Can Teach Themselves to Use Tools*. arXiv:2302.04761.
- Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., Chi, E., Le, Q. and Zhou, D. (2022) *Chain of Thought Prompting Elicits Reasoning in Large Language Models*. Advances in Neural Information Processing Systems, 35.
- Wu, S., Irsoy, O., Lu, S., Dabravolski, V., Dredze, M., Gehrmann, S., Kambadur, P., Rosenberg, D. and Mann, G. (2023) *BloombergGPT: A Large Language Model for Finance*. arXiv:2303.17564.
- Yang, H., Liu, X. and Wang, C. D. (2023) *FinGPT: Open Source Financial Large Language Models*. arXiv:2306.06031.
- Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K. and Cao, Y. (2022) *ReAct: Synergizing Reasoning and Acting in Language Models*. arXiv:2210.03629.
