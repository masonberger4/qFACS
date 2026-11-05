import copy
from pathlib import Path

import pytest

from qfacs.model import Setup
from qfacs.setup_io import read_setup
from qfacs.template import write_setup
from qfacs.validate import validate
from qfacs.wellmap import expand_wells, parse_cols

ROOT = Path(__file__).resolve().parents[1]


def good_setup() -> Setup:
    s = Setup()
    s.experiment = dict(experiment_id="ExpTest", pe_parameter="PE-A", live_gate="Live", fixed_after_staining="N")
    s.beads = [dict(bead_run="Set1", kit_lot="L1", pe_low=500, pe_med_low=5000, pe_med_high=24000, pe_high=62000)]
    s.reagents = [
        dict(name="CD58", target="CD58", is_isotype="N", host="Mouse", isotype="IgG1, κ", fp_ratio=1.2, matched_isotype="mIgG1"),
        dict(name="mIgG1", is_isotype="Y", host="Mouse", isotype="IgG1 kappa", fp_ratio=1.0),
    ]
    s.cell_lines = [dict(cell_line="H1975"), dict(cell_line="A549")]
    s.plates = [dict(plate_id="Plate1", bead_run="Set1")]
    s.layout = [
        dict(plate_id="Plate1", row="A", cell_line="H1975", reagent="CD58", top_conc_ug_ml=50, dilution_factor=1.8,
             first_col=1, n_points=11, blank_cols="12"),
        dict(plate_id="Plate1", row="B", cell_line="H1975", reagent="mIgG1", top_conc_ug_ml=50, dilution_factor=1.8,
             first_col=1, n_points=11, blank_cols="12"),
    ]
    s.controls = [dict(control_id="PE1", type="PE only", data_file="pe_only.fcs")]
    return s


def roundtrip(tmp_path, s: Setup):
    p = tmp_path / "setup.xlsx"
    write_setup(p, s)
    s2, parse_issues = read_setup(p)
    return s2, parse_issues + validate(s2)


def messages(issues, level=None):
    return [i.message for i in issues if level is None or i.level == level]


def test_blank_template_reports_missing_basics(tmp_path):
    p = tmp_path / "t.xlsx"
    write_setup(p)
    s, issues = read_setup(p)
    errs = messages(issues + validate(s), "error")
    assert "Experiment ID is required" in errs
    assert any("no bead run" in e for e in errs)
    assert any("no plate rows" in e for e in errs)


def test_good_setup_roundtrips_clean(tmp_path):
    s, issues = roundtrip(tmp_path, good_setup())
    assert [i for i in issues if i.level == "error"] == []
    assert messages(issues, "warning") == []
    assert s.experiment["experiment_id"] == "ExpTest"
    assert s.layout[0]["first_col"] == 1 and isinstance(s.layout[0]["first_col"], int)


def test_well_map_concentrations(tmp_path):
    s, _ = roundtrip(tmp_path, good_setup())
    wells = {w.well: w for w in expand_wells(s)[0]}
    assert len(wells) == 24
    assert wells["A01"].conc_ug_ml == pytest.approx(50)
    assert wells["A02"].conc_ug_ml == pytest.approx(50 / 1.8)
    assert wells["A11"].conc_ug_ml == pytest.approx(50 / 1.8 ** 10)
    assert wells["A12"].role == "blank" and wells["A12"].reagent is None


def test_isotype_host_mismatch_is_flagged(tmp_path):
    s = good_setup()
    s.reagents[0].update(host="Rabbit", isotype="Fc chimera")
    _, issues = roundtrip(tmp_path, s)
    assert any("isotype mismatch" in m for m in messages(issues, "warning"))


def test_isotype_check_needs_host_and_isotype(tmp_path):
    s = good_setup()
    s.reagents[1]["host"] = None
    _, issues = roundtrip(tmp_path, s)
    assert any("cannot check the isotype match" in m for m in messages(issues, "warning"))


def test_isotype_not_run_on_cell_line(tmp_path):
    s = good_setup()
    s.layout.append(dict(plate_id="Plate1", row="C", cell_line="A549", reagent="CD58", top_conc_ug_ml=50,
                         dilution_factor=1.8, first_col=1, n_points=11, blank_cols="12"))
    _, issues = roundtrip(tmp_path, s)
    assert "CD58 runs on A549 but its matched isotype mIgG1 does not" in messages(issues, "warning")


def test_overlapping_wells_and_bad_columns(tmp_path):
    s = good_setup()
    s.layout.append(dict(plate_id="Plate1", row="A", cell_line="H1975", reagent="mIgG1", top_conc_ug_ml=50,
                         dilution_factor=1.8, first_col=5, n_points=2))
    s.layout.append(dict(plate_id="Plate1", row="D", cell_line="H1975", reagent="CD58", top_conc_ug_ml=50,
                         dilution_factor=1.8, first_col=6, n_points=11))
    _, issues = roundtrip(tmp_path, s)
    errs = messages(issues, "error")
    assert any("A05 on plate Plate1 is also used" in e for e in errs)
    assert any("columns must be 1-12" in e for e in errs)


def test_bead_values_must_rise_and_refs_must_exist(tmp_path):
    s = good_setup()
    s.beads[0]["pe_med_high"] = 400
    s.plates[0]["bead_run"] = "Set9"
    s.layout[0]["reagent"] = "Nope"
    _, issues = roundtrip(tmp_path, s)
    errs = messages(issues, "error")
    assert any("must rise" in e for e in errs)
    assert any("bead run 'Set9'" in e for e in errs)
    assert any("reagent 'Nope'" in e for e in errs)


def test_unparseable_cells_are_reported(tmp_path):
    s = good_setup()
    s.reagents[0]["fp_ratio"] = "about one"
    s.experiment["fixed_after_staining"] = "maybe"
    _, issues = roundtrip(tmp_path, s)
    errs = messages(issues, "error")
    assert any("F/P (PE per antibody)' must be a number" in e for e in errs)
    assert any("must be Y or N" in e for e in errs)


def test_missing_no_antibody_well_and_reporter_control(tmp_path):
    s = good_setup()
    for rec in s.layout:
        rec["blank_cols"] = None
    s.cell_lines[0]["reporter"] = "GFP"
    _, issues = roundtrip(tmp_path, s)
    warns = messages(issues, "warning")
    assert any("has no no-antibody well" in w for w in warns)
    assert any("carries GFP but has no reporter-only control" in w for w in warns)


def test_parse_cols():
    assert parse_cols("12") == [12]
    assert parse_cols("11, 12") == [11, 12]
    assert parse_cols(None) == []
    with pytest.raises(ValueError):
        parse_cols("x")


def test_exp2281_example():
    s, issues = read_setup(ROOT / "examples" / "Exp2281_setup.xlsx")
    issues = issues + validate(s)
    wells, _ = expand_wells(s)
    assert len(s.plates) == 5 and len(wells) == 480
    errs = messages(issues, "error")
    # bead lot values and two F/P ratios are not in the source workbook: the user must enter them
    assert sum("PE/bead" in e for e in errs) == 4
    assert sum("F/P" in e for e in errs) == 2
    assert any("DLL3 is Rabbit" in w for w in messages(issues, "warning"))
