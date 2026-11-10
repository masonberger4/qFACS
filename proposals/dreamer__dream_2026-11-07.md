<!-- proposal by dreamer at 2026-11-07 06:04:37Z; target: dream_2026-11-07.md; reason: daily dream report 2026-11-07 (quiet day); link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBPgvKtpcNb2BqTfihhMvG4G; status: open -->
# Dream report 2026-11-07 (qfacs-dream skill)
Scope: memory v1-v50, all proposals, threads active since 2026-11-06 06:08Z (none besides this run), project chat to 06:03Z, origin/main git log.

Quiet day: no new threads, no Mase messages, no new commits on main since PR #5 (2026-11-05). No new facts to capture.

| ID | pri | target | change | evidence | uplift |
|---|---|---|---|---|---|
| S1 | HIGH | status.md | (open since 11-06, unchanged) Rewrite: phases 1-3 shipped, PRs #1-#5 merged, waiting on Mase's edited setup + .fcs. | proposals/dreamer__status.md | status.md is now 2 days stale and still says build plan awaits review. |
| D1 | HIGH | decisions.md | (open since 11-06, unchanged) Exp2290 layout, F/P 1.24/1.2/1.357, how-to note rule, cloud runs. Absorbs qfacs-build-thread__decisions. | proposals/dreamer__decisions.md | owner answers otherwise re-asked. |
| R1 | HIGH | results.md | (open since 11-06, unchanged) Confirmed run numbers + gMFI biex fix (0.2%). Absorbs qfacs-build-thread__results. | proposals/dreamer__results.md | results.md still shows placeholder-F/P numbers. |
| D2 | HIGH | decisions.md | (open since 11-06, unchanged) AWAITING list: isotype in PE units when F/P blank (never answered), QC defaults 1000 / 0.98 / k=5. | proposals/dreamer__decisions.md | keeps Claude recs separate from Mase decisions. |
| O2 | MED | process (dream skill) | New: when a run finds no new activity, post one line ("no new activity; N proposals still open, apply with ...") instead of a fresh top-5. | this run; 10 items unanswered 24 h | fewer notifications for Mase. |
| A1, T1, L1, L2, I1, O1 | MED/LOW | various | (open since 11-06, unchanged) see dream_2026-11-06. | proposals/dreamer__*.md | as before. |

Conflicts / checks:
- No reversals of Mase decisions. No lot values hard-coded in qfacs/ (no code changes since last check).
- Index drift: live index matches INDEX.md. verify: only scratch/dreamer/cursor.json flagged (own scratch, edited directly; expected). sync: AHEAD 9 (curator PR still pending).
- Still open for Mase: confirm `memory` ruleset visually (since 11-04).
- Open proposals from other threads: qfacs-build-thread__decisions + __results (11-05), folded into D1/R1.

Not reviewed: PR diffs, build plan doc, xlsx contents, prior_work/, uploads/hearth/.

approve with: apply D1,L2  (e.g. "apply S1,D1,D2,R1,A1,T1,L1,O2")
