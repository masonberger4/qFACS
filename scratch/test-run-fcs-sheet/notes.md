# Test run from only fcs and sheet (2026-11-10)
- Mase confirmed bead kit lot 42618 values from the kit flyer photo: 474 / 5359 / 23843 / 62336 PE/bead (lot is the one in hand; no longer a placeholder).
- Mase's antibody table (screenshot): stock CD58 400, B7H3 350, DLL3 800, mIgG1 200 ug/mL; F/P CD58 1.24, B7H3 1.2, DLL3 blank on sheet (1.357 from vial used), isotype '-'.
- .fcs-only run on main e752a5b (Plate_001 + Tube_001.fcs): runs in 3 s, no errors, but auto gates too loose vs Mase's 02-Nov-2026.wsp: Live counts 1.4x (U-87) / 2.2x (A431), antigens/cell ~half (A431 CD58 53,902 vs 105,140). FlowJo-gated rerun matches PR #3 numbers within 0.2%. Files: /mnt/project-files/results/fcs_only_test_2026-11-10/. Sent to gating thread to fix.
