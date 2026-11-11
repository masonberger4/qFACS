"""NS (non-specific binding) fit model: Y = Bmax*C/(Kd + C) + NS*C instead of isotype subtraction.

Reference values: QuantiBRITE_ABC_calculator.xlsx (Excel Solver, Bmax/Kd/NS >= 0), CD58 and B7H3 tabs (A549, gMFI).
The fit is linear in Bmax and NS, so fitting gMFI or ABC gives the same Kd and a proportional Bmax.
"""
import numpy as np
import pytest

from qfacs.analysis import analyze
from qfacs.calc import ns_fit, one_site_fit
from qfacs.validate import validate
from v1_case import DATA, v1_setup

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


def _run(s):
    return {(f.cell_line, f.reagent): f for f in analyze(
        s, [str(DATA / "Plate1 H1975.csv"), str(DATA / "Plate1 A549.csv")], [str(DATA / "Quantbrite PE Beads.csv")]).fits}


def test_isotype_stays_the_default():
    fits = _run(v1_setup())
    f = fits[("H1975", "CD58")]
    assert f.model == "Isotype" and f.fit.model == "isotype" and f.fit.ns is None
    assert f.antigens == pytest.approx(80432.02, rel=1e-3)
    # isotype data exists, so the NS fit on the unsubtracted ABC is reported as a cross-check
    assert f.cross is not None and f.cross.model == "NS" and f.cross_antigens is not None
    assert not any("NS" in x for x in f.flags)


def test_ns_model_skips_isotype_subtraction_and_cross_checks():
    s = v1_setup()
    s.reagent("CD58")["fit_model"] = "NS"
    res = analyze(s, [str(DATA / "Plate1 H1975.csv"), str(DATA / "Plate1 A549.csv")], [str(DATA / "Quantbrite PE Beads.csv")])
    fits = {(f.cell_line, f.reagent): f for f in res.fits}
    f = fits[("H1975", "CD58")]
    assert f.model == "NS" and f.fit.model == "NS"
    wells = [w for w in res.wells if w.well.reagent == "CD58" and w.well.cell_line == "H1975" and w.abc is not None]
    assert all(w.specific == w.abc for w in wells)                     # fit input is ABC, not ABC - isotype
    assert all(w.iso_sub == pytest.approx(w.abc - w.iso_abc) for w in wells)
    assert f.points == sorted((w.well.conc_ug_ml, w.abc) for w in wells)
    assert f.antigens is not None and f.fit.ns is not None and f.fit.ns >= 0
    assert f.ns_share_top is not None and 0 <= f.ns_share_top <= 1
    # cross-check = the isotype method on the same wells = the default result
    assert f.cross.model == "isotype"
    assert f.cross_antigens == pytest.approx(_run(v1_setup())[("H1975", "CD58")].antigens, rel=1e-9)
    assert not any("isotype" in x and "not subtracted" in x for x in f.flags)
    # other antibodies are untouched
    assert fits[("H1975", "B7H3")].model == "Isotype"


def test_experiment_default_and_no_isotype_needed():
    s = v1_setup()
    s.experiment["fit_model"] = "NS"
    for r in s.reagents:
        r["matched_isotype"] = None
    s.layout = [r for r in s.layout if r["reagent"] != "mIgG1"]
    s.reagents = [r for r in s.reagents if r["name"] != "mIgG1"]
    msgs = [i.message for i in validate(s)]
    assert not any("no matched isotype" in m for m in msgs)
    fits = _run(s)
    f = fits[("H1975", "B7H3")]
    assert f.model == "NS" and f.cross is None and f.antigens is not None
    assert not any("isotype" in x for x in f.flags)
    s.reagent("B7H3")["fit_model"] = "isotype"           # per-antibody override, any case
    assert _run(s)[("H1975", "B7H3")].model == "Isotype"


def test_bad_fit_model_is_an_error():
    s = v1_setup()
    s.reagent("CD58")["fit_model"] = "Langmuir"
    errs = [i for i in validate(s) if i.level == "error"]
    assert any("fit model 'Langmuir'" in i.message for i in errs)


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


def test_report_has_ns_columns(tmp_path):
    from openpyxl import load_workbook
    from qfacs.report import write_results
    s = v1_setup()
    s.reagent("CD58")["fit_model"] = "NS"
    res = analyze(s, [str(DATA / "Plate1 H1975.csv"), str(DATA / "Plate1 A549.csv")], [str(DATA / "Quantbrite PE Beads.csv")])
    out = tmp_path / "r.xlsx"
    write_results(res, out)
    wb = load_workbook(out)
    hdr = [c.value for c in wb["Fits"][1]]
    rows = {(r[0], r[1]): dict(zip(hdr, r)) for r in wb["Fits"].iter_rows(min_row=2, values_only=True)}
    r = rows[("H1975", "CD58")]
    assert r["Fit model"] == "NS" and r["NS (ABC per µg/mL)"] is not None
    assert r["Cross-check model"] == "isotype" and r["Cross-check antigens/cell"] is not None
    assert rows[("H1975", "B7H3")]["Fit model"] == "Isotype"
    ws = wb["Wells"]
    i = next(k for k, w in enumerate(res.wells, 2) if w.well.reagent == "CD58" and w.abc is not None)
    assert ws[f"P{i}"].value == f"=N{i}"


def test_method_sheet_names_ns_antibodies(tmp_path):
    from openpyxl import load_workbook
    from qfacs.report import write_results
    s = v1_setup()
    s.reagent("CD58")["fit_model"] = "NS"
    res = analyze(s, [str(DATA / "Plate1 H1975.csv")], [str(DATA / "Quantbrite PE Beads.csv")])
    out = tmp_path / "r.xlsx"
    write_results(res, out)
    text = " ".join(str(c.value) for c in load_workbook(out)["Method"]["A"] if c.value)
    assert "NS model (used for: CD58)" in text and "Isotype model (used for: B7H3, DLL3)" in text
