# qFACS

Automated qFACS workflow: flow cytometry data (.fcs) from the BD FACSDiscover A8 plus an experiment setup sheet,
calibrated with BD Quantibrite PE beads, to antigens (antibodies bound) per cell.

Project memory lives on the separate `memory` branch. The earlier Excel-only workbook is kept in `legacy/excel_v1/`.

## Status
Phase 1 of the build plan: the experiment setup workbook and its validator. The analysis engine (phase 2) comes next.

## Install
```
pip install -e ".[dev]"     # needs Python 3.10+; only dependency is openpyxl
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
are always entered by the user.

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
