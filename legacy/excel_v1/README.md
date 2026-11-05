# Excel-only qFACS workbook (v1, from an earlier session)

Snapshot of the first working approach, kept for reference while the automated pipeline is built.

| File | What it is |
|---|---|
| `build_qfacs_xl.py` | openpyxl script that generates the workbook. `python build_qfacs_xl.py out.xlsx` makes the blank master; `--example inputs.xlsx "export.xls::name" ...` pre-fills a plate (needs `xlrd`). |
| `qFACS_Import.pq` | Power Query (M) that reads every FlowJo table export (.xls/.csv/.txt) in the workbook's folder (local or SharePoint) into the hidden `Import` sheet. Same code is embedded in the `PQ_Setup` sheet. |
| `qFACS_master_template.xlsx` | Blank master (one 96-well plate per workbook). |
| `qFACS_Plate1.xlsx` | Example filled with Plate 1 (H1975 rows A-D, A549 rows E-H; CD58, B7H3, DLL3, mIgG1 isotype) and static import rows from `Plate1 H1975.xls`, `Plate1 A549.xls`, `Quantbrite PE Beads.xls`. |

## Inputs it expects
FlowJo table exports, not .fcs: one per cell line named `<PlateID> <CellLine>.xls` with columns
`<gate path> | Geometric Mean (B5 (575)-A)` (and optional `Count`) per well, plus a bead export whose name contains
`bead` with gates `Low`, `Med Low`, `Med High`, `High`.

## Maths (all live Excel formulas)
1. Bead curve: log10(gMFI) = m·log10(PE/bead) + c over the 4 Quantibrite peaks; QC = R² ≥ 0.98 and 80-120 % back-calculated recovery.
2. Per well: PE/cell = 10^((log10 gMFI − c)/m); ABC = (PE/cell − column-12 no-antibody PE/cell) / F:P.
3. Isotype ABC from the matched isotype row (same cell line), interpolated at the same concentration; specific ABC = ABC − isotype ABC.
4. One-site fit per plate row, specific ABC = Bmax·C/(Kd + C), via a two-stage log grid on Kd with exact least-squares Bmax,
   SE/95 % CI from the Jacobian. Antigens/cell = Bmax × valency factor (default 1, i.e. ABC).
5. Flags: plateau (top conc ≥ 5×Kd), fit quality, bead range, low events, missing isotype, import issues.

## Example result (Plate 1, recalculated in LibreOffice)
Bead curve slope 0.977, R² 0.9995, QC PASS.

| Cell line | CD58 | B7H3 | DLL3 |
|---|---|---|---|
| H1975 | 80,400 (top conc above High bead) | 89,000 (top conc above High bead) | ND |
| A549 | 56,800 | 62,700 | ND |

## Known limits
- Needs FlowJo gating and table export first; does not read .fcs.
- One plate per workbook; Exp2281 has 11 plates.
- Power Query code was never executed in Excel by its author; verify on first run.
- Panel F/P values are placeholders (1) for the BioLegend reagents; bead lot 42618 values are pre-filled and that lot expired 2022-10-31.
