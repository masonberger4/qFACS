<!-- proposal by dreamer at 2026-11-06 06:06:43Z; target: dream_2026-11-06.md; reason: daily dream report 2026-11-06; link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBNB3va9jdUjAAZJoNmn6nHv; status: open -->
# Dream report 2026-11-06 (qfacs-dream skill)
Scope: memory v1-v42, all open proposals, threads active since 2026-11-05 06:15Z (build thread "Review prior qFACS workbook work" 21:00Z-23:36Z, curator, 11-05 dream thread), project chat to 06:03Z, origin/main git log.

| ID | pri | target | change | evidence | uplift |
|---|---|---|---|---|---|
| S1 | HIGH | status.md | Rewrite: phases 1-3 shipped, PRs #1-#5 merged, waiting on Mase's edited setup + .fcs; gating inputs Mase can supply. | git log origin/main; msg ...BJfoD2hGW | status says build plan awaits review, PR #1 open. |
| D1 | HIGH | decisions.md | Record Mase's answers: Exp2290 layout; F/P 1.24/1.2/1.357; "every setup input gets a how-to note and/or suggestion"; cloud runs wanted. Absorbs open qfacs-build-thread__decisions. | msgs ...BYBrSGg, ...B3K3Yv, ...BCkEZe, ...BRax1n, ...BVYHb9 | otherwise re-asked. |
| R1 | HIGH | results.md | Replace placeholder-F/P numbers with confirmed run (A431 CD58 105,026...); add PR #5 gMFI fix (biex mean, 0.2%), auto bead peaks, .fcs route 0.3%. Absorbs open qfacs-build-thread__results. | msgs ...BXL6Z4, ...B4gzK2; PR #5 | results.md shows stale numbers and an "unsolved" 3% gap. |
| D2 | HIGH | decisions.md | Add to AWAITING list: isotype subtracted in PE units when F/P blank (asked, never answered); convert-then-subtract; QC suggestions 1000 events / R^2 0.98 / k=5; phase 4 gate-library plan. | msg ...BXL6Z4 Q1; ...B5pUKG; ...BRax1n | stops Claude recs being read as Mase decisions. |
| L1 | MED | lessons.md | Terse numbered answers across overlapping lists ("1 correct", "#2 that works") left Q1 unanswered; use distinct labels, one list at a time. | msgs ...BYBrSGg, ...B3K3Yv | avoids misfiled answers. |
| A1 | MED | data.md | Fix "repo empty" line; document setup/, results/, test_run/ (zip, to_edit/, cloud_run/), Exp2290 inputs; flag 2 template copies. Replaces open 11-05 A1. | ls shared folder | template duplicate can serve stale copy. |
| T1 | MED | threads.md | Build thread: 3 phases shipped, blocked on Mase's files; curator applied PR #4. | list_threads | registry stale. |
| L2 | LOW | lessons.md | One thread, one --agent name (build thread used two). | CHANGELOG v23, v42 | clean provenance. |
| I1 | LOW | INDEX (coordinator) | POINTERS: "Code base branch is `main` (README-only seed)" -> "`main` holds the qfacs engine (PRs #1-#5)"; add test kit test_run/qFACS_test_run.zip. | git log | index misdescribes main. |
| O1 | LOW | process | Curator: after applying, mark qfacs-build-thread__decisions/results merged; sync shows AHEAD 1. Build thread: delete or regenerate setup/qFACS_setup_template.xlsx. | memsave sync | keeps store and folders consistent. |

Conflicts / checks:
- No reversals of Mase decisions found. Lot values: engine (qfacs/) has no hard-coded F/P or bead PE/bead; only legacy/excel_v1 does (expected).
- Regression baseline (Excel v1 Plate 1) still in tests per PR #2 notes.
- Index drift: live index matches INDEX.md. verify: CLEAN. All files < 4 KB except CHANGELOG (9.6 KB, append-only log; fine).
- Previously merged (11-05 D1/D2/L1): not recurring.
- Open since 11-05: O1 (sync) still open; A1 replaced above.

Not reviewed: PR diffs beyond git log, the build plan doc, xlsx contents, prior_work/, uploads/hearth/, skills/ and memory-export/ folders.

approve with: apply D1,L2  (e.g. "apply S1,D1,D2,R1,A1,T1,L1")
