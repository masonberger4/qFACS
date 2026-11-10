# qFACS

Automated qFACS workflow: flow cytometry data (.fcs) from the BD FACSDiscover A8 plus an experiment setup sheet,
calibrated with BD Quantibrite PE beads, to antigens (antibodies bound) per cell.

Project memory lives on the separate `memory` branch. The earlier Excel-only workbook is kept in `legacy/excel_v1/`.

## Status
Phases 1-3 of the build plan: the experiment setup workbook and validator, the analysis engine working from
FlowJo table exports, and reading .fcs files gated by a FlowJo workspace (.wsp), with automatic Quantibrite bead
peak gating. Automatic cell gating without a workspace and spectral unmixing (phase 4) come next.

## Install
```
pip install -e ".[dev]"     # Python 3.10+; openpyxl, numpy, scipy, xlrd
pip install -e ".[fcs]"     # optional: FlowKit, to read .fcs + .wsp directly
```

## Setup workbook
One Excel workbook per experiment, made from `examples/qFACS_setup_template.xlsx` (or `python -m qfacs template out.xlsx`).
Yellow cells are inputs; column headers carry help notes; `*` marks required columns.

| Sheet | One line per | Key fields |
|---|---|---|
| Experiment | setting | Experiment ID, PE parameter, live gate name, fixed after staining (Y/N), QC thresholds |
| Beads | Quantibrite tube acquired | bead run ID, kit lot, PE molecules per bead for the 4 peaks (from the lot flyer) |
| Reagents | PE antibody or isotype | name, isotype control?, host, isotype, catalog, lot, F/P, valency, MW, matched isotype |
| Cell_Lines | cell line | name, source ID, fluorescent reporter |
| Plates | plate | plate ID (as in the data files), bead run that calibrates it |
| Layout | plate row | plate, row, cell line, reagent, top final conc, dilution factor, first column, points, no-antibody column(s) |
| Controls | control well or tube | type (unstained, PE only, live/dead only, reporter only), plate + well or data file |

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
- no PE-only control, or a reporter cell line without a reporter-only control (unmixing)

`--wells` writes one line per well with cell line, reagent and final concentration.

## Analyze FlowJo exports
```
python -m qfacs analyze my_setup.xlsx path/to/exports/ [-o results.xlsx]
```
Inputs are FlowJo table exports (.xls, .xlsx, .csv or .txt), one row per sample (named from the well, e.g. `E01-Sample_049`):
- cell exports with `<gate path> | Geometric Mean (<PE parameter>)` and optionally `<gate path> | Count` for the live gate.
  A file belongs to the plate whose Plate ID starts its name (`Plate1_A431.xls` -> Plate1).
- a bead export (name contains "bead") with gates named Low, Med Low, Med High and High.

The results workbook has Summary (cell line x antibody antigens/cell and flags), Plots, Fits, Wells, Beads and Issues.

Method:
1. Bead curve per bead run: log10(gMFI) = slope x log10(PE/bead) + intercept; QC = R² and 80-120 % recovery.
2. PE/cell from gMFI; ABC = (PE/cell - same-row no-antibody PE/cell) / F:P.
3. Isotype ABC of the matched isotype on the same cell line, interpolated on log concentration; specific ABC = ABC - isotype ABC.
4. One-site fit per cell line x antibody (replicate plates pooled): specific ABC = Bmax x C / (Kd + C), 95 % CIs.
   Antigens/cell = Bmax x valency (blank valency = 1).
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

## From .fcs + .wsp
Put the setup workbook, the FlowJo workspace (.wsp, gated e.g. Cells > Single Cells > Live), the plate's .fcs
files (any subfolder) and the bead tube .fcs in one folder, then
```
python -m qfacs analyze FOLDER/my_setup.xlsx FOLDER
```
- Cells: the workspace's gates are applied with FlowKit. Live count and PE geometric mean per sample are written to
  `FOLDER/qfacs_gated/<Plate ID>_<workspace>_gated.xlsx` in FlowJo export layout. The plate comes from the .fcs
  `plateid` keyword (Plate_001 = Plate1), or the only plate in the setup.
- Geometric mean is computed the FlowJo v10 way: averaged on the parameter's biexponential display transform from
  the workspace, then transformed back. On Exp2290 Plate 1 this matches FlowJo's export to a median +0.2%
  (90% of wells within 0.5%); counts match to a median of <0.5%. Final antigens/cell agree within 0.3%.
- Beads: the bead .fcs (named on the Beads sheet, containing "bead", or the only .fcs left over) is gated
  automatically: the four peaks on log PE, valley to valley. On Exp2290 this is within 3% of the manual FlowJo gates.

## From .fcs only (no FlowJo workspace)
Put the setup workbook, the plate's .fcs files and the bead tube .fcs in one folder and run the same command.
Any .fcs not covered by a .wsp is gated automatically (`qfacs/autogate.py`), the way a FlowJo group gate works:
one set of Cells > Single Cells > Live gates is learned per plate and cell line from all of that line's wells
pooled, then applied to every well.
- Cells: main FSC-A / SSC-A population (density hull) above a debris cut at the valley below the main log FSC-A
  peak (never below 35% of the FSC-A mode).
- Single Cells: SSC-W below its main peak + 3 sigma (narrow side), and at least 1.3 x the peak.
- Live: viability dye (V6 (515)-A) below mode + 2.5 x the live peak's dim-side width, tilted with SSC like a
  hand-drawn V6 vs SSC gate. Type `none` on the
  Experiment sheet when no dye was used.
- Channels are set on the Experiment sheet (A8 defaults pre-filled). The learned gates are listed in the
  results' notes.
- Check against Mase's hand gates (same .fcs, same PE display transform), PE gMFI per well: CHO-EGFR median 0.6%
  (max 1.9%), U-87 MG median 3.3% (max 5.1%), A431 median 1.5% (max 5.5%). Antigens/cell vs the .wsp route:
  CHO-EGFR EGFR +2.6%; U-87 MG CD58 +2.6%, B7H3 +3.1%; A431 CD58 -3.4%, B7H3 -4.2%.
- With no workspace, PE gMFI uses the default biex display transform (positive 6.45, width -1000). FlowJo's gMFI
  depends on the transform set in each workspace, so expect a few % difference from a FlowJo export.
