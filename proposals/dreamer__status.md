<!-- proposal by dreamer at 2026-11-10 06:08:23Z; target: status.md; reason: dream 2026-11-10 status; link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJrQ5JqsXPoSgEm6n6XyCDW; status: open -->
[S1 HIGH] Overwrite status.md body with:
2026-11-10 (dreamer):
- Done: phases 1-3 (PRs #2,#3,#5). PR #7 optional F/P (blank = 1, flagged) + first auto gating for .fcs-only runs + CHO-EGFR example. PRs #8 (debris floor, Imaging SSC singlets, tilted Live), #9 (SSC-A floor on Cells), #10 (Live gate for mostly-dead wells) all merged into `main` by 2026-11-10 04:33Z. Memory PR #6 merged.
- Auto gating vs Mase's .wsp, 9 lines: within ~4% on CHO-EGFR, U-87 MG, A431, MCF7, FaDu, SHP77; H82 ~16% (singlet gate tighter), Kasumi 2 ~24% (Live tail trim), CORL279 wrong FSC population (~12x).
- Waiting on Mase (thread "Finish qFACS setup template from run"): gating strategy decision card (recommended: per-line gate library from Mase's gates); confirm Plate 2 layout (assumed Plate 1 antibody order); MCF7 Live on V5 (500)-A vs V6?; layouts for Plates 3-4 also assumed; Plates 2-4 have no bead tube (Plate 1 beads used).
- Needs Mase: confirm AWAITING defaults in decisions.md; approve memory proposals.
Evidence: GitHub PR list; msgs cmsg_01Y3oxsYABfATcqbm4kp4uVB8u3MvrNvmV8cYXsbuZUHWw, cmsg_01Y3oxsYABfATcqbm4kp4uVBKnY4HJfveXCVxVmWTwKHLG, cmsg_01Y3oxsYABfATcqbm4kp4uVBUH4dGbXYftUrQUNf69R84t.
Uplift: status.md (2026-11-06 text, refreshed 11-09) still says "Next build work: phase 4" and "waiting on .fcs"; four PRs and 4 plates of gating checks have landed since.
