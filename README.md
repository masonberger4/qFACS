# qFACS

Automated qFACS workflow: FlowJo Excel exports of BD FACSDiscover A8 data plus an experiment setup sheet,
calibrated with BD Quantibrite PE beads, to antigens (antibodies bound) per cell.

Project memory lives on the separate `memory` branch. The earlier Excel-only workbook is kept in `legacy/excel_v1/`.

## Status
The experiment setup workbook and validator, and the analysis engine working from FlowJo table exports.
Everything on the FlowJo side (unmixing, compensation, gating of cells and beads, the gMFI and count statistics)
is done by hand in FlowJo. The engine does not read .fcs or .wsp files and does not unmix or gate.

**New data set?** Step-by-step guide (FlowJo Excel exports + setup workbook): [docs/RUN_NEW_DATASET.md](docs/RUN_NEW_DATASET.md).

## Install
```
pip install -e ".[dev]"     # Python 3.10+; openpyxl, numpy, scipy, xlrd
```

## Setup workbook
One Excel workbook per experiment, made from `examples/qFACS_setup_template.xlsx` (or `python -m qfacs template out.xlsx`).
Yellow cells are inputs; column headers carry help notes; `*` marks required columns.

| Sheet | One line per | Key fields |
|---|---|---|
| Experiment | setting | Experiment ID, PE parameter, live gate name, fixed after staining (Y/N), QC thresholds |
| Beads | Quantibrite tube acquired | bead run ID, kit lot, PE molecules per bead for the 4 peaks (from the lot flyer) |
| Reagents | PE antibody or isotype | name, isotype control?, host, isotype, catalog, lot, F/P, valency, MW, matched isotype |
| Cell_Lines | cell line | name, source ID |
| Plates | plate | plate ID (as in the data files), bead run that calibrates it |
| Layout | plate row | plate, row, cell line, reagent, top final conc, dilution factor, first column, points, no-antibody column(s) |

No reagent or bead values are built in: F/P, valency, concentrations, catalog and lot numbers, and bead PE values
are always entered by the user. The one fallback: an antibody left with a blank F/P is treated as a 1:1 PE
conjugate (F/P = 1, so ABC = PE molecules per cell), and every affected result is flagged "F/P assumed 1".

## Validate
```
python -m qfacs validate my_setup.xlsx [--wells wells.csv]
```
Errors block the analysis (missing or unreadable values, unknown references, overlapping wells, bead values not rising).
Warnings are QC flags that travel with the results, including:
- isotype mismatch: an antibody's host/isotype differs from its matched isotype, or the isotype was not run on that cell line
- no no-antibody well for a cell line on a plate
- cells fixed after staining

`--wells` writes one line per well with cell line, reagent and final concentration.

## Analyze FlowJo exports
```
python -m qfacs analyze my_setup.xlsx path/to/exports/ [-o results.xlsx]
```
Inputs are FlowJo table exports (.xls, .xlsx, .csv or .txt), one row per sample (named from the well, e.g. `E01-Sample_049`):
- cell exports with `<gate path> | Geometric Mean (<PE parameter>)` and optionally `<gate path> | Count` for the live gate.
  A file belongs to the plate whose Plate ID starts its name (`Plate1_A431.xls` -> Plate1). A cell line named after
  the plate (`Plate1 A431.xls`) ties the file to that line: wells the Layout gives to another line are skipped and
  flagged. The Data files sheet lists each file's plate, cell line, wells and antibodies.
- a bead export (name contains "bead") with gates named Low, Med Low, Med High and High.

The results workbook has Summary (cell line x antibody antigens/cell and flags, for the isotype-subtracted and the NS fit), Plots, Method (each calculation step in
plain language, with the sheet and columns that hold it), Fits, Wells, Beads and Issues.
On Wells and Beads the calculated columns are live Excel formulas (bead curve, PE/cell, no-antibody background,
ABC, isotype ABC, specific ABC), so every value can be traced cell by cell. Bmax and Kd on Fits are fitted values.

Method:
1. Bead curve per bead run: log10(gMFI) = slope x log10(PE/bead) + intercept; QC = R² and 80-120 % recovery.
2. PE/cell from gMFI; ABC = (PE/cell - same-row no-antibody PE/cell) / F:P.
3. Isotype ABC of the matched isotype on the same cell line, interpolated on log concentration; specific ABC = ABC - isotype ABC.
4. One-site fit per cell line x antibody (replicate plates pooled): specific ABC = Bmax x C / (Kd + C), 95 % CIs.
   Antigens/cell = Bmax x valency (blank valency = 1).

Both fit models, every run (one Fits row each, both on Summary and Plots):
- Isotype subtracted: steps 3-4 above. Uses the antibody's "Matched isotype"; when that is blank, the only isotype
  control run on the same cell line is used and the result says so.
- NS fit: no isotype subtraction. Total-binding fit ABC = Bmax x C / (Kd + C) + NS x C, with Bmax, Kd, NS >= 0
  (the model of BD's QuantiBRITE ABC calculator); NS x C is the non-specific signal. It needs top doses well past
  saturation (ideally >= 10x Kd, several points on the plateau) so the plateau and the slow linear rise can be
  told apart. The two are never combined: subtracting the isotype and fitting NS would remove the background twice.
- Each model gets its full result: antigens/cell, Bmax and Kd with 95 % CIs, R², saturation, flags and a plot.
  Summary lists both tables and their ratio (NS fit / isotype subtracted).
- No isotype to use (none run on the cell line, or several and none matched), or no isotype data: NS fit only, flagged.
- There is no fit-model setting. Setup workbooks from older templates that still have one are read as before and
  the value is ignored with a warning.
- NS flags: Kd below the lowest or above the top dose, non-specific > 50 % of the top-dose signal, wide Bmax CI
  (SE > 25 %). Both rows are flagged when the two models differ by > 25 %, or when one is ND and the other is not.
5. Flags (nothing is excluded): not saturated (top conc < k x Kd), poor fit, imprecise Bmax, ND, isotype mismatch or
   missing, low live events, missing data, signal above the High bead (note), bead QC.

`tests/test_analysis.py` checks that the Excel v1 Plate 1 example reproduces to 0.1 %.
`examples/Exp2290_Set2_Plate1/` holds a full worked example (U-87 MG and A431). Its F/P and bead lot values are
placeholders copied from the v1 workbook.

## Converting older setup sheets
```
python scripts/convert_legacy_setup.py Exp2281_qFACS_Setup.xlsx examples/Exp2281_setup.xlsx \
    --panel legacy/excel_v1/qFACS_Plate1.xlsx
```
Reads the Design, Cell Lines and Plate Maps sheets (the latest dated "Plate Maps" sheet by default). Values missing
from the source stay blank so the validator asks for them.

## Tests
```
python -m pytest
```
