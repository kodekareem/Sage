# Gates: CM3020 final report

OWNS: report/**, scripts/**, GATES.md

Scope: Produce the six-chapter CM3020 final report for Sage, backed by a real
evaluation study rather than only a passing test suite, written in the author's
own voice without AI-slop patterns, inside every stated word limit, plus the
3-5 minute video script.

- [ ] G0: this ledger states outcomes that can fail
  CHECK: node "C:/Users/pc/.claude/skills/unlazy/scripts/gate-lint.mjs" GATES.md
  EXPECT: LINT OK
  EVIDENCE: pending

- [ ] G1: the evaluation harness produces measured results over a fixed question
      set, scoring trace validity, groundedness and tool appropriateness
  CHECK: python scripts/run_evaluation.py --offline --out report/data
  EXPECT: EVALUATION COMPLETE
  EVIDENCE: pending

- [ ] G1b: the groundedness scorer catches a fabricated figure while accepting
      indicator names and standard thresholds as the vocabulary they are
  CHECK: python scripts/verify_scorer.py
  EXPECT: SCORER VERIFICATION PASSED
  EVIDENCE: pending

- [ ] G1c: the rule-vs-LLM agreement study is measured with the corrected scorer
  EVIDENCE: pending

- [ ] G2: every figure quoted in the report is reproduced from the measured
      results file rather than typed by hand
  CHECK: python scripts/verify_report_figures.py
  EXPECT: REPORT FIGURES VERIFICATION PASSED
  EVIDENCE: pending

- [ ] G3: each chapter is within its stated word limit and the whole report is
      within 10500 words, excluding references, headings and captions
  CHECK: python scripts/verify_report_limits.py
  EXPECT: WORD LIMIT VERIFICATION PASSED
  EVIDENCE: pending

- [ ] G4: the report contains none of the banned AI-slop vocabulary or sentence
      patterns from the no-ai-slop skill
  CHECK: python scripts/verify_no_slop.py
  EXPECT: SLOP SCAN PASSED
  EVIDENCE: pending

- [ ] G5: all six required chapters are present in order, with the project
      template number, the public repository link, and a reference list whose
      entries are each cited in the body
  CHECK: python scripts/verify_report_structure.py
  EXPECT: REPORT STRUCTURE VERIFICATION PASSED
  EVIDENCE: pending

- [ ] G6: the code still passes its full suite after the report work
  CHECK: python -m pytest -q
  EXPECT: /^\d+ passed/m
  EVIDENCE: pending

- [ ] G7: no API key or other secret is committed anywhere in the repository
  CHECK: python scripts/verify_no_secrets.py
  EXPECT: SECRET SCAN PASSED
  EVIDENCE: pending

- [ ] G8: the report's factual claims about the codebase match the codebase
      (test count, tool count, engine names, module sizes)
  CHECK: python scripts/verify_report_claims.py
  EXPECT: REPORT CLAIMS VERIFICATION PASSED
  EVIDENCE: pending

- [ ] G9: the video script exists, is timed within 3-5 minutes at a measured
      speaking rate, and records the no-AI-voice and no-speed-up constraints
  CHECK: python scripts/verify_video_script.py
  EXPECT: VIDEO SCRIPT VERIFICATION PASSED
  EVIDENCE: pending

- [ ] G10: the report reads as the author's own writing rather than generated
      prose, judged by hand against the preliminary report, with limitations
      stated honestly rather than the project oversold
  EVIDENCE: pending
