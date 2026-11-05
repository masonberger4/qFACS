"""Build the setup for the Exp2290 Set 2 Plate 1 example (U-87 MG rows A-D, A431 rows E-H).

Layout and CD58/B7H3 F/P confirmed by Mase (2026-11-05). DLL3 F/P is the vial-label value from the v1 workbook;
the isotype F/P is unknown. Bead lot values are from the v1 workbook and still need checking against the kit flyer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qfacs.model import Setup  # noqa: E402
from qfacs.template import write_setup  # noqa: E402

PH = "PLACEHOLDER from the v1 workbook; confirm"
s = Setup()
s.experiment = dict(experiment_id="Exp2290_Set2", date="2026-10-30", instrument="BD FACSDiscover A8",
                    pe_parameter="B5 (575)-A", live_gate="Live", fixed_after_staining="Y", min_live_events=1000,
                    bead_r2_min=0.98, saturation_k=5,
                    notes="Example built from FlowJo exports Plate1_U87.xls / Plate1_A431.xls; layout assumed as in Exp2281")
s.beads = [dict(bead_run="Set2", kit_lot="42618", lot_expiry="2022-10-31", pe_low=474, pe_med_low=5359,
                pe_med_high=23843, pe_high=62336, data_file="Quantbrite PE Beads.xls", notes=PH)]
s.reagents = [
    dict(name="CD58", target="CD58 (LFA-3)", is_isotype="N", host="Mouse", isotype="IgG1, κ", clone="TS2/9", vendor="BioLegend",
         catalog="330928", lot="B511152", fp_ratio=1.24, matched_isotype="mIgG1", notes="F/P confirmed by Mase (Exp2281 Design sheet)"),
    dict(name="B7H3", target="CD276 (B7-H3)", is_isotype="N", host="Mouse", isotype="IgG1, κ", clone="MIH42", vendor="BioLegend",
         catalog="351004", lot="B487135", fp_ratio=1.2, matched_isotype="mIgG1", notes="F/P confirmed by Mase (Exp2281 Design sheet)"),
    dict(name="DLL3", target="DLL3", is_isotype="N", host="Rabbit", isotype="(chimeric)", clone="SC16.15", vendor="Novus",
         catalog="NBP3-45128PE", lot="D224308", fp_ratio=1.357, matched_isotype="mIgG1", notes="F/P 1.357 from the vial label in the v1 workbook; blank on the Exp2281 Design sheet, confirm"),
    dict(name="mIgG1", is_isotype="Y", host="Mouse", isotype="IgG1, κ", clone="MOPC-21", vendor="BioLegend", catalog="400114",
         notes="F/P not given ('-' on the Exp2281 Design sheet): isotype subtracted in PE units"),
]
s.cell_lines = [dict(cell_line="U-87 MG", source_id="FP# 7695"), dict(cell_line="A431", source_id="FP# 7768")]
s.plates = [dict(plate_id="Plate1", bead_run="Set2", acquired="2026-10-30", data_folder="Plate1")]
for row, line, ab in zip("ABCDEFGH", ["U-87 MG"] * 4 + ["A431"] * 4, ["CD58", "B7H3", "DLL3", "mIgG1"] * 2):
    s.layout.append(dict(plate_id="Plate1", row=row, cell_line=line, reagent=ab, top_conc_ug_ml=50, dilution_factor=1.8,
                         first_col=1, n_points=11, blank_cols="12"))
out = Path(__file__).resolve().parents[1] / "examples" / "Exp2290_Set2_Plate1" / "Exp2290_Set2_setup.xlsx"
write_setup(out, s)
print("wrote", out)
