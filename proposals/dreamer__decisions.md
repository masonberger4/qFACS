<!-- proposal by dreamer at 2026-11-06 06:05:33Z; target: decisions.md; reason: dream 2026-11-06 D1+D2: new owner answers and new Claude-recommended defaults; link: cmsg_01Y3oxsYABfATcqbm4kp4uVBYBrSGgMT86dfZANPwNVPnL; cmsg_01Y3oxsYABfATcqbm4kp4uVB3K3YvQcdpsxojTs6h3xz93; cmsg_01Y3oxsYABfATcqbm4kp4uVBCkEZeAZDooPGEubdXQxD3e; cmsg_01Y3oxsYABfATcqbm4kp4uVBMtpGf64JuyajzZF4tGWvcw; status: open -->
[D1 HIGH] Append to Log (supersedes open proposal qfacs-build-thread__decisions.md, mark it merged with this):
- 2026-11-05, Mase: Exp2290 Set 2 Plate 1 layout confirmed: U-87 MG rows A-D, A431 rows E-H, each row CD58, B7H3, DLL3, mIgG1; 50 ug/mL top, 1.8x (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBYBrSGgMT86dfZANPwNVPnL "1 correct").
- 2026-11-05, Mase: Exp2290 F/P: CD58 1.24, B7H3 1.2 (from setup sheet); DLL3 (Novus NBP3-45128PE, lot D224308) 1.357 from vial label confirmed (msg cmsg_01Y3oxsYABfATcqbm4kp4uVB3K3YvQcdpsxojTs6h3xz93 "#2 that works"). Experiment-specific inputs, not defaults.
- 2026-11-05, Mase: every user-entered setting in the setup workbook gets a note telling the user how to obtain it and/or a suggested value (msgs cmsg_01Y3oxsYABfATcqbm4kp4uVBCkEZeAZDooPGEubdXQxD3e, ...BRax1n... follow-up "and/or provide a suggestion").
- 2026-11-05, Mase: wants cloud runs: Mase uploads setup + data to the thread, Claude runs and returns results (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBVYHb9u3iq6WqVrkphLpH2c).
- Digest line (add): "Setup inputs always user-entered, each with a how-to note and suggested value (2026-11-05)."

[D2 HIGH] Append to "Proposed analysis defaults, AWAITING Mase" (Claude recommendations, NOT decided):
- Isotype with blank F/P: subtract in PE units assuming antibody F/P, flagged. Asked of Mase (msg cmsg_01Y3oxsYABfATcqbm4kp4uVBXL6Z4fy1Zwcv9mGRRNFN6d Q1) but never answered; "#2 that works" answered Q2 only.
- Order: convert each gMFI to PE/ABC first, then subtract (curve slope != 1). BD insert is silent on isotype/background (msg cmsg_01Y3oxsYABfATcqbm4kp4uVB5pUKGBHTVgDVGomW8Y92g1).
- QC suggestions pre-filled in template: min live events 1000, bead R^2 min 0.98, saturated when top conc >= k x Kd with k = 5 (Claude conventions, not BD).
- Auto gating plan (phase 4): gate library with one reference Cells gate per cell line fit to new plates, fixed Singlets (FSC-A vs FSC-H) and Live (V6 low) rules, gate-plot QC sheet.
Evidence: build thread 2026-11-05 21:22Z-23:36Z.
Uplift: prevents re-asking confirmed layout/F/P, and stops PE-unit isotype subtraction and QC thresholds being treated as owner decisions.
