# Live status
Short, current. Overwrite freely (by a writer). What is in flight, what is blocked, what needs the owner.

2026-11-10 (dreamer S1, updated by curator with Mase's gating decision):
- Done: phases 1-3 (PRs #2,#3,#5). PR #7 optional F/P (blank = 1, flagged) + first auto gating for .fcs-only runs + CHO-EGFR example. PRs #8 (debris floor, Imaging SSC singlets, tilted Live), #9 (SSC-A floor on Cells), #10 (Live gate for mostly-dead wells) all merged into `main` by 2026-11-10 04:33Z. Memory PR #6 merged.
- Auto gating vs Mase's .wsp, 9 lines: within ~4% on CHO-EGFR, U-87 MG, A431, MCF7, FaDu, SHP77; H82 ~16% (singlet gate tighter), Kasumi 2 ~24% (Live tail trim), CORL279 wrong FSC population (~12x).
- Decided (Mase, 2026-11-10): gating is manual. Mase draws Cells > Single Cells > Live in FlowJo and supplies the .wsp; qFACS automates everything after that. Auto gating stays only as a flagged fallback; rule tuning stopped. See decisions.md.
- Waiting on Mase (thread "Finish qFACS setup template from run"): go-ahead on 3 proposed additions (use bead gates from the .wsp, gate-check sheet in results, one run over a folder of several plates); confirm Plate 2-4 layouts (assumed Plate 1 antibody order); Plates 2-4 have no bead tube (Plate 1 beads used).
- Needs Mase: confirm AWAITING defaults in decisions.md; approve memory proposals.
