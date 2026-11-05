from pathlib import Path

import numpy as np
import pytest

from qfacs.__main__ import main
from qfacs.analysis import analyze, interp_log, match_plate
from qfacs.calc import fit_beads, one_site_fit
from qfacs.stats_io import bead_gmfis, read_table, well_of, well_stats
from v1_case import DATA, v1_setup

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples" / "Exp2290_Set2_Plate1"


def v1_results():
    return analyze(v1_setup(), [str(DATA / "Plate1 H1975.csv"), str(DATA / "Plate1 A549.csv")],
                   [str(DATA / "Quantbrite PE Beads.csv")])


def test_reproduces_excel_v1_plate1():
    """Same inputs as legacy/excel_v1/qFACS_Plate1.xlsx -> same antigens/cell and Kd (to 0.1 %)."""
    res = v1_results()
    assert [i for i in res.issues if i.level == "error"] == []
    b = res.beads["Set1"]
    assert b.slope == pytest.approx(0.976528284488864, rel=1e-9)
    assert b.r2 == pytest.approx(0.999547051331197, rel=1e-9)
    got = {(f.cell_line, f.reagent): f for f in res.fits}
    expected = {("H1975", "CD58"): (80432.02, 2.794119), ("H1975", "B7H3"): (88986.66, 7.506645),
                ("A549", "CD58"): (56822.98, 1.533251), ("A549", "B7H3"): (62652.08, 6.072388)}
    for key, (bmax, kd) in expected.items():
        assert got[key].antigens == pytest.approx(bmax, rel=1e-3), key
        assert got[key].fit.kd == pytest.approx(kd, rel=1e-3), key
    assert got[("H1975", "DLL3")].status == "ND" and got[("A549", "DLL3")].status == "ND"
    assert got[("H1975", "CD58")].fit.bmax_ci[0] == pytest.approx(73982.43, rel=1e-3)


def test_bead_curve_matches_bd_example():
    pe = dict(pe_low=474, pe_med_low=5359, pe_med_high=23843, pe_high=62336)
    g = dict(pe_low=1661, pe_med_low=16383, pe_med_high=72239, pe_high=197572)
    c = fit_beads("S", pe, g)
    assert c.qc == "PASS"
    assert all(0.9 < v < 1.1 for v in c.recovery.values())
    assert c.pe_per_cell(g["pe_high"]) == pytest.approx(65199.6, rel=1e-4)


def test_one_site_fit_recovers_parameters():
    x = 50 / 1.8 ** np.arange(11)
    y = 120000 * x / (3.0 + x) * (1 + 0.01 * np.sin(np.arange(11)))
    f = one_site_fit(x, y)
    assert f.bmax == pytest.approx(120000, rel=0.02)
    assert f.kd == pytest.approx(3.0, rel=0.05)
    assert not f.nd and f.r2 > 0.99


def test_one_site_fit_flat_data_is_nd():
    x = 50 / 1.8 ** np.arange(11)
    f = one_site_fit(x, np.random.default_rng(1).normal(0, 50, 11))
    assert f.nd


def test_interp_log():
    pts = [(1.0, 10.0), (10.0, 20.0)]
    v, out = interp_log(pts, 10 ** 0.5)
    assert v == pytest.approx(15.0) and not out
    assert interp_log(pts, 100.0) == (20.0, True)


def test_read_flowjo_xls_exports():
    t = read_table(EX / "Plate1_U87.xls")
    assert len(t.rows) == 48  # Mean / SD rows dropped
    stats, notes = well_stats(t, "B5 (575)-A", "Live")
    a1 = next(s for s in stats if s.well == "A01")
    assert (a1.gmfi, a1.count) == (178441.0, 3477.0) and notes == []
    g = bead_gmfis(read_table(EX / "Quantbrite PE Beads.xls"), "B5 (575)-A")
    assert g == dict(pe_high=197572.0, pe_low=1661.0, pe_med_high=72239.0, pe_med_low=16383.0)
    assert well_of("E01-Sample_049") == "E01" and well_of("Tube_001") is None


def test_match_plate_by_file_name():
    plates = [dict(plate_id="Plate1"), dict(plate_id="Plate2")]
    assert match_plate("Plate1_A431.xls", plates) == "Plate1"
    assert match_plate("plate 2 H358.xls", plates) == "Plate2"
    assert match_plate("other.xls", plates) is None


def test_missing_isotype_and_missing_data_are_flagged():
    s = v1_setup()
    s.layout = [r for r in s.layout if r["row"] not in "DH"]  # drop the isotype rows
    res = analyze(s, [str(DATA / "Plate1 H1975.csv")], [str(DATA / "Quantbrite PE Beads.csv")])
    fits = {(f.cell_line, f.reagent): f for f in res.fits}
    assert "isotype data missing: not subtracted" in fits[("H1975", "CD58")].flags
    assert "no data for 11 well(s)" in fits[("A549", "CD58")].flags


def test_cli_end_to_end(tmp_path):
    out = tmp_path / "res.xlsx"
    rc = main(["analyze", str(EX / "Exp2290_Set2_setup.xlsx"), str(EX), "-o", str(out)])
    assert rc == 0 and out.exists()
    from openpyxl import load_workbook
    wb = load_workbook(out)
    assert wb.sheetnames[:3] == ["Summary", "Plots", "Fits"]
    fits = {(r[0], r[1]): r for r in wb["Fits"].iter_rows(min_row=2, values_only=True)}
    assert fits[("A431", "DLL3")][10] == "ND"
    assert fits[("U-87 MG", "CD58")][10] == pytest.approx(43164, rel=0.01)  # F/P 1.24, isotype F/P blank
    assert "low events in 2 well(s)" in fits[("A431", "CD58")][24]
    assert "isotype F/P unknown" in fits[("A431", "CD58")][24]


def test_blank_isotype_fp_subtracts_in_pe_units():
    """Isotype F/P blank -> (PE_ab - PE_iso) / F/P_ab; equals the old result when both F/P were equal."""
    s = v1_setup()
    for r in s.reagents:
        if r.get("is_isotype") == "Y":
            iso_fp, r["fp_ratio"] = r["fp_ratio"], None
    ref = {(f.cell_line, f.reagent): f for f in v1_results().fits}
    res = analyze(s, [str(DATA / "Plate1 H1975.csv"), str(DATA / "Plate1 A549.csv")], [str(DATA / "Quantbrite PE Beads.csv")])
    got = {(f.cell_line, f.reagent): f for f in res.fits}
    f = got[("H1975", "CD58")]
    assert "isotype F/P unknown: subtracted in PE units (assumes equal F/P)" in f.flags
    fp = s.reagent("CD58")["fp_ratio"]
    if fp == iso_fp:
        assert f.antigens == pytest.approx(ref[("H1975", "CD58")].antigens, rel=1e-9)
    w = next(w for w in res.wells if w.well.reagent == "CD58" and w.iso_abc is not None)
    assert w.specific == pytest.approx((w.net_pe - w.iso_abc * fp) / fp)
