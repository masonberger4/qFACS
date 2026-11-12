"""The Python version of QuantiBRITE_ABC_calculator.xlsx must land on the workbook's Solver solutions."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "exp2290"))
import abc_calc  # noqa: E402

CONC = [50 / 1.8 ** k for k in range(11)] + [0.0]
# 'Observed gMFI' columns of the workbook's solved CD58 and B7H3 tabs
CD58 = [32477, 26474, 22354, 20221, 18560, 15163, 9998, 7561, 4101, 2541, 1267, 0]
B7H3 = [176856, 160102, 142423, 116084, 88497, 59107, 34531, 17644, 10693, 5363, 2881, 0]


def test_bead_slope():
    m, c, r2 = abc_calc.bead_line([474, 5359, 23843, 62336], [1668, 16312, 72171, 198832])
    assert m == pytest.approx(3.1926448, rel=1e-6)
    assert c == pytest.approx(-1194.6585, rel=1e-5)
    assert r2 == pytest.approx(0.99956090, rel=1e-6)


def test_cd58_tab():
    f = abc_calc.abc(abc_calc.fit_total_binding(CONC, CD58), 3.1926448088, 1.24)
    assert f.bmax == pytest.approx(22157.25, rel=1e-4)
    assert f.kd == pytest.approx(1.67045, rel=1e-4)
    assert f.ns == pytest.approx(213.251, rel=1e-4)
    assert f.sse <= 4899395.5
    assert f.abc == pytest.approx(5596.85, rel=1e-4)
    assert not f.nd


def test_b7h3_tab():
    f = abc_calc.abc(abc_calc.fit_total_binding(CONC, B7H3), 3.1926448088, 1.2)
    assert f.bmax == pytest.approx(199620.3, rel=1e-4)
    assert f.kd == pytest.approx(6.38234, rel=1e-4)
    assert f.ns == pytest.approx(0, abs=1e-6)
    assert f.abc == pytest.approx(52104.2, rel=1e-4)


def test_no_binding_is_nd():
    f = abc_calc.fit_total_binding(CONC, [40 * c for c in CONC])     # a straight line: all non-specific
    assert f.nd and f.ns == pytest.approx(40, rel=1e-6)
