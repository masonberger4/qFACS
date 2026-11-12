# Running qFACS on a new data set

From a new plate (or several) to antigens per cell. You gate in FlowJo and export the gated values to Excel;
qFACS works only from those Excel files and the setup workbook. No .wsp or .fcs files are needed, so the
numbers it uses are exactly FlowJo's.

## What you need

| # | File | Where it comes from |
|---|---|---|
| 1 | **Setup workbook** (.xlsx) | Copy `qFACS_setup_template.xlsx` (or `python -m qfacs template my_setup.xlsx`) and fill it in (step 1). A filled example: `EXAMPLE_filled_setup_Exp2290_Set2.xlsx`. |
| 2 | **FlowJo cell exports** (.xls/.xlsx), one per plate and cell line | FlowJo Table Editor export of the gated wells (step 2), named `<Plate ID> <cell line>.xls`, e.g. `Plate1 A431.xls`. |
| 3 | **FlowJo bead export**, one per bead tube | Table Editor export of the bead tube with gates named Low, Med Low, Med High, High. Put "bead" in the file name (e.g. `Quantbrite PE Beads.xls`), or name the file on the Beads sheet. |

Values you look up and type in (never built in): bead lot and PE molecules per bead for the four peaks (lot flyer),
each antibody's F/P (vial label or CoA; blank = 1 and flagged), valency (blank = 1), concentrations and dilution.

## Step 1. Fill in the setup workbook

Yellow cells are inputs, `*` marks required columns, and every column header has a note on how to get the value.

- **Experiment**: Experiment ID; PE parameter exactly as in the export column (A8: `B5 (575)-A`); live gate name (`Live`).
  QC thresholds come pre-filled.
- **Beads**: one row per bead tube: bead run ID, kit lot, PE/bead for Low, Med Low, Med High, High; optionally the
  bead export's file name.
- **Reagents**: one row per PE antibody and isotype: name, isotype control Y/N, host, isotype, F/P, valency,
  matched isotype (blank = the only isotype run on that cell line is used).
- **Cell_Lines**: one row per line. Use the same name you will put in the export file names (spaces, dashes and
  case don't matter: `Kasumi 2` = `Kasumi-2`; a shortened name like `U87` for `U87 MG` also works).
- **Plates**: plate ID (`Plate1`, `Plate2`, ...) and the bead run that calibrates it.
- **Layout**: one row per plate row: plate, row, cell line, reagent (antibody or isotype), top final conc (µg/mL),
  dilution factor, first column, number of points, no-antibody column(s). This is how every well is tied to its
  cell line, antibody and concentration.

Check it (fast, no data needed):
```
python -m qfacs validate my_setup.xlsx --wells wells.csv
```
Errors must be fixed; warnings are QC flags that travel with the results. `wells.csv` lists every well with its cell
line, reagent and concentration, so you can check the plate map.

## Step 2. Gate and export from FlowJo

1. Gate **Cells > Single Cells > Live** on the plate's wells as usual.
2. On **Live** add **Count** and **Geometric Mean** of the PE parameter (`B5 (575)-A`). Count is optional but lets
   qFACS flag wells with too few live events.
3. In the Table Editor, export one table per cell line (or one per plate) to Excel. Keep the sample names as the
   A8 writes them (`A01-Sample_001`): the well ID at the start ties each row to the Layout.
4. Name each file `<Plate ID> <cell line>.xls`, e.g. `Plate1 A431.xls`, `Plate2 FaDu.xls`. A file named only
   `Plate1.xls` also works: each well's cell line then comes from the Layout.
5. Export the bead tube the same way (gates Low, Med Low, Med High, High with Geometric Mean of PE).

## Step 3. Run it

### Option A: in this project (no install)
Upload the setup workbook and the export files to the project and ask in a new thread:
"Run qFACS on <experiment> with <setup file>". Results come back as a workbook.

### Option B: on your computer
One-time install (Python 3.10 or newer):
```
git clone https://github.com/masonberger4/qFACS
cd qFACS
pip install -e ".[dev]"
```
Put everything for the experiment in one folder:
```
Exp2300/
  Exp2300_setup.xlsx
  Plate1 A431.xls
  Plate1 U87 MG.xls
  Plate2 FaDu.xls
  Quantbrite PE Beads.xls
```
Then:
```
python -m qfacs analyze Exp2300/Exp2300_setup.xlsx Exp2300
```
It first prints one `FILE` line per export, showing what it understood, e.g.
```
FILE    Plate1 A431.xls: Plate1, A431 (from file name), 48 wells; CD58, B7H3, DLL3, mIgG1
```
then one line per cell line x antibody (antigens/cell and flags), and writes
`Exp2300/<Experiment ID>_qFACS_results.xlsx` (`-o` sets another name).

If a file is named for one cell line but holds wells the Layout gives to another, those wells are skipped and
flagged, so a mislabeled file cannot be mixed into the wrong cell line.

## Step 4. Read the results

| Sheet | What it holds |
|---|---|
| Summary | antigens/cell per cell line x antibody by both methods (isotype subtracted, NS fit), their ratio, and flags |
| Plots | titration curves with fits: isotype subtracted on the left, NS fit on the right |
| Fits | one row per fit model: Bmax, Kd, 95% CIs, flags |
| Wells | every well: gMFI, PE/cell, ABC, isotype, specific ABC, as live Excel formulas |
| Beads | bead curve, R², recovery |
| Data files | each export: plate, cell line, wells used, antibodies |
| Method | each calculation step in plain words |
| Issues | everything flagged |

Flags never remove data. The common ones: not saturated (top conc < 5x Kd), poor fit, low live events (< 1000),
F/P assumed 1, isotype mismatch, signal above the High bead (a note only).

## When something goes wrong

| Message | Fix |
|---|---|
| `could not tell which plate it belongs to` | Start the file name with the Plate ID, e.g. `Plate1 A431.xls`. |
| `is named for X but holds wells the Layout gives to another cell line` | Check the file name and the Layout rows for that plate. |
| `no 'Geometric Mean' column for B5 (575)-A` | Add Geometric Mean of the PE parameter to Live and export again, or fix the PE parameter on the Experiment sheet. |
| `bead gate(s) not found` | Name the bead gates Low, Med Low, Med High, High. |
| `several PE gMFI columns` | Set the live gate name on the Experiment sheet. |
| `no data for N well(s)` | Those Layout wells were in no export (a plate or cell line not exported yet). |
| validate errors | Fix the named sheet and row; each column note says what goes there. |
