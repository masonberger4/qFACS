# Running qFACS on a new data set

From a new plate (or several) to antigens per cell. You gate in FlowJo; qFACS does everything after that.

## What you need

| # | File | Where it comes from |
|---|---|---|
| 1 | **Setup workbook** (.xlsx) | Copy `examples/qFACS_setup_template.xlsx` (or `python -m qfacs template my_setup.xlsx`) and fill it in (step 1 below). A filled example: `examples/Exp2290_Set2_Plate1/Exp2290_Set2_setup.xlsx`. |
| 2 | **FlowJo workspace** (.wsp), one per plate | You draw Cells > Single Cells > Live and add two statistics to Live (step 2). |
| 3 | **Bead data**, one per bead tube | Any one of: a FlowJo table export of the bead tube (file name contains "bead", gates named Low, Med Low, Med High, High); a bead .wsp with those four gates; or the bead tube .fcs alone (peaks found automatically; name it on the Beads sheet or put "bead" in the file name when there is more than one bead tube). |
| 4 | .fcs files | Optional. Only needed if a .wsp has no saved statistics (qFACS then re-applies the gates itself) or for a bead tube given only as .fcs. |

Values you look up and type in (never built in): bead lot and PE molecules per bead for the four peaks (lot flyer),
each antibody's F/P (vial label or CoA; blank = 1 and flagged), valency (blank = 1), concentrations and dilution.

## Step 1. Fill in the setup workbook

Yellow cells are inputs, `*` marks required columns, and every column header has a note on how to get the value.

- **Experiment**: Experiment ID; PE parameter exactly as in the data (A8: `B5 (575)-A`); live gate name (`Live`).
  QC thresholds come pre-filled.
- **Beads**: one row per bead tube: bead run ID, kit lot, PE/bead for Low, Med Low, Med High, High; optionally the
  bead data file name.
- **Reagents**: one row per PE antibody and isotype: name, isotype control Y/N, host, isotype, F/P, valency,
  matched isotype, fit model (Isotype default, or NS when no isotype was run).
- **Cell_Lines**: one row per line.
- **Plates**: plate ID and the bead run that calibrates it. Use `Plate1`, `Plate2`, ...: the A8's `Plate_001` in the
  .fcs/.wsp is matched to `Plate1` automatically.
- **Layout**: one row per plate row: plate, row, cell line, reagent, top final conc (µg/mL), dilution factor, first
  column, number of points, no-antibody column(s).
- **Controls**: optional control wells or tubes.

Check it (fast, no data needed):
```
python -m qfacs validate my_setup.xlsx --wells wells.csv
```
Errors must be fixed; warnings are QC flags that travel with the results. `wells.csv` lists every well with its cell
line, reagent and concentration, so you can check the plate map.

## Step 2. Gate in FlowJo and save the workspace

1. Open the plate's .fcs files in FlowJo (one workspace per plate). Make a group per cell line if you like.
2. Draw **Cells > Single Cells > Live** and apply it to the wells (group gating is fine).
3. On the **Live** population add two statistics: **Count** and **Geometric Mean** of the PE parameter
   (`B5 (575)-A`). This is what lets qFACS read FlowJo's own numbers straight from the .wsp.
4. Let FlowJo finish recalculating, then **save** the workspace. qFACS reads the values as of the last save.

Wells must keep the A8 names (`A01-Sample_001`): the well ID at the start is how wells are matched to the Layout.

## Step 3. Run it

### Option A: in this project (no install)
Upload the setup workbook, the .wsp file(s) and the bead data to the project, and ask in a new thread:
"Run qFACS on <experiment> with <setup file>". Results come back as a workbook.

### Option B: on your computer
One-time install (Python 3.10 or newer):
```
git clone https://github.com/masonberger4/qFACS
cd qFACS
pip install -e ".[dev,fcs]"
```
Put everything for the experiment in one folder:
```
Exp2300/
  Exp2300_setup.xlsx
  Plate_001.wsp            (any names; one .wsp per plate)
  Plate_002.wsp
  Quantbrite PE Beads.xls  (or the bead .wsp, or Tube_001.fcs)
```
Then:
```
python -m qfacs analyze Exp2300/Exp2300_setup.xlsx Exp2300
```
It prints one line per cell line x antibody (antigens/cell and flags) and writes
`Exp2300/<Experiment ID>_qFACS_results.xlsx` (`-o` sets another name). The per-well numbers it read are kept in
`Exp2300/qfacs_gated/` in FlowJo export layout. Look for lines like
`Plate_001.wsp: FlowJo's saved Live count and gMFI used for 96 samples of Plate1 (no re-gating)`.

Already have FlowJo table exports instead of a .wsp? Put them in the folder named `Plate1_<anything>.xls`
(the plate ID starts the name) and run the same command.

## Step 4. Read the results

| Sheet | What it holds |
|---|---|
| Summary | antigens/cell per cell line x antibody, with flags |
| Plots | titration curves with fits |
| Fits | Bmax, Kd, 95% CIs, the cross-check method (NS vs isotype) |
| Wells | every well: gMFI, PE/cell, ABC, isotype, specific ABC, as live Excel formulas |
| Beads | bead curve, R², recovery |
| Method | each calculation step in plain words |
| Issues | everything flagged |

Flags never remove data. The common ones: not saturated (top conc < 5x Kd), poor fit, low live events (< 1000),
F/P assumed 1, isotype mismatch, signal above the High bead (a note only).

## When something goes wrong

| Message | Fix |
|---|---|
| `no saved B5 (575)-A Geometric Mean ... and no .fcs files to re-gate` | Add Count and Geometric Mean (PE) to Live in FlowJo, let it recalculate, save. Or put the plate's .fcs files in the folder. |
| `plate 'Plate_005' not on the Plates sheet` | Add the plate to Plates (as `Plate5`). |
| `bead gate(s) not found` | Name the bead gates Low, Med Low, Med High, High in the bead export. |
| `several PE gMFI columns` | Set the live gate name on the Experiment sheet. |
| validate errors | Fix the named sheet and row; each column note says what goes there. |
