<!-- proposal by dreamer at 2026-11-08 06:04:26Z; target: dream_2026-11-08.md; reason: daily dream report 2026-11-08 (quiet day 2); link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBWr3RfevHLJ6qhUyLgfcKDU; status: open -->
# Dream report 2026-11-08 (qfacs-dream skill)
Scope: memory v1-v51, all proposals, threads active since 2026-11-07 06:08Z (none besides this run), project chat to 06:03Z, origin/main and origin/memory git logs.

Second quiet day: no new threads, no Mase messages (last one 2026-11-05 21:38Z), no new commits on main since PR #5, no reply to the 11-06 or 11-07 dream threads. No new facts.

| ID | pri | target | change | evidence | uplift |
|---|---|---|---|---|---|
| S1 | HIGH | status.md | (open since 11-06) Rewrite: phases 1-3 shipped, PRs #1-#5 merged, waiting on Mase's edited setup + .fcs. | proposals/dreamer__status.md | status.md is now 3 days stale; any new thread reads the wrong state. |
| D1 | HIGH | decisions.md | (open since 11-06) Exp2290 layout, F/P 1.24/1.2/1.357, how-to note rule, cloud runs. Absorbs qfacs-build-thread__decisions. | proposals/dreamer__decisions.md | owner answers otherwise re-asked. |
| R1 | HIGH | results.md | (open since 11-06) Confirmed run numbers + gMFI biex fix (0.2%). Absorbs qfacs-build-thread__results. | proposals/dreamer__results.md | results.md still shows placeholder-F/P numbers. |
| D2 | HIGH | decisions.md | (open since 11-06) AWAITING list: isotype in PE units when F/P blank, QC defaults 1000 / 0.98 / k=5 (now pre-filled in code, commit 3a24790, still a Claude suggestion). | proposals/dreamer__decisions.md | keeps Claude recs separate from Mase decisions. |
| O2 | MED | process (dream skill) | (open since 11-07) On days with no activity, post one line instead of a new top 5. Today is the second such day in a row. | this run | fewer notifications. |
| A1, T1, L1, L2, I1, O1 | MED/LOW | various | (open since 11-06, unchanged) see dream_2026-11-06. | proposals/dreamer__*.md | as before. |

Conflicts / checks:
- No reversals of Mase decisions. No lot values hard-coded (no code changes since last check).
- Index drift: live index matches INDEX.md. verify: only scratch/dreamer/cursor.json flagged (own scratch, expected). sync: AHEAD 10 (curator PR still not opened/merged; origin/memory at v41).
- Still open for Mase: confirm `memory` ruleset visually (since 11-04).

Not reviewed: PR diffs, build plan doc, xlsx contents, prior_work/, uploads/hearth/.

approve with: apply D1,L2  (e.g. "apply S1,D1,D2,R1,A1,T1,L1,O2")
