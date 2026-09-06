# Gates: CM3020 final report

OWNS: report/**, scripts/**, GATES.md

Scope: Produce the six-chapter CM3020 final report for Sage, backed by a real
evaluation study rather than only a passing test suite, written in the author's
own voice without AI-slop patterns, inside every stated word limit, plus the
3-5 minute video script.

- [x] G0: this ledger states outcomes that can fail
  CHECK: node "C:/Users/pc/.claude/skills/unlazy/scripts/gate-lint.mjs" GATES.md
  EXPECT: LINT OK
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=5143c1258a9df6b9ef4e5513e93ec0122f63bb28b9081fae1e4d229522fb401d; output-bytes=151

- [x] G1: the evaluation harness produces measured results over a fixed question
      set, scoring trace validity, groundedness and tool appropriateness
  CHECK: python scripts/run_evaluation.py --offline --out report/data
  EXPECT: EVALUATION COMPLETE
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=fc2f0a516d03b05c22aa9655575db0fbbd5070f5d8e3916ae0901981ff833c79; output-bytes=1062

- [x] G1b: the groundedness scorer catches a fabricated figure while accepting
      indicator names and standard thresholds as the vocabulary they are
  CHECK: python scripts/verify_scorer.py
  EXPECT: SCORER VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=8e5211bb0bb08e8712f7d093ac2bef75edeaa4bdc6025a6449bc5408f76bd0d1; output-bytes=423

- [x] G1c: the rule-vs-LLM agreement study is measured with the corrected scorer
  CHECK: python scripts/verify_agreement_measured.py
  EXPECT: AGREEMENT STUDY VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=19cc593d237e9b037bde69dbcc01c0023916da3b45477376362aee24de1bc248; output-bytes=161

- [x] G2: every figure quoted in the report is reproduced from the measured
      results file rather than typed by hand
  CHECK: python scripts/verify_report_figures.py
  EXPECT: REPORT FIGURES VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=e25b40bcd5b1b1b1b1d1dc20b1ddb2859bf27e3a967123b64cd4a667895bcbda; output-bytes=97

- [x] G3: each chapter is within its stated word limit and the whole report is
      within 10500 words, excluding references, headings and captions
  CHECK: python scripts/verify_report_limits.py
  EXPECT: WORD LIMIT VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=6ebde34bc47f16911f82067d61e08c3844a46d0c182820e705ee6b5032d26f67; output-bytes=448

- [x] G4: the report contains none of the banned AI-slop vocabulary or sentence
      patterns from the no-ai-slop skill
  CHECK: python scripts/verify_no_slop.py
  EXPECT: SLOP SCAN PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=c25e5394360b6c0a72f5f4aafc220d201a84f076b2c22e85684da1caf009feb1; output-bytes=158

- [x] G5: all six required chapters are present in order, with the project
      template number, the public repository link, and a reference list whose
      entries are each cited in the body
  CHECK: python scripts/verify_report_structure.py
  EXPECT: REPORT STRUCTURE VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=8c78c6194244a0ff1dfc9f911e8226c837f247c671737f90170395abd51c9b89; output-bytes=216

- [x] G6: the code still passes its full suite after the report work
  CHECK: python -m pytest -q
  EXPECT: /^\d+ passed/m
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=b548424eed9ca2ce27116873a33da38d71c8b01abb96a13106bb7054a36284a3; output-bytes=182

- [x] G7: no API key or other secret is committed anywhere in the repository
  CHECK: python scripts/verify_no_secrets.py
  EXPECT: SECRET SCAN PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=a6087d3d2692c0657791a6080b1672fe962bd884b3a70d02b254f8f1def4586b; output-bytes=113

- [x] G8: the report's factual claims about the codebase match the codebase
      (test count, tool count, engine names, module sizes)
  CHECK: python scripts/verify_report_claims.py
  EXPECT: REPORT CLAIMS VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=b5e7ef2a777f833e6bb071d3d4ea9354ae93910992ff951f5beafc924e989e1a; output-bytes=159

- [x] G9: the video script exists, is timed within 3-5 minutes at a measured
      speaking rate, and records the no-AI-voice and no-speed-up constraints
  CHECK: python scripts/verify_video_script.py
  EXPECT: VIDEO SCRIPT VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=dceca196566bb6465241fcb3d741951d721cff4ab5596cf6f87de42f7ef86d22; output-bytes=176

- [x] G10: the report reads as the author's own writing rather than generated
      prose, judged by hand against the preliminary report, with limitations
      stated honestly rather than the project oversold
  EVIDENCE: Read the full report against the preliminary submission and judged
    by hand. Voice: chapters 1-3 keep the preliminary report's register and much
    of its wording, so the final report reads continuously with the draft a
    marker has already seen; chapters 4-6 were written new in the same plain,
    first-person-light style with no bullet lists in the body. Rhythm measured
    rather than assumed: 393 sentences, mean 21.0 words, standard deviation 10.5,
    so no uniform sentence shape. Zero em dashes. The mechanical slop scan (G4)
    passes with a negative control proving the matcher works. Honesty: the report
    states that the rule engine's perfect scores are close to structurally
    guaranteed and calls them "a floor, not an achievement"; reports the LLM
    answering three questions it should have refused; reports the 25.0% agreement
    figure as mostly an artefact of crude verdict normalisation rather than
    quietly correcting it; and devotes section 5.5 to the four wrong groundedness
    figures the scorer produced before it was right, including the 16.7% that
    would have been published as evidence of hallucination. Limitations in 5.7
    name the small sample, the absent ground truth, the judgement-chosen scoring
    weights and the unofficial data source. The project is not oversold: it is
    called a feasibility prototype and explicitly not financial advice.

- [x] G11: the report is typeset as a PDF and delivered to the user's Downloads
  CHECK: python scripts/verify_pdf_delivered.py
  EXPECT: PDF DELIVERY VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=8caa235477f7/74 entries; EXPECT=matched; output-sha256=2cd551cc9fc606170bf8474423e0c1fa1193f94752fa4b74863b44c2f41abb93; output-bytes=117

- [x] G12: each chapter title states that chapter's word count against its limit,
      as the submission form requires, and the stated counts match the measured
      body text rather than being typed by hand
  CHECK: python scripts/verify_chapter_counts.py
  EXPECT: CHAPTER COUNT VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=90d2e5011cab/74 entries; EXPECT=matched; output-sha256=e45ab6c258cb896b47a48cc9fdbbf84c7ff340f13d190b3b051e223196211d54; output-bytes=384

- [x] G13: the OpenAI-compatible engine is named for the protocol it speaks
      rather than one vendor, so the app, the report and the evaluation agree
      on what it is
  CHECK: python scripts/verify_engine_naming.py
  EXPECT: ENGINE NAMING VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=90d2e5011cab/74 entries; EXPECT=matched; output-sha256=8186ccdc76b74d4538fce86afb44107ae7c9be93f7477f09cbe66525d4f8f00a; output-bytes=422

- [x] G14: every numeric claim spoken in the video script matches the measured
      data and the live code, so the narration cannot state a figure that has
      since moved
  CHECK: python scripts/verify_video_claims.py
  EXPECT: VIDEO CLAIMS VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=90d2e5011cab/74 entries; EXPECT=matched; output-sha256=4766040c16a078ef682440a61b9a54dfcb759e8bbdb44c7c657bd208f83e4309; output-bytes=250

- [x] G15: the evidence the report quotes appears verbatim in the stored results,
      and superseded scorer readings are presented as superseded
  CHECK: python scripts/verify_report_quotes.py
  EXPECT: REPORT QUOTES VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=90d2e5011cab/74 entries; EXPECT=matched; output-sha256=f476db49b9c0e8b8172a98616877e7357e908529d32705e116ae79588d1c56f8; output-bytes=154

- [x] G16: every verification script in the repository is executed and passes,
      so a summary line can never report success while a check is failing
  CHECK: python scripts/verify_all_checks.py
  EXPECT: ALL CHECKS VERIFICATION PASSED
  EVIDENCE: exit=0; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\pc\sage-project; path=90d2e5011cab/74 entries; EXPECT=matched; output-sha256=f404345d64f9b7f13eea63a6a3a4ed9a01ff52ebc8b9b6ed4ccfda988aa16abd; output-bytes=822

- [ ] G17: the sidebar offers every reachable engine and hides only unreachable
      ones, never hiding the default, and the report still describes the full
      engine set that remains in the code
  CHECK: python scripts/verify_engine_visibility.py
  EXPECT: ENGINE VISIBILITY VERIFICATION PASSED
  EVIDENCE: pending

- [ ] G18: the report, README and video script describe the interface the app
      actually presents, so a stage direction is never read aloud over footage
      that contradicts it
  CHECK: python scripts/verify_ui_descriptions.py
  EXPECT: UI DESCRIPTION VERIFICATION PASSED
  EVIDENCE: pending
