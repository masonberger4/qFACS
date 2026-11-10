# Check auto gating on Plate 3 (2026-11-10)
- Code: qFACS 59b5cfc (PR #9 head, includes PR #8). Data: Plate_003.zip (96 .fcs, plateid Plate_003), 02-Nov-2026 3.wsp (groups H82 = rows A-D, SHP77 = rows E-H; Cells > Single Cells > Live, Live = polygon V6 vs SSC). Beads: Plate 1 FlowJo bead export (no bead .fcs in Plate_003.zip). Antibody order per row ASSUMED same as Plate 1.
- SHP77: auto matches hand. Live counts 1.01x, gMFI median +0.2% (same transform), antigens/cell CD58 +1.1%, B7H3 -1.0%.
- H82: auto Live gate fails. H82 singlets are ~87% dead (hand Live = 12.8% of singlets, ~430 live/well); the main V6 peak is the dead one, so auto Live keeps 100%. Live counts 7x, gMFI +56%, antigens/cell CD58 -16%, B7H3 -32%. Sent to gating thread.
- Files: /mnt/project-files/results/autogate_check_plate3_2026-11-10/
