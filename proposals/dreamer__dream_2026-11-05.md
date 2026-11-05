<!-- proposal by dreamer at 2026-11-05 06:10:07Z; target: dream_2026-11-05.md; reason: daily dream report 2026-11-05 (first run); link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBGFBWLDVsP3Lv4Cifvhe6GT; status: open -->
# Dream report 2026-11-05 (first run, skill draft fallback: qfacs-dream skill not loaded)
Scope: memory store v1-v14, 5 open proposals, 4 threads (setup, curator, review prior work, this one), project chat 2026-10-20..2026-11-05 06:07Z.

| ID | pri | target | change | evidence | uplift |
|---|---|---|---|---|---|
| D1 | HIGH | decisions/data/results/status/INDEX | Merge the 5 open proposals from "Review prior qFACS workbook work" (Mase's 12 scoping answers, Excel v1 baseline, input formats, build plan, index pointer). Index item via coordinator. | proposals/review-prior-qfacs-workbook-work__*; msg ...B6cVH9VPUt24hvTMMzC2JN2 | Mase's answers exist only in a proposal; any new thread would re-ask them. |
| D2 | HIGH | decisions.md | Add "proposed analysis defaults, awaiting Mase" (Bmax + top-dose ABC + not-saturated flag; valency default 1; no-Ab then isotype-ABC subtraction; DLL3 isotype mismatch). | proposals/dreamer__decisions.md; msg ...BXkS8uJRi9P43NcnSqQJZAs | Stops threads re-deriving or treating them as decided. |
| S1 | MED | status.md | Rewrite: ruleset done; skills still not uploaded; build plan awaiting review; 5 versions not on GitHub. | proposals/dreamer__status.md; msg ...B8VFNGPiKy3YWpwVhojbkzr | status.md still asks Mase for a ruleset he already set. |
| T1 | MED | threads.md | Add "Review prior qFACS workbook work"; mark setup done, curator idle. | proposals/dreamer__threads.md | Registry missing the only active work thread. |
| L1 | MED | lessons.md | 3 lessons: qfacs- skill prefix; don't test-push protected branch; A8 PDF has no text layer. | proposals/dreamer__lessons.md | lessons.md is empty; avoids repeat slow lookups. |
| A1 | LOW | data.md | Fix stale "repo empty" line, note A8 PDFs identical + scanned, pointer to REVIEW_excel_v1.md. | proposals/dreamer__data.md | data.md tells threads to grep an unsearchable PDF. |
| O1 | LOW | process | Curator: after applying, open one PR syncing local versions to `memory` (sync reports AHEAD 5, now more). | memsave.py sync | Keeps approved store current. |

Notes / conflicts:
- INDEX says "project-specific rules: none yet", but kit rules (30-min check-in, no helper agents, short replies) are listed as standing rules; coordinator flagged this to Mase (chat 22:09Z). No change proposed; Mase's call.
- Build plan has two links (artifact/MKhhyuQpTo8xxKecP1LEhv and code/artifact/a4933f53-...); likely same doc. Verify before indexing.
- Index drift: live index matches INDEX.md (visual compare). verify: CLEAN.
- Structure: all files < 4 KB; no splits needed.

Not reviewed: PR #1 diff, prior_work/ files, the build plan doc contents, PDFs.

approve with: apply D1,L2  (e.g. "apply D1,D2,S1,T1,L1")
