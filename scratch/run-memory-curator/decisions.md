# Decisions and standing rules
Owner answers and standing rules. One entry each: date (UTC), who decided, rule. Grep here before asking the owner anything.

## Active Rules Digest
- Only Mase and the coordinator write the platform memory index; only Mase merges PRs (2026-11-04).
- Threads over 30 min check in and commit+push every 30 min; no workflows or helper agents unless Mase asks; short replies (2026-11-04).
- Project-specific rules: none yet; Mase will add them as we go (2026-11-04).
- Setup inputs always user-entered, each with a how-to note and suggested value (2026-11-05).
- Gating is manual: Mase's FlowJo .wsp gates (Cells > Single Cells > Live) feed the workflow; auto gating is only a flagged fallback (2026-11-10).

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

- 2026-11-05, Mase: Exp2290 Set 2 Plate 1 layout confirmed: U-87 MG rows A-D, A431 rows E-H, each row CD58, B7H3, DLL3, mIgG1; 50 ug/mL top, 1.8x (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBYBrSGgMT86dfZANPwNVPnL "1 correct").
- 2026-11-05, Mase: Exp2290 F/P: CD58 1.24, B7H3 1.2 (from setup sheet); DLL3 (Novus NBP3-45128PE, lot D224308) 1.357 from vial label confirmed (msg cmsg_01Y3oxsYABfATcqbm4kp4uVB3K3YvQcdpsxojTs6h3xz93 "#2 that works"). Experiment-specific inputs, not defaults.
- 2026-11-05, Mase: every user-entered setting in the setup workbook gets a note telling the user how to obtain it and/or a suggested value (msgs cmsg_01Y3oxsYABfATcqbm4kp4uVBCkEZeAZDooPGEubdXQxD3e, cmsg_01Y3oxsYABfATcqbm4kp4uVBRax1nhtLCdXxrenZSXNnLu "and/or provide a suggestion").
- 2026-11-05, Mase: wants cloud runs: Mase uploads setup + data to the thread, Claude runs and returns results (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBVYHb9u3iq6WqVrkphLpH2c).
- 2026-11-10, Mase: gating is manual for now. Mase draws Cells > Single Cells > Live in FlowJo and saves the .wsp; qFACS automates everything after that (reads the .wsp gates + .fcs, exports gMFI/counts, runs the analysis). Automatic gating (qfacs/autogate.py) stays only as a flagged fallback; rule tuning stopped (6 of 9 lines within ~4%, H82/Kasumi 2/CORL279 not) (msgs cmsg_01Y3oxsYABfATcqbm4kp4uVBNqCEKoVU5r6p9HjZdgcPjZ, cmsg_01Y3oxsYABfATcqbm4kp4uVB6D8caEamfwpWywk2obeiEH).

## Proposed analysis defaults, AWAITING Mase confirmation (2026-11-04, Claude in "Review prior qFACS workbook work", msg cmsg_01Y3oxsYABfATcqbm4kp4uVBXkS8uJRi9P43NcnSqQJZAs)
Not owner decisions yet; ask Mase to confirm via the build plan doc before treating as rules.
- Report: Bmax from titration fit as main number, plus top-dose ABC; flag "not saturated" when top conc < ~5x fitted Kd.
- Valency: per-antibody input, default 1 (antigens = ABC).
- Background: (1) subtract no-antibody well gMFI (autofluorescence); (2) convert each reagent to ABC with its own F/P; (3) subtract isotype ABC at matched concentration. Isotype must match host/isotype (note: DLL3 rabbit chimera vs mIgG1 isotype is a mismatch).
- gMFI above High bead: note only, not a warning (Mase agreed, msg cmsg_01Y3oxsYABfATcqbm4kp4uVB6cVH9VPUt24hvTMMzC2JN2).
- Fixation: suggested fixed vs unfixed head-to-head on one line; Mase has not committed to running it.
- Isotype with blank F/P: subtract in PE units assuming antibody F/P, flagged. Asked of Mase (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBXL6Z4fy1Zwcv9mGRRNFN6d Q1) but never answered; "#2 that works" answered Q2 only.
- Order: convert each gMFI to PE/ABC first, then subtract (curve slope != 1). BD insert is silent on isotype/background (msg cmsg_01Y3oxsYABfATcqbm4kp4uVB5pUKGBHTVgDVGomW8Y92g1).
- QC suggestions pre-filled in template: min live events 1000, bead R^2 min 0.98, saturated when top conc >= k x Kd with k = 5 (Claude conventions, not BD).
- [Superseded 2026-11-10 by Mase's manual-gating decision, see Log] Auto gating plan (phase 4): gate library with one reference Cells gate per cell line fit to new plates, fixed Singlets (FSC-A vs FSC-H) and Live (V6 low) rules, gate-plot QC sheet.
- F/P optional, blank = 1 and flagged (PR #7). Came from Claude's answer to Mase's question "is F/P completely necessary" (cmsg_01Y3oxsYABfATcqbm4kp4uVBDQ8BjtwDzVwQAMF79XcW23); Mase merged PR #7 but did not state the rule. Note it relaxes the 2026-11-05 "never hard-code F/P" rule only as a flagged fallback.
- Plates 2-4 antibody order assumed = Plate 1 (unanswered). MCF7 Live channel V5 vs V6 asked, unanswered; now only matters for the auto-gating fallback.
