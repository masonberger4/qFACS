"""Build the setup for the CHO-EGFR run (plate 'CHO EGFR', acquired 2026-11-04; beads Tube_001 2026-11-05).

From Mase's 2026-11-09 upload: setup sheet screenshot (antibodies, lots, stocks) and plate map
(row A EGFR, row B mIgG1, 50 µg/mL top, 1.8x, 11 points, column 12 no antibody).
EGFR F/P was blank on the setup sheet, so it is left blank here (analysis assumes 1, flagged).
Bead lot values are PLACEHOLDERS from the v1 workbook (lot 42618) until Mase gives the kit lot in use.
Rows C-D (no antibody on the plate map) are left out of the Layout until Mase says what they are.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qfacs.model import Setup  # noqa: E402
from qfacs.template import write_setup  # noqa: E402

PH = "PLACEHOLDER: lot 42618 values from the v1 workbook; replace with the kit lot used on 2026-11-05"
s = Setup()
s.experiment = dict(experiment_id="CHO-EGFR_Plate3", date="2026-11-04", instrument="BD FACSDiscover A8",
                    pe_parameter="B5 (575)-A", live_gate="Live", min_live_events=1000, bead_r2_min=0.98, saturation_k=5,
                    notes="Setup sheet set 11.3.26. Cells acquired 2026-11-04 (05-Nov-2026.wsp: Cells > Single Cells > Live); "
                          "beads Tube_001 acquired 2026-11-05 (09-Nov-2026.wsp). Fixation not stated.")
s.beads = [dict(bead_run="Beads_2026-11-05", kit_lot="42618 (confirm)", lot_expiry="2022-10-31", pe_low=474, pe_med_low=5359,
                pe_med_high=23843, pe_high=62336, data_file="Beads Analysis.xls", notes=PH)]
s.reagents = [
    dict(name="EGFR", target="EGFR", is_isotype="N", host="Mouse", isotype="IgG1, κ", clone="AY13", vendor="BioLegend",
         catalog="352904", lot="B433431", stock_ug_ml=100, matched_isotype="mIgG1",
         notes="F/P blank on the setup sheet: assumed 1 (1:1 PE conjugate). Enter the vial/CoA F/P if known."),
    dict(name="mIgG1", target="Isotype control", is_isotype="Y", host="Mouse", isotype="IgG1, κ", clone="MOPC-21",
         vendor="BioLegend", catalog="400114", stock_ug_ml=200,
         notes="Lot and F/P not given ('-' on the setup sheet): isotype subtracted in PE units"),
]
s.cell_lines = [dict(cell_line="CHO-EGFR", notes="CHO cells expressing EGFR")]
s.plates = [dict(plate_id="CHO EGFR", bead_run="Beads_2026-11-05", acquired="2026-11-04", data_folder="Plate3",
                 notes="FlowJo export 'Plate3 CHO-EGFR.xls'")]
for row, ab in (("A", "EGFR"), ("B", "mIgG1")):
    s.layout.append(dict(plate_id="CHO EGFR", row=row, cell_line="CHO-EGFR", reagent=ab, top_conc_ug_ml=50,
                         dilution_factor=1.8, first_col=1, n_points=11, blank_cols="12"))
out = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(__file__).resolve().parents[1] / "examples" / "CHO_EGFR_Plate3" / "CHO-EGFR_setup.xlsx"
write_setup(out, s)
print("wrote", out)
