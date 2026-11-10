# Results
Experiments, tests, audits, builds, baselines, status history. Group by subject, not date.

## Phase 2 engine (2026-11-05, PR #2)
- qfacs analyze reproduces Excel v1 Plate 1 to 0.1% (regression test).
- Exp2290 Set 2 Plate 1 (data: /mnt/project-files/Plate_001.zip .fcs, 02-Nov-2026.wsp, FlowJo exports Plate1_U87.xls / Plate1_A431.xls, bead Tube_001 = same bead export as v1). Layout assumed U-87 MG rows A-D, A431 E-H (CD58, B7H3, DLL3, mIgG1), 50 ug/mL, 1.8x. With PLACEHOLDER F/P (1,1,1.357,1) and bead lot 42618 values: A431 CD58 130,000, B7H3 120,000, DLL3 ND; U-87 MG CD58 53,500, B7H3 89,600, DLL3 4,490 (not saturated). Results: /mnt/project-files/results/. [superseded 2026-11-05 (PR #3)]
- Exp2290 Set 2 Plate 1 with confirmed F/P (CD58 1.24, B7H3 1.2, DLL3 1.357; isotype F/P blank -> subtracted in PE units, flagged), PR #3: A431 CD58 105,026, B7H3 100,015, DLL3 ND; U-87 MG CD58 43,164, B7H3 74,661, DLL3 6,533 (not saturated, top conc 0.5x Kd). Bead curve R^2 0.9995. Example run warnings: fixation, DLL3 isotype mismatch, blank isotype F/P, no PE-only control.
- Phase 3 feasibility: FlowKit 1.3.2 loads 02-Nov-2026.wsp (groups A431, U87 MG; gates Cells > Single Cells > Live) and applies it to Plate_001 .fcs in <1 s. Live counts within ~0.5% of FlowJo; geometric mean of raw B5 (575)-A is ~3% (max 6%) higher than FlowJo's: resolved, see Phase 3 .fcs route.
- FCS keywords from FACSChorus: plateid (Plate_001), wellid (A01), bdspectral unmixing method SpectralFX; channels are raw detectors (e.g. B5 (575)-A), no unmixed parameters in these files.

## Phase 3 .fcs + .wsp route (2026-11-05, PR #5)
- FlowJo v10 gMFI = mean on the workspace biex display transform, inverted (B5 (575)-A biex pos 6.45, width -1000, max 1e8). Matches FlowJo export within 0.2% median, 90% of wells within 0.5%; plain log gmean was -3.4%. Implemented in qfacs/fcs_io.py.
- Bead .wsp 10.29.26.wsp has no gates; bead peaks auto-gated within 3% of manual gates.
- End to end Plate 1: antigens/cell from .fcs route within 0.3% of FlowJo-export run.
