# Exp2290: both methods, per set

One-off scripts that analyse the three Exp2290 sets with the qFACS engine and with the method of
`QuantiBRITE_ABC_calculator.xlsx`, and write, per set, an analysis workbook (layout of Mase's `Exp2290_Analysis.xlsx`)
and one FlowJo-style export per cell line (layout of `Plate1 A549.xls`).

| Set | Lab setup sheet | Data |
|---|---|---|
| Set1 | `Exp2290_qFACS_Setup.xlsx`, `Plate Maps 10.19.26` | no .fcs: FlowJo gMFI table in `Exp2290_Analysis.xlsx` |
| Set2 | `Exp2290_qFACS_Setup2.xlsx`, `Plate Maps 10.28.26` | `Plate_001`-`004` .fcs + `02-Nov-2026*.wsp` |
| Set3 | `Exp2290_qFACS_Setup3.xlsx`, `Plate Maps` | `Kasumi 2 HT55`, `CHO EGFR` .fcs + .wsp (Plate 2 not supplied) |

```
# FlowJo's own table straight from a workspace: reads the gate counts and Live gMFI FlowJo saved in the .wsp
# (no .fcs, no re-gating). Matches FlowJo's Table Editor export cell for cell on the three exports Mase supplied.
python wsp_export.py "02-Nov-2026.wsp" OUT/Set2/flowjo_exports Plate1
# Set 1 has no workspace: rebuild the exports from the FlowJo table in Exp2290_Analysis.xlsx
python set1_exports.py Exp2290_Analysis.xlsx Exp2290_qFACS_Setup.xlsx OUT/Set1/cell_line_exports
# exact-layout replicas of Mase's own files for a set, on the numbers saved in the .wsp: 'PlateN <line>.xls' in the
# five-column layout of 'Plate1 A549.xls' (cell_line_exports/), FlowJo's six-column table (flowjo_exports/) and his
# Exp2290_Analysis.xlsx itself refilled (edited at the XML level so his styles, charts, picture and hidden sheets stay)
python replicas.py Set2 Exp2290_qFACS_Setup2.xlsx Exp2290_Analysis.xlsx OUT/Set2 --beads 1661 16383 72239 197572 \
    --bead-name "Tube_001 (20-Oct-2026)" --plate 1 "02-Nov-2026.wsp" --plate 2 "02-Nov-2026 2.wsp"
# (gate_export.py re-applies the workspace gates to the .fcs files instead; kept as a cross-check, within about 1 %)
# both methods + workbooks (reads flowjo_exports when it exists, else cell_line_exports)
python run_set.py Set2 Exp2290_qFACS_Setup2.xlsx OUT/Set2 "Quantbrite PE Beads.xls"
# one QuantiBRITE_ABC_calculator.xlsx per cell line (Mase's workbook refilled: beads, unstained-subtracted Live gMFI,
# F/P and the solved Bmax, Kd, NS; tabs for antibodies not run on the line are removed) -> OUT/Set2/abc_calculator/
python calc_books.py Set2 Exp2290_qFACS_Setup2.xlsx OUT/Set2 "Quantbrite PE Beads.xls" QuantiBRITE_ABC_calculator.xlsx
# check abc_calc.py against the calculator's solved tabs
python abc_calc.py QuantiBRITE_ABC_calculator.xlsx
```

Methods
- Engine (`qfacs`): log-log bead curve, PE/cell per well, minus the same-row no-antibody well, / F:P, minus the isotype
  at the same concentration, one-site fit; antigens/cell = Bmax.
- Calculator (`abc_calc.py`): linear bead slope m; Y = gMFI - same-row no-antibody gMFI; Y = Bmax*C/(Kd+C) + NS*C with
  Bmax, Kd, NS >= 0 over the 11 points plus (0, 0); ABC = Bmax / m / (F:P). Reproduces the workbook's solved CD58 and
  B7H3 tabs exactly. "ND" when Bmax = 0, or when Bmax is only a flat offset (Kd below the lowest dose and the NS line
  is more than half of the top-dose signal).

Assumptions to confirm with Mase: Set 2 uses the 20-Oct-2026 bead tube (none supplied for Set 2); DLL3 F/P 1.357
(vial label) rather than the 0.8 on the Set 1 sheet; EGFR F/P blank = 1.
