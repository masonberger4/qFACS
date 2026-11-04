<!-- proposal by Review prior qFACS workbook work at 2026-11-04 23:39:49Z; target: decisions.md; reason: Mase's answers to scoping questions; link: msg cmsg_01Y3oxsYABfATcqbm4kp4uVB6cVH9VPUt24hvTMMzC2JN2; status: open -->
## Scoping answers (2026-11-04, Mase, msg cmsg_01Y3oxsYABfATcqbm4kp4uVB6cVH9VPUt24hvTMMzC2JN2)
- Users: Mase + 1 lab member. Files live on SharePoint (experiment, data, analysis). Excel is the preferred front end.
- Input: ideal = raw .fcs -> gated FlowJo .wsp + Excel export of gate frequencies, counts, gMFI. Fallback = user gates manually and exports Excel, which is then the input.
- Gating: Cells > Singlets > Live (Aqua live/dead, V6). "Cells" gate differs per cell line (many morphologies), so it can't be one fixed template. The lab has an internal AI; we could write skill files for it to apply gates.
- Unmixing: not done yet (Aqua on V6, PE on B5, assumed minimal overlap; unstained acts as Aqua single stain). Add a PE-only (no live/dead) single-stain control and add unmixing to the workflow; some lines carry fluorescent-protein reporters.
- Antibody F/P and bead lot PE/bead values: lot-dependent, always entered manually by the user; workflow starts agnostic (no hard-coded values).
- Valency: antibody-dependent; workflow should support it per antibody. Report choice (Bmax vs single dose) still open; Mase unsure. Saturation not always reachable because of stock concentration.
- Plate identity in examples: ignore (Plate 1 is just an example).
- Cells are PFA-fixed after staining; Mase may run a fixed vs unfixed head-to-head if it matters.
- Layouts vary: a cell line may be tested with only 2-3 antibodies.
- Output: per-experiment table of cell line x antigens per cell.
- QC: wells are all processed; failing a QC check = flag, not exclusion. gMFI above the High bead is not a problem for Mase (curve covers it); flag only. Background subtraction choice (isotype vs unstained) was asked back to Claude.
