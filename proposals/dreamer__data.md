<!-- proposal by dreamer at 2026-11-06 06:06:17Z; target: data.md; reason: dream 2026-11-06 A1: stale repo line; new shared-folder dirs (updates 2026-11-05 A1); link: cmsg_01Y3oxsYABfATcqbm4kp4uVBMES3SuWi4BZyTSobutNw1h; cmsg_01Y3oxsYABfATcqbm4kp4uVBTfGPYtsWACQJ5QUNRoVu9H; status: open -->
[A1 MED] Replaces the open 2026-11-05 A1 (A8 part already merged).
- Repo line -> "Repo: https://github.com/masonberger4/qFACS. Branches: `main` (code: qfacs/ package, tests/, examples/, legacy/excel_v1; PRs #1-#3, #5 merged 2026-11-05), `memory` (approved memory store)."
- ADD "## Working folders (2026-11-05)":
  - setup/: qFACS_setup_template.xlsx (phase 1 version), Exp2281_setup.xlsx (converted example).
  - results/: Exp2290_Set2_qFACS_results.xlsx + setup (phase 2 run).
  - test_run/: qFACS_test_run.zip + unzipped qFACS_test_run/ (HOW_TO_RUN.md, 1_install.bat, 2_run_example.bat, 3_analyze_my_folder.bat); to_edit/ (current template with pre-filled QC suggestions + Exp2290_Set2_setup_prefilled.xlsx, the files Mase edits); cloud_run/ (results from cloud run).
  - Exp2290 inputs: Plate_001.zip (.fcs), 02-Nov-2026.wsp (gates Cells > Single Cells > Live), bead tube Tube_001 / bead wsp 10.29.26.wsp (no gates).
  - prior_work/REVIEW_excel_v1.md: review of Excel v1 incl. 6 inconsistencies.
- FLAG: two qFACS_setup_template.xlsx copies (setup/ older, test_run/to_edit/ newer with QC notes). Point threads at to_edit/ or regenerate setup/ (O-item for build thread).
Uplift: data.md still says the repo is empty; folders created yesterday are undocumented, and the template duplicate can hand Mase the stale copy.
