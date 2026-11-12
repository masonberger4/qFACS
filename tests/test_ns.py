"""NS (non-specific binding) fit model: Y = Bmax*C/(Kd + C) + NS*C instead of isotype subtraction.

Reference values: QuantiBRITE_ABC_calculator.xlsx (Excel Solver, Bmax/Kd/NS >= 0), CD58 and B7H3 tabs (A549, gMFI).
The fit is linear in Bmax and NS, so fitting gMFI or ABC gives the same Kd and a proportional Bmax.
"""
import numpy as np
import pytest

from qfacs.analysis import analyze
from qfacs.calc import ns_fit, one_site_fit
from qfacs.validate import validate
from v1_case import DATA, fits_of, v1_setup

C = list(50 / 1.8 ** np.arange(11)) + [0.0]
CALC = {  # tab: (observed gMFI, Solver Bmax, Kd, SSE)
    "CD58": ([170823, 169129, 153959, 147382, 142686, 124223, 86253, 53694, 31770, 15924, 8104, 0],
             178279.197369035, 1.6069957090619158, 537149406.7057073),
    "B7H3": ([176856, 160102, 142423, 116084, 88497, 59107, 34531, 17644, 10693, 5363, 2881, 0],
             199620.30341311317, 6.382343496333397, 66206874.165651456),
}


def _sse(f, x, y):
    return float(np.sum((np.asarray(y) - f.predict(np.asarray(x))) ** 2))


@pytest.mark.parametrize("tab", CALC)
def test_ns_fit_matches_quantibrite_calculator(tab):
    y, bmax, kd, sse = CALC[tab]
    f = ns_fit(C, y)
    assert f.model == "NS" and not f.nd
    assert f.bmax == pytest.approx(bmax, rel=1e-4)
    assert f.kd == pytest.approx(kd, rel=1e-4)
    assert f.ns == pytest.approx(0, abs=1e-6)            # Solver: NS at its >= 0 bound
    assert _sse(f, C, y) <= sse * (1 + 1e-6)
    assert f.bmax_ci[0] < f.bmax < f.bmax_ci[1]


def test_ns_fit_beats_calculator_starting_values_on_dll3_and_egfr():
    """DLL3/EGFR tabs hold un-solved starting values; our fit must do at least as well and keep every parameter >= 0."""
    dll3_c = list(100 / 1.8 ** np.arange(11)) + [0.0]
    dll3 = [9113, 7206, 5966, 5297, 4702, 4267, 4221, 4107, 3971, 4036, 3953, 2572]
    egfr = [22029, 20318, 19263, 17922, 16875, 16172, 15689, 14331, 14270, 13207, 12097, 0]
    for x, y, sse in ((dll3_c, dll3, 106697906.0), (C, egfr, 54317156.0)):
        f = ns_fit(x, y)
        assert _sse(f, x, y) < sse
        assert f.bmax >= 0 and f.kd >= 0 and f.ns >= 0


def test_ns_fit_recovers_parameters():
    x = 200 / 1.8 ** np.arange(12)
    y = 80000 * x / (2.0 + x) + 150 * x
    f = ns_fit(x, y * (1 + 0.005 * np.sin(np.arange(12))))
    assert f.bmax == pytest.approx(80000, rel=0.03)
    assert f.kd == pytest.approx(2.0, rel=0.08)
    assert f.ns == pytest.approx(150, rel=0.1)
    # the plain one-site fit absorbs the NS line into an inflated Bmax
    assert one_site_fit(x, y).bmax > 1.1 * f.bmax


def test_ns_fit_negative_slope_data_keeps_ns_zero():
    x = 50 / 1.8 ** np.arange(11)
    f = ns_fit(x, 50000 * x / (1 + x) - 100 * x)
    assert f.ns == 0.0 and f.bmax > 0


def test_ns_fit_needs_five_points():
    assert ns_fit([1, 2, 3, 4], [1, 2, 3, 4]).nd


def _res(s):
    return analyze(s, [str(DATA / "Plate1 H1975.csv"), str(DATA / "Plate1 A549.csv")], [str(DATA / "Quantbrite PE Beads.csv")])


def test_both_models_reported_for_every_antibody():
    res = _res(v1_setup())
    iso, ns = fits_of(res), fits_of(res, "NS")
    assert set(iso) == set(ns) and len(res.fits) == 2 * len(ns)
    f, g = iso[("H1975", "CD58")], ns[("H1975", "CD58")]
    # isotype-subtracted row: unchanged from the single-model engine
    assert f.fit.model == "isotype" and f.fit.ns is None
    assert f.antigens == pytest.approx(80432.02, rel=1e-3)
    # NS row: fitted on ABC, no isotype subtraction, with its own Kd, CI and NS terms
    wells = [w for w in res.wells if w.well.reagent == "CD58" and w.well.cell_line == "H1975" and w.abc is not None]
    assert g.points == sorted((w.well.conc_ug_ml, w.abc) for w in wells)
    assert f.points == sorted((w.well.conc_ug_ml, w.abc - w.iso_abc) for w in wells)
    assert g.fit.model == "NS" and g.antigens is not None and g.fit.ns >= 0 and g.fit.bmax_ci and g.kd_nm
    assert g.ns_share_top is not None and 0 <= g.ns_share_top <= 1
    # each row points at the other model's result
    assert f.cross_antigens == g.antigens and g.cross_antigens == f.antigens
    assert f.ns_vs_iso == g.ns_vs_iso == pytest.approx(g.antigens / f.antigens)
    assert not any("isotype" in x and "NS fit only" in x for x in g.flags)


def test_no_isotype_gives_ns_only_and_flags_it():
    s = v1_setup()
    for r in s.reagents:
        r["matched_isotype"] = None
    s.layout = [r for r in s.layout if r["reagent"] != "mIgG1"]
    s.reagents = [r for r in s.reagents if r["name"] != "mIgG1"]
    assert any("has no single isotype to use; only the NS fit" in i.message for i in validate(s))
    res = _res(s)
    assert fits_of(res) == {}
    f = fits_of(res, "NS")[("H1975", "B7H3")]
    assert f.antigens is not None and f.cross is None and f.ns_vs_iso is None
    assert "no matched isotype: NS fit only" in f.flags


def test_blank_matched_isotype_uses_the_only_isotype_on_the_cell_line():
    """Mase's Exp2290 setup: isotype rows in the Layout, 'Matched isotype' left blank -> still subtracted, and flagged."""
    ref = fits_of(_res(v1_setup()))
    s = v1_setup()
    for r in s.reagents:
        r["matched_isotype"] = None
    assert any("mIgG1, the only isotype run on A549, H1975, is used" in i.message for i in validate(s))
    res = _res(s)
    f = fits_of(res)[("H1975", "CD58")]
    assert f.antigens == pytest.approx(ref[("H1975", "CD58")].antigens, rel=1e-9)
    assert "matched isotype blank: used mIgG1 (the only isotype on this cell line)" in f.flags
    assert fits_of(res, "NS")[("H1975", "CD58")].antigens is not None


def test_large_difference_between_models_is_flagged_on_both_rows():
    s = v1_setup()
    res = _res(s)
    for d in res.by_pair.values():
        f, g = d["Isotype"], d["NS"]
        differ = [x for x in g.flags if "vs isotype-subtracted" in x or "models disagree" in x]
        assert differ == [x for x in f.flags if "vs isotype-subtracted" in x or "models disagree" in x]
        if f.ns_vs_iso is not None:
            assert bool(differ) == (abs(f.ns_vs_iso - 1) > 0.25)
        elif (f.antigens is None) != (g.antigens is None):
            assert differ


def test_old_fit_model_setting_is_ignored_with_a_warning(tmp_path):
    from openpyxl import load_workbook
    from qfacs.setup_io import read_setup
    from qfacs.template import write_setup
    p = tmp_path / "s.xlsx"
    write_setup(p, v1_setup())
    wb = load_workbook(p)
    ws = wb["Experiment"]
    ws.append(["Fit model default (Isotype / NS)", "NS"])
    wb.save(p)
    setup, issues = read_setup(p)
    assert any("no longer used" in i.message and i.level == "warning" for i in issues)
    assert not any(i.level == "error" for i in issues)
    assert "fit_model" not in setup.experiment


def test_ns_qc_flags():
    """Kd outside the doses, NS dominating the top dose and a wide Bmax CI are flagged."""
    from qfacs.analysis import FitRow, _ns_flags
    from qfacs.calc import FitResult
    pts = [(c, 0.0) for c in (0.1, 1, 10)]
    f = FitRow("L", "Ab", {}, [], pts, FitResult(3, bmax=1000, kd=0.01, ns=500, model="NS"), top_conc=10)
    flags = _ns_flags(f, pts)
    assert any("below the lowest dose" in x for x in flags)
    assert any("non-specific is" in x and "top-dose" in x for x in flags)
    f.fit.kd, f.fit.ns = 50, 0
    assert any("above the top dose" in x for x in _ns_flags(f, pts))


def test_report_has_a_row_per_model(tmp_path):
    from openpyxl import load_workbook
    from qfacs.report import write_results
    res = _res(v1_setup())
    out = tmp_path / "r.xlsx"
    write_results(res, out)
    wb = load_workbook(out)
    hdr = [c.value for c in wb["Fits"][1]]
    rows = {(r[0], r[1], r[2]): dict(zip(hdr, r)) for r in wb["Fits"].iter_rows(min_row=2, values_only=True)}
    i, n = rows[("H1975", "CD58", "Isotype subtracted")], rows[("H1975", "CD58", "NS fit")]
    assert n["NS (ABC per µg/mL)"] is not None and i["NS (ABC per µg/mL)"] is None
    assert i["Kd (µg/mL)"] and n["Kd (µg/mL)"] and i["Bmax 95% CI low"] and n["Bmax 95% CI low"]
    assert n["Other model antigens/cell"] == i["Antigens/cell"] and i["Other model antigens/cell"] == n["Antigens/cell"]
    assert i["NS fit ÷ isotype subtracted"] == pytest.approx(n["Antigens/cell"] / i["Antigens/cell"], rel=0.01)
    ws = wb["Wells"]
    k = next(k for k, w in enumerate(res.wells, 2) if w.well.reagent == "CD58" and w.abc is not None)
    assert ws[f"P{k}"].value == f"=N{k}-O{k}"
    assert len(wb["Plots"]._charts) == len(res.fits)
    text = " ".join(str(c.value) for c in wb["Method"]["A"] if c.value)
    assert "Isotype subtracted:" in text and "NS fit:" in text and "(none in this experiment)" in text
