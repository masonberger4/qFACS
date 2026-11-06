<!-- proposal by dreamer at 2026-11-06 06:06:15Z; target: results.md; reason: dream 2026-11-06 R1: results.md shows placeholder-F/P numbers; add confirmed run + PR #5; link: cmsg_01Y3oxsYABfATcqbm4kp4uVBXL6Z4fy1Zwcv9mGRRNFN6d; cmsg_01Y3oxsYABfATcqbm4kp4uVB4gzK2xnohj5voxjuKF8CBz; PR #5; status: open -->
[R1 HIGH] In "Phase 2 engine": mark the PLACEHOLDER-F/P line "superseded 2026-11-05 (PR #3)" and add:
- Exp2290 Set 2 Plate 1 with confirmed F/P (CD58 1.24, B7H3 1.2, DLL3 1.357; isotype F/P blank -> subtracted in PE units, flagged), PR #3: A431 CD58 105,026, B7H3 100,015, DLL3 ND; U-87 MG CD58 43,164, B7H3 74,661, DLL3 6,533 (not saturated, top conc 0.5x Kd). Bead curve R^2 0.9995. Example run warnings: fixation, DLL3 isotype mismatch, blank isotype F/P, no PE-only control.
ADD section "## Phase 3 .fcs + .wsp route (2026-11-05, PR #5)" (supersedes open proposal qfacs-build-thread__results.md):
- FlowJo v10 gMFI = mean on the workspace biex display transform, inverted (B5 (575)-A biex pos 6.45, width -1000, max 1e8). Matches FlowJo export within 0.2% median, 90% of wells within 0.5%; plain log gmean was -3.4%. Implemented in qfacs/fcs_io.py.
- Bead .wsp 10.29.26.wsp has no gates; bead peaks auto-gated within 3% of manual gates.
- End to end Plate 1: antigens/cell from .fcs route within 0.3% of FlowJo-export run.
- Replace the "gMFI ~3% higher ... still to match" sentence in Phase 3 feasibility with "resolved, see Phase 3 .fcs route".
Uplift: results.md currently gives the placeholder numbers (130,000 etc.) and an unresolved 3% gap; a new thread would re-investigate a solved problem.
