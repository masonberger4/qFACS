# Decisions and standing rules
Owner answers and standing rules. One entry each: date (UTC), who decided, rule. Grep here before asking the owner anything.

## Active Rules Digest
- Only Mase and the coordinator write the platform memory index; only Mase merges PRs (2026-11-04).
- Threads over 30 min check in and commit+push every 30 min; no workflows or helper agents unless Mase asks; short replies (2026-11-04).
- Project-specific rules: none yet; Mase will add them as we go (2026-11-04).

## Log
- 2026-11-04, Mase: project "Quantbrite Automation" goal is an automated qFACS workflow: input .fcs files + experiment setup sheet (e.g. Exp2281_qFACS_Setup.xlsx) -> calculated antigens per cell, using BD PE Quantibrite bead calibration. Code repo: https://github.com/masonberger4/qFACS.
- 2026-11-04, Mase: memory system set up from the starter kit (thread "Set up project memory system"). Detail in /mnt/project-files/memory/; approved store is GitHub branch `memory`; only Mase and the coordinator write the platform index; only Mase merges PRs; curator thread "Run memory curator" applies only changes Mase approves in chat; daily dreaming pass writes proposals only.
- 2026-11-04, Mase: project-specific standing rules not given yet (setup prompt placeholder left unfilled); asked Mase in thread "Set up project memory system".
- 2026-11-04, Mase: "No standing rules at the moment. We will add as we go" (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBGfpWMCpEixpKGWfWmHHq6w).
- 2026-11-05, Mase (inline edits to build plan doc https://claude.ai/artifact/MKhhyuQpTo8xxKecP1LEhv):
  - Users: Mase and other lab members (plural).
  - Never hard-code reagent values: F/P, valency, concentration, catalog #, lot #, PE bead lot values all user-entered.
  - Engine runs locally until confirmed working, then moves to a locally hosted web UI.
  - Example .fcs/.wsp/FlowJo export: Mase will add to the thread; FlowJo export sample to be uploaded.
  - Single-stain controls (PE-only, reporter-only) will come as .fcs files.
  - Fixation head-to-head: to be tested in the future.
  - Isotype: add a QC flag checking the isotype run matches (host/isotype) the antibodies tested on that cell line.

## Proposed analysis defaults, AWAITING Mase confirmation (2026-11-04, Claude in "Review prior qFACS workbook work", msg cmsg_01Y3oxsYABfATcqbm4kp4uVBXkS8uJRi9P43NcnSqQJZAs)
Not owner decisions yet; ask Mase to confirm via the build plan doc before treating as rules.
- Report: Bmax from titration fit as main number, plus top-dose ABC; flag "not saturated" when top conc < ~5x fitted Kd.
- Valency: per-antibody input, default 1 (antigens = ABC).
- Background: (1) subtract no-antibody well gMFI (autofluorescence); (2) convert each reagent to ABC with its own F/P; (3) subtract isotype ABC at matched concentration. Isotype must match host/isotype (note: DLL3 rabbit chimera vs mIgG1 isotype is a mismatch).
- gMFI above High bead: note only, not a warning (Mase agreed, msg cmsg_01Y3oxsYABfATcqbm4kp4uVB6cVH9VPUt24hvTMMzC2JN2).
- Fixation: suggested fixed vs unfixed head-to-head on one line; Mase has not committed to running it.
