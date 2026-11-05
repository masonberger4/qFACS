"""Numerical pieces: Quantibrite bead curve and the one-site binding fit."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats
from scipy.optimize import minimize_scalar

BEAD_KEYS = ("pe_low", "pe_med_low", "pe_med_high", "pe_high")
BEAD_LABELS = {"pe_low": "Low", "pe_med_low": "Med-Low", "pe_med_high": "Med-High", "pe_high": "High"}


@dataclass
class BeadCurve:
    bead_run: str
    pe: dict            # level -> PE molecules per bead (lot value)
    gmfi: dict          # level -> measured gMFI
    slope: float
    intercept: float
    r2: float
    recovery: dict      # level -> back-calculated / lot value
    qc: str
    source: str = ""

    @property
    def gmfi_min(self):
        return min(self.gmfi.values())

    @property
    def gmfi_max(self):
        return max(self.gmfi.values())

    def pe_per_cell(self, gmfi):
        if gmfi is None or gmfi <= 0:
            return None
        return 10 ** ((math.log10(gmfi) - self.intercept) / self.slope)


def fit_beads(bead_run, pe: dict, gmfi: dict, r2_min=0.98, source="") -> BeadCurve:
    """log10(gMFI) = slope * log10(PE/bead) + intercept over the four peaks."""
    x = np.log10([pe[k] for k in BEAD_KEYS])
    y = np.log10([gmfi[k] for k in BEAD_KEYS])
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
    rec = {k: 10 ** ((math.log10(gmfi[k]) - intercept) / slope) / pe[k] for k in BEAD_KEYS}
    bad = [BEAD_LABELS[k] for k, v in rec.items() if not 0.8 <= v <= 1.2]
    if r2 < r2_min:
        qc = f"CHECK: R² {r2:.4f} below {r2_min}"
    elif bad:
        qc = f"CHECK: recovery outside 80-120% for {', '.join(bad)}"
    else:
        qc = "PASS"
    return BeadCurve(bead_run, dict(pe), dict(gmfi), float(slope), float(intercept), float(r2), rec, qc, source)


@dataclass
class FitResult:
    n: int
    bmax: float | None = None
    kd: float | None = None
    bmax_se: float | None = None
    kd_se: float | None = None
    bmax_ci: tuple | None = None
    kd_ci: tuple | None = None
    r2: float | None = None
    at_bound: bool = False
    nd: bool = False
    flags: list = field(default_factory=list)


def _bmax_for(kd, x, y):
    f = x / (kd + x)
    return max(0.0, float(np.sum(y * f) / np.sum(f * f)))


def _sse(logkd, x, y):
    kd = 10 ** logkd
    b = _bmax_for(kd, x, y)
    return float(np.sum((y - b * x / (kd + x)) ** 2))


def one_site_fit(conc, y) -> FitResult:
    """Least-squares fit of y = Bmax*C/(Kd + C).

    For any Kd the best Bmax is exact (linear), so the search is one-dimensional in log Kd:
    a log grid from xmax*1e-4 to xmax*1e2 finds the basin, then a bounded scalar minimisation refines it.
    SEs come from (J'J)^-1 * s², s² = SSE/(n-2); 95% CI = estimate ± t(0.975, n-2) * SE.
    """
    x = np.asarray(conc, float)
    y = np.asarray(y, float)
    n = len(x)
    res = FitResult(n)
    if n < 4:
        res.flags.append("too few points to fit")
        res.nd = True
        return res
    lo, hi = math.log10(x.max()) - 4, math.log10(x.max()) + 2
    grid = np.linspace(lo, hi, 241)
    sse = np.array([_sse(g, x, y) for g in grid])
    i = int(np.argmin(sse))
    a, b = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
    opt = minimize_scalar(_sse, bounds=(a, b), args=(x, y), method="bounded", options={"xatol": 1e-9})
    logkd = opt.x if opt.fun <= sse[i] else grid[i]
    kd = 10 ** logkd
    bmax = _bmax_for(kd, x, y)
    res.at_bound = i in (0, len(grid) - 1)
    pred = bmax * x / (kd + x)
    sse_v = float(np.sum((y - pred) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    res.r2 = 1 - sse_v / sst if sst > 0 else None
    res.bmax, res.kd = bmax, kd
    f = x / (kd + x)
    j = np.column_stack([f, -bmax * x / (kd + x) ** 2])
    s2 = sse_v / (n - 2)
    tval = stats.t.ppf(0.975, n - 2)
    try:
        cov = np.linalg.inv(j.T @ j) * s2
        res.bmax_se, res.kd_se = float(math.sqrt(cov[0, 0])), float(math.sqrt(cov[1, 1]))
        res.bmax_ci = (bmax - tval * res.bmax_se, bmax + tval * res.bmax_se)
        res.kd_ci = (max(kd - tval * res.kd_se, 0.0), kd + tval * res.kd_se)
    except np.linalg.LinAlgError:
        res.flags.append("fit covariance could not be computed")
    if bmax <= 0 or y.max() <= 0 or (res.r2 is not None and res.r2 < 0) or (res.bmax_ci and res.bmax_ci[0] <= 0):
        res.nd = True
    return res
