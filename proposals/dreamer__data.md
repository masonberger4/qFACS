<!-- proposal by dreamer at 2026-11-10 06:08:28Z; target: data.md; reason: dream 2026-11-10 data; link: thread cmsg_01Y3oxsYABfATcqbm4kp4uVBJrQ5JqsXPoSgEm6n6XyCDW; status: open -->
[A1 MED] Replaces open A1 (2026-11-06).
- Repo line -> "Repo: https://github.com/masonberger4/qFACS. `main` = code (qfacs/ package, tests, examples, legacy/excel_v1; PRs #1-#3, #5, #7-#10 merged by 2026-11-10). `memory` = approved memory store (PRs #4, #6)."
- ADD "## Working folders (2026-11-10)":
  - setup/: qFACS_setup_template.xlsx, Exp2281_setup.xlsx, CHO-EGFR_setup.xlsx.
  - results/: Exp2290_Set2_* (phase 2), CHO-EGFR/, fcs_only_test_2026-11-10/, autogate_check_2026-11-10/, autogate_check_plate3_2026-11-10/, autogate_check_plate4_2026-11-10/.
  - test_run/: qFACS_test_run.zip (HOW_TO_RUN.md, Windows .bat untested), to_edit/, cloud_run/.
  - Raw data (Exp2290 Set 2, acquired 02-Nov-2026): Plate_001.zip + 02-Nov-2026.wsp (U-87 MG/A431); Plate_002.zip + "02-Nov-2026 2.wsp" (MCF7 A-D, FaDu E-H); Plate_003.zip + "02-Nov-2026 3.wsp" (H82 A-D, SHP77 E-H); Plate_004.zip + "02-Nov-2026 4.wsp" (Kasumi 2 A-D, CORL279 E-H). Only Plate 1 has a bead tube (Tube_001). "Plate_001 2.zip" appears to be a duplicate upload (same size).
  - CHO EGFR.zip: CHO-EGFR plate + beads.
- FLAG (carried): duplicate qFACS_setup_template.xlsx (setup/ vs test_run/to_edit/); not re-checked whether PR #7 resolved it.
Uplift: threads re-discover which .wsp/zip belongs to which plate and that beads are only in Plate 1.
