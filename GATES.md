# Gates: Sage pre-submission audit fixes

OWNS: sage/**, tests/**, run.py, scripts/**

Scope: Fix the four audit findings blocking the CM3020 final submission — silent
order-dependent comparison ties, CLI cp1252 character mangling, the two LLM
engines never having been run against a real model, and two of the six library
tools never being reachable by any engine — leaving the full test suite green.

- [x] G0: this ledger states outcomes that can fail
  CHECK: node "C:/Users/pc/.claude/skills/unlazy/scripts/gate-lint.mjs" GATES.md
  EXPECT: LINT OK
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=48630b7361dd44ee870917b12c3d19b9d7bdea738aaca16bb04d4cab83b772d2; output-bytes=8

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

- [ ] G4: the LLM ReAct loop is proven against a real served model, not a stub
  EVIDENCE: pending

- [x] G4b: the LLM engine's real HTTP/socket path is proven, independent of any model
  CHECK: python -m pytest tests/test_llm_http.py -q
  EXPECT: /^\d+ passed/m
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=694136e7b402a5dbfaa21c478069246c5167948edc5fdb27ecc84727d40cd94c; output-bytes=100

ABANDON: G4 No LLM backend exists on this machine: Ollama is not installed (absent from PATH, nothing on :11434) and ANTHROPIC_API_KEY is unset, so no real model can be served here. Fabricating this evidence is not an option. Mitigation delivered instead: (a) scripts/verify_llm_engine.py runs the loop against a real Ollama or Anthropic backend and fails loudly rather than skipping when neither is reachable, so the user can produce this evidence in one command; (b) G4b proves the real HTTP/socket/JSON path and malformed-output recovery via a local server. HANDOFF TO USER: install Ollama, run `ollama serve` and `ollama pull llama3.2`, then run `python scripts/verify_llm_engine.py`. Until that is done, the report must NOT claim the loop is verified end-to-end on all three engines; it should say the rule engine is verified against live market data, the LLM loop is verified through its HTTP path and unit tests, and note that quality against a live model is untested.

- [x] G5: the full test suite passes with no regressions and covers the new behaviour
  CHECK: python -m pytest -q
  EXPECT: /^\d+ passed/m
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=afe062272c6ade28fda200ecda135e52c00c4dc224e39aaaea1fc81cd1594c01; output-bytes=101

- [x] G6: the live rule engine still produces a grounded end-to-end trace
  CHECK: python scripts/verify_live.py
  EXPECT: LIVE VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=dd64494f8075b8e20c0fd92ad54c339b7ab7c8c6a800632f63edf4df46b8acb5; output-bytes=153
