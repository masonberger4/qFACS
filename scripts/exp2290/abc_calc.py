"""The method of Mase's QuantiBRITE_ABC_calculator.xlsx, in Python.

Beads tab:   slope m = SLOPE(bead gMFI, PE molecules/bead)   (linear, not log-log; the intercept is not used)
Antigen tab: Y = gMFI - unstained gMFI, fitted with the one-site total-binding model
                 Y(C) = Bmax*C/(Kd + C) + NS*C      Bmax, Kd, NS >= 0   (Excel Solver, minimum SSE)
             over the titration points plus the (0, 0) point;  R2 = 1 - SSE/DEVSQ(Y)
             PE molecules/cell = Bmax/m ;  ABC = Bmax/m/(F/P)
No isotype control is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize_scalar, nnls

KD_MAX = 1e4          # ug/mL: beyond this the saturable term is a straight line (same as NS*C)


def bead_line(pe_per_bead, gmfi):
    """Excel SLOPE / INTERCEPT / RSQ of gMFI (y) on PE molecules per bead (x)."""
    x, y = np.asarray(pe_per_bead, float), np.asarray(gmfi, float)
    m, c = np.polyfit(x, y, 1)
    r2 = float(np.corrcoef(x, y)[0, 1] ** 2)
    return float(m), float(c), r2


@dataclass
class CalcFit:
    bmax: float
    kd: float
    ns: float
    sse: float
    r2: float | None
    pe_per_cell: float | None = None
    abc: float | None = None
    flags: list = field(default_factory=list)
    nd: bool = False      # no saturable binding to report (see fit_total_binding)

    def predict(self, c):
        c = np.asarray(c, float)
        return self.bmax * c / (self.kd + c) + self.ns * c


def _linear(kd, c, y):
    """Best Bmax, NS >= 0 for a fixed Kd (the model is linear in both)."""
    a = np.column_stack([c / (kd + c), c])
    scale = a.max(axis=0)
    scale[scale == 0] = 1.0
    coef, _ = nnls(a / scale, y)
    coef = coef / scale
    return coef, float(((a @ coef - y) ** 2).sum())


def fit_total_binding(conc, y):
    """Global minimum-SSE fit of Y = Bmax*C/(Kd+C) + NS*C with Bmax, Kd, NS >= 0. conc/y include the (0, 0) point."""
    c, y = np.asarray(conc, float), np.asarray(y, float)
    pos = c[c > 0]
    grid = np.logspace(np.log10(pos.min()) - 3, np.log10(KD_MAX), 400)
    sse = np.array([_linear(k, c, y)[1] for k in grid])
    i = int(sse.argmin())
    lo, hi = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    opt = minimize_scalar(lambda lk: _linear(10 ** lk, c, y)[1], bounds=(np.log10(lo), np.log10(hi)), method="bounded",
                          options=dict(xatol=1e-10))
    kd = 10 ** opt.x if opt.fun <= sse[i] else grid[i]
    (bmax, ns), best = _linear(kd, c, y)
    dev = float(((y - y.mean()) ** 2).sum())
    f = CalcFit(float(bmax), float(kd), float(ns), best, 1 - best / dev if dev > 0 else None)
    top = pos.max()
    if bmax <= 0:
        f.flags.append("ND: no saturable binding, all signal is non-specific (Bmax = 0)")
        f.nd = True
    else:
        if kd >= 0.99 * KD_MAX:
            f.flags.append("Kd at the search limit: signal is a straight line, Bmax not determined")
        elif kd > top:
            f.flags.append(f"Kd {kd:.3g} above the top conc {top:g}: curve not saturated, Bmax extrapolated")
        elif kd < pos.min():
            f.flags.append(f"Kd {kd:.3g} below the lowest conc {pos.min():.3g}: no points on the rising part")
        if ns * top > 0.5 * f.predict(top):
            f.flags.append("non-specific term is more than half of the top-dose signal")
            if kd < pos.min():
                # a flat step between the unstained well and every stained well plus a straight line: not a binding curve
                f.flags.insert(0, f"ND: no saturable binding (Bmax {bmax:,.0f} gMFI is a flat offset, not a curve)")
                f.nd = True
    if f.r2 is not None and f.r2 < 0.9:
        f.flags.append(f"poor fit (R2 {f.r2:.2f})")
    return f


def abc(fit: CalcFit, slope, fp):
    fit.pe_per_cell = fit.bmax / slope
    fit.abc = fit.pe_per_cell / fp
    return fit


if __name__ == "__main__":   # check against the solved tabs of the calculator workbook
    import sys
    from openpyxl import load_workbook
    wb = load_workbook(sys.argv[1], data_only=True)
    b = wb["Beads"]
    m, c0, r2 = bead_line([b.cell(r, 2).value for r in range(4, 8)], [b.cell(r, 3).value for r in range(4, 8)])
    print(f"bead slope {m:.6f} (workbook {b['B9'].value:.6f}), R2 {r2:.6f}")
    for tab in ("CD58", "B7H3", "DLL3", "EGFR"):
        ws = wb[tab]
        c = [ws.cell(r, 1).value for r in range(19, 31)]
        y = [ws.cell(r, 2).value for r in range(19, 31)]
        f = abc(fit_total_binding(c, y), m, ws["B9"].value)
        print(f"{tab}: Bmax {f.bmax:,.1f} Kd {f.kd:.4f} NS {f.ns:.4f} SSE {f.sse:,.0f} R2 {f.r2:.4f} ABC {f.abc:,.0f} | workbook "
              f"Bmax {ws['B4'].value:,.1f} Kd {ws['B5'].value:.4f} NS {ws['B6'].value:.4f} SSE {ws['B11'].value:,.0f} ABC {ws['B15'].value:,.0f} | {f.flags}")
