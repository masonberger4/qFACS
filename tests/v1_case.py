"""Setup matching the Excel v1 Plate 1 example (values as entered in that workbook)."""
from pathlib import Path

from qfacs.model import Setup

DATA = Path(__file__).parent / "data" / "v1_plate1"


def v1_setup() -> Setup:
    s = Setup()
    s.experiment = dict(experiment_id="Exp2290", pe_parameter="B5 (575)-A", live_gate="Live", fixed_after_staining="N")
    s.beads = [dict(_row=5, bead_run="Set1", kit_lot="42618", pe_low=474, pe_med_low=5359, pe_med_high=23843, pe_high=62336)]
    mk = lambda name, iso, fp: dict(name=name, is_isotype=iso, host="Mouse", isotype="IgG1 k", fp_ratio=fp,
                                    matched_isotype=None if iso == "Y" else "mIgG1")
    s.reagents = [mk("CD58", "N", 1), mk("B7H3", "N", 1), mk("DLL3", "N", 1.357), mk("mIgG1", "Y", 1)]
    s.cell_lines = [dict(cell_line="H1975"), dict(cell_line="A549")]
    s.plates = [dict(plate_id="Plate1", bead_run="Set1")]
    for row, line, ab in zip("ABCDEFGH", ["H1975"] * 4 + ["A549"] * 4, ["CD58", "B7H3", "DLL3", "mIgG1"] * 2):
        s.layout.append(dict(plate_id="Plate1", row=row, cell_line=line, reagent=ab, top_conc_ug_ml=50,
                             dilution_factor=1.8, first_col=1, n_points=11, blank_cols="12"))
    for i, rec in enumerate(s.beads + s.reagents + s.cell_lines + s.plates + s.layout):
        rec.setdefault("_row", 5 + i)
    return s


def fits_of(res, model="Isotype"):
    """(cell line, antibody) -> FitRow of one fit model; pairs without that model (no isotype data) are left out."""
    return {k: d[model] for k, d in res.by_pair.items() if model in d}
