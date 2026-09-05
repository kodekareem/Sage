# Gates: Sage pre-submission audit fixes

OWNS: sage/**, tests/**, run.py, app.py, scripts/**, README.md

Scope: Fix the four audit findings blocking the CM3020 final submission — silent
order-dependent comparison ties, CLI cp1252 character mangling, the two LLM
engines never having been run against a real model, and two of the six library
tools never being reachable by any engine — leaving the full test suite green
and the project genuinely submission-ready.

- [x] G0: this ledger states outcomes that can fail
  CHECK: node "C:/Users/pc/.claude/skills/unlazy/scripts/gate-lint.mjs" GATES.md
  EXPECT: LINT OK
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=497e1b1fd83aa8c97730b46891c668bfc53799ce4cdaa54b7d44728bf3aca6e2; output-bytes=150

- [x] G1: a tied comparison is reported honestly and is order-independent
  CHECK: python scripts/verify_ties.py
  EXPECT: TIE VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=e92f2c64b3deef58ab49aef57e3bf8ead4f98c1b79423c70ae93a1adef34dd9c; output-bytes=131

- [x] G2: the CLI emits its non-ASCII characters intact on a cp1252 console
  CHECK: python scripts/verify_encoding.py
  EXPECT: ENCODING VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=020d363a5be126aa0fb64e4dd90765837cffa68b96551a2051dab7974ee9c474; output-bytes=163

- [x] G3: every one of the six registered tools is reachable by the rule engine
  CHECK: python scripts/verify_tool_coverage.py
  EXPECT: TOOL COVERAGE VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=1ee6dd54f9fcbdea95c4bfcd09b65219599b2c2c083d199bb694204dd7b3bd3e; output-bytes=261

- [x] G4: the ReAct loop drives a real served LLM through real tool calls to a verdict
  CHECK: python scripts/verify_llm_engine.py --engine groq
  EXPECT: LLM ENGINE VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=9043b6580ec6fe61f5acd8783ecaae239c24c7e5141b65a895a6aa5e9308c34b; output-bytes=855

- [x] G4b: the LLM engine's real HTTP/socket path is proven, independent of any model
  CHECK: python -m pytest tests/test_llm_http.py -q
  EXPECT: /^\d+ passed/m
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=8138bed04e912d9f6fc1ab44c4fe0b39c0f5e2abfbccb16668b9c980b0ab8e73; output-bytes=100

- [x] G5: the full test suite passes with no regressions and covers the new behaviour
  CHECK: python -m pytest -q
  EXPECT: /^\d+ passed/m
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=9d49837993fa92f509a4c308041213b5ae6aad872d482488a795930b35b83cb1; output-bytes=182

- [x] G6: the live rule engine still produces a grounded end-to-end trace
  CHECK: python scripts/verify_live.py
  EXPECT: LIVE VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=dd64494f8075b8e20c0fd92ad54c339b7ab7c8c6a800632f63edf4df46b8acb5; output-bytes=153

- [x] G7: no API key or other secret is committed anywhere in the repository
  CHECK: python scripts/verify_no_secrets.py
  EXPECT: SECRET SCAN PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=12b26d4e5e6c5674c16b3d995497d0329c1cd97981fd6dbe634520a7af978993; output-bytes=113

- [x] G8: the app still works with no keys at all, as the deployed demo will
  CHECK: python scripts/verify_no_key_fallback.py
  EXPECT: NO-KEY FALLBACK VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=b955b7f88c72d370c078ac77f35ff9a8117f539b696b2664db4301b4086e4508; output-bytes=126

- [x] G9: remaining submission work is stated plainly to the user rather than
      implied complete (report chapters 4-6, video, repo URL)
  EVIDENCE: Audited the working code against the CM3020 final-submission brief
    and reported to the user, in the reply accompanying this commit, that the
    CODE is submission-ready (54 tests, 10 runnable gates met, all four engines
    working, verified against live market data and a real served LLM) while
    these deliverables are NOT done and are not implied to be: (1) report ch.4
    Implementation, ch.5 Evaluation, ch.6 Conclusion — unwritten; ch.2/ch.3 need
    revising from the preliminary report toward the 2500/2000-word limits;
    (2) the 3-5 minute video with the user's own spoken narration — not made;
    (3) `git push` — SINCE RESOLVED: at the time of this gate both commits were
    local only; main was later fast-forwarded and pushed, and the public repo
    at github.com/kodekareem/Sage was verified to serve them (remote HEAD
    8981c63, private=false, raw files 200, no key in any published file or in
    history); (4) evaluation depth — no rubric-scored question
    set and no rule-vs-LLM agreement study, which the user was told is the main
    gap for ch.5's five marking criteria. Report word limits and the video's
    "no AI voices, not sped up" constraint were restated rather than assumed.

- [x] G10: a rate-limited (429) LLM call is retried with backoff and succeeds,
      rather than failing the run on the first refusal
  CHECK: python -m pytest tests/test_rate_limit.py -q
  EXPECT: /^\d+ passed/m
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=7c9e9deedbb6c400d1040b5fce3bb59f0f65aeaa9d41c9fe15c0f5c2fe13b7fe; output-bytes=101

- [x] G11: the verify script names a rate limit as a rate limit, and never
      reports it as a bad key (and still reports a bad key as a bad key)
  CHECK: python scripts/verify_rate_limit_reporting.py
  EXPECT: RATE LIMIT REPORTING VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=089fd99dd84a065ef81fe3ad94c3f193f438538053d2044c1f32d1f93c174935; output-bytes=276
