<!-- proposal by dreamer at 2026-11-10 06:08:57Z; target: dream_2026-11-10.md; reason: daily dream report 2026-11-10; link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJrQ5JqsXPoSgEm6n6XyCDW; status: open -->
# Dream report 2026-11-10 (qfacs-dream skill)
Scope: memory v1-v63, all proposals, threads active since 2026-11-09 06:12Z (6), full project chat, qFACS PR list.

Busy day: Mase active 2026-11-09 23:20Z to 11-10 04:32Z. PRs #6-#10 all merged. Four new threads (setup template / auto gating, fcs-only test, Plate 3 and Plate 4 gating checks). New Mase rule (small threads). Proposals below supersede the open 11-06 A1/T1/L1/L2/I1 and the other thread's CHO-EGFR entry.

| ID | pri | target | change | evidence | uplift |
|---|---|---|---|---|---|
| R1 | HIGH | results.md | CHO-EGFR run + auto gating results on 9 lines (PRs #7-#10); supersedes finish-qfacs...__results.md (wrongly says bead values PLACEHOLDER) | 4 thread reports | gating evidence behind the pending decision is only in transcripts |
| S1 | HIGH | status.md | PRs #7-#10 merged; 6/9 lines within ~4%; waiting on gating decision, Plate 2 layout, MCF7 V5 | PR list; cmsg_...8u3MvrNv | status says "next: phase 4" |
| D1 | HIGH | decisions.md | Mase 11-10 small-threads rule (digest still says "none yet"); bead lot 42618 confirmed real; Exp2290 stock concs | cmsg_...SgXw9hrE; notes.md | bead lot already re-asked once |
| D2 | HIGH | decisions.md AWAITING | F/P optional = Claude answer, not Mase rule; gating strategy and Plate 2-4 layouts open | cmsg_...DQ8BjtwD | keeps Claude recs apart |
| I1 | HIGH | INDEX.md (coordinator) | INDEX.md lacks live rule (4) + FACTS line; `main` "README-only" pointer stale; FACTS (c) fix now done | live index vs INDEX.md | drift |
| A1 | MED | data.md | repo line; folders; plate->.wsp->cell line map; beads only in Plate 1 | file listing | threads re-discover |
| T1 | MED | threads.md | 4 new threads, old ones resolved | list_threads | registry 3/4 stale |
| L3 | MED | lessons.md | confirmed value left tagged PLACEHOLDER spread and got re-asked | cmsg_...2kB7kjAp | avoids re-asks |
| L4 | MED | lessons.md | ask plate layout once per experiment | Plate 3/4 reports | fewer assumptions |
| L1, L2 | MED/LOW | lessons.md | unchanged from 11-06 | | |

Conflicts / checks:
- F/P optional (PR #7) vs 2026-11-05 "never hard-code F/P": a default of 1 is a flagged fallback, not a hard-coded value, but Mase never stated it. Flagged in D2.
- Bead lot 42618 listed as expired 2022-10-31 in data.md; Mase says it is the lot in hand. Possible QC flag, Mase's call.
- Open owner questions in the build thread: gating strategy card, Plate 2 layout, MCF7 V5 vs V6, isotype-in-PE-units (since 11-05).
- verify: untracked scratch dirs of 3 threads (allowed, own scratch). sync: AHEAD 2 (v63 proposal etc. not on GitHub).
- O1 (duplicate template) and memory ruleset visual confirm still open.

Not reviewed: code diffs of PRs #7-#10 (did not check for hard-coded lot values in code), xlsx contents, plots, uploads/hearth/, build plan doc.

approve with: apply D1,L2  (e.g. "apply R1,S1,D1,D2,I1")
