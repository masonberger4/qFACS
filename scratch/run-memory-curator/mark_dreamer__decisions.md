<!-- proposal by dreamer at 2026-11-10 06:08:31Z; target: decisions.md; reason: dream 2026-11-10 decisions; link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJrQ5JqsXPoSgEm6n6XyCDW; status: partly merged v74: D2 applied (gating line dropped, decided); D1 still open -->
[D1 HIGH] Append to Log:
- 2026-11-10, Mase: threads are small and focused (one task per thread, new ask = new thread) and rely on memory/ for context (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBSgXw9hrEBxkeHCFbaUMMyg). Digest: replace "Project-specific rules: none yet" with "Threads small and focused, one task each, rely on memory (2026-11-10)".
- 2026-11-10, Mase: bead lot 42618 (474 / 5359 / 23843 / 62336 PE/bead) is the lot in hand, from the kit flyer (thread "Test run from only fcs and sheet", notes scratch/test-run-fcs-sheet/notes.md). Still user-entered per run, not a default. Note: data.md lists this lot as expired 2022-10-31; worth a QC flag.
- 2026-11-10, Mase (antibody table screenshot): stock conc CD58 400, B7H3 350, DLL3 800, mIgG1 200 ug/mL (Exp2290).
[D2 HIGH] Append to AWAITING (Claude recommendations, NOT Mase decisions):
- F/P optional, blank = 1 and flagged (PR #7). Came from Claude's answer to Mase's question "is F/P completely necessary" (cmsg_01Y3oxsYABfATcqbm4kp4uVBDQ8BjtwDzVwQAMF79XcW23); Mase merged PR #7 but did not state the rule. Note it relaxes the 2026-11-05 "never hard-code F/P" rule only as a flagged fallback.
- Gating strategy (open decision card, 2026-11-10): recommended per-cell-line gate library from Mase's own gates; alternatives keep tuning rules / always use .wsp. Unanswered.
- Plates 2-4 antibody order assumed = Plate 1; MCF7 Live channel V5 vs V6 asked, unanswered.
Uplift: prevents re-asking the bead lot; keeps the F/P default and gating plan marked as Claude's until Mase rules.
