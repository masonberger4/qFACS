<!-- proposal by dreamer at 2026-11-10 06:08:27Z; target: results.md; reason: dream 2026-11-10 results; link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJrQ5JqsXPoSgEm6n6XyCDW; status: open -->
[R1 HIGH] Supersedes proposal finish-qfacs-setup-template-from-run__results.md (it calls bead lot 42618 values a PLACEHOLDER; Mase confirmed them real from the kit flyer). ADD to results.md:

## CHO-EGFR Plate3 (2026-11-09, PR #7)
- Data: /mnt/project-files/CHO EGFR.zip (48 .fcs; 05-Nov-2026.wsp Cells>Single Cells>Live), beads Tube_001.fcs 2026-11-05 (09-Nov-2026.wsp). Row A EGFR (BioLegend AY13 352904 lot B433431, F/P blank -> 1, flagged), row B mIgG1, 50 ug/mL 1.8x 11 pts, col 12 no Ab; rows C-D unlabeled.
- EGFR 5,295 antigens/cell (FlowJo export) / 5,247 (.fcs route); Kd ~0.08 ug/mL, R2 0.82. Bead lot 42618 values 474/5359/23843/62336 (real, kit flyer). Setup setup/CHO-EGFR_setup.xlsx; results results/CHO-EGFR/.

## Auto gating vs Mase's .wsp (2026-11-10, PRs #7-#10)
- First version (PR #7) on Exp2290 Plate 1: ~2x loose (debris, A431 doublets kept), antigens/cell about half. Fixed in PR #8: within ~4% (U-87 CD58 +2.6%, B7H3 +3.1%; A431 -3.4/-4.2%; CHO-EGFR +2.6%). Results results/fcs_only_test_2026-11-10/.
- Plate 2 MCF7/FaDu: MCF7 14-26% low until SSC-A floor (PR #9); then within ~5%. DLL3 ND both lines.
- Plate 3: SHP77 within ~1%; H82 (87% dead) Live rule took dead peak, fixed in PR #10 (Live -0.3%), residual ~16% from singlet gate. results/autogate_check_plate3_2026-11-10/.
- Plate 4: Kasumi 2 +24% gMFI (Mase trims bright V6 tail); CORL279 wrong FSC population, ~12x high (CD58 533 hand vs 6,447 auto). results/autogate_check_plate4_2026-11-10/.
- Caveats: Plates 2-4 antibody order assumed = Plate 1; no bead tube in Plates 2-4 (Plate 1 beads used); no-.wsp runs use a default PE display transform (CHO and Exp2290 workspaces differ).
Evidence: threads "Test run from only fcs and sheet", "Check auto gating on Plate 3/4", "Finish qFACS setup template from run".
Uplift: results.md stops at PR #5; all gating evidence behind the pending gating decision is otherwise only in transcripts.
