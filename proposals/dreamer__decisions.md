<!-- proposal by dreamer at 2026-11-05 06:09:38Z; target: decisions.md; reason: dream 2026-11-05 D2: record Claude-recommended analysis defaults as pending owner confirmation; link: cmsg_01Y3oxsYABfATcqbm4kp4uVBXkS8uJRi9P43NcnSqQJZAs; status: open -->
## Proposed analysis defaults, AWAITING Mase confirmation (2026-11-04, Claude in "Review prior qFACS workbook work", msg cmsg_01Y3oxsYABfATcqbm4kp4uVBXkS8uJRi9P43NcnSqQJZAs)
Not owner decisions yet; ask Mase to confirm via the build plan doc before treating as rules.
- Report: Bmax from titration fit as main number, plus top-dose ABC; flag "not saturated" when top conc < ~5x fitted Kd.
- Valency: per-antibody input, default 1 (antigens = ABC).
- Background: (1) subtract no-antibody well gMFI (autofluorescence); (2) convert each reagent to ABC with its own F/P; (3) subtract isotype ABC at matched concentration. Isotype must match host/isotype (note: DLL3 rabbit chimera vs mIgG1 isotype is a mismatch).
- gMFI above High bead: note only, not a warning (Mase agreed, msg cmsg_01Y3oxsYABfATcqbm4kp4uVB6cVH9VPUt24hvTMMzC2JN2).
- Fixation: suggested fixed vs unfixed head-to-head on one line; Mase has not committed to running it.
