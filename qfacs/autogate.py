"""Automatic Cells > Single Cells > Live gating for plates with no FlowJo workspace.

Like a hand-gated FlowJo group, one set of gates is learned per plate and cell line (from all of that line's wells
pooled) and the same gates are applied to every well:

- Cells: the main FSC-A / SSC-A population. The convex hull of the 2D density above 2% of its peak, enlarged 10%
  about its centre, above a debris cut at the valley below the main log FSC-A peak (never below 35% of the FSC-A mode).
- Single Cells: SSC-W below its main peak + 3 x the peak's narrow-side width, and at least 1.3 x the peak
  (doublets and clumps are wider).
- Live: viability dye low. Cut = mode + 2.5 x the dim-side width of the main (live) peak, on log10 of the dye,
  tilted with SSC like a hand-drawn V6 vs SSC gate (slope of the live peak's log V6 on log SSC, 0-1).

Checked against Mase's hand gates (same PE display transform), PE gMFI per well vs FlowJo gating:
  CHO-EGFR (05-Nov-2026.wsp, rows A-B):  median 0.6%, 90% of wells within 1.3%, max 1.9%
  U-87 MG (02-Nov-2026.wsp, rows A-D):   median 3.3%, 90% within 4.5%, max 5.1%
  A431 (02-Nov-2026.wsp, rows E-H):      median 1.5%, 90% within 4.2%, max 5.5%
Antigens/cell vs the same plates gated by hand: within 4.2% (CHO-EGFR EGFR, U-87 MG and A431 CD58 / B7H3).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Suggested channels (BD FACSDiscover A8 raw detectors); overridable on the Experiment sheet.
SUGGESTED_CHANNELS = dict(gate_fsc="FSC-A", gate_ssc="SSC (Violet)-A", gate_width="SSC (Violet)-W",
                          gate_viability="V6 (515)-A")
CELLS_DENSITY_FRAC = 0.02
CELLS_EXPAND = 1.1
DEBRIS_LOG = 0.45         # debris floor: 0.45 log below the FSC-A mode (35% of it)
SINGLET_N_SIGMA = 3.0
SINGLET_MIN_RATIO = 1.3     # never cut singlet width below 1.3 x its peak
LIVE_N_SIGMA = 2.5
LIVE_TILT = True
POOL_PER_WELL = 3000


@dataclass
class Gates:
    channels: dict
    hull_pts: np.ndarray = None          # hull vertices (scaled)
    scale: np.ndarray = None
    centre: np.ndarray = None
    fsc_min: float = 0.0
    w_max: float = None
    live_cut: float | None = None
    live_slope: float = 0.0       # Live cut tilts with SSC: V6 < live_cut * (SSC / ssc_ref) ** live_slope
    ssc_ref: float = 1.0
    n_pooled: int = 0
    notes: list = field(default_factory=list)

    def describe(self):
        c = self.channels
        s = (f"Cells on {c['gate_fsc']} / {c['gate_ssc']} (FSC-A > {self.fsc_min:,.0f}); "
             f"Single Cells {c['gate_width']} < {self.w_max:,.0f}")
        if self.live_cut is not None:
            s += f"; Live {c['gate_viability']} < {self.live_cut:,.0f}"
            if self.live_slope:
                s += f" x (SSC / {self.ssc_ref:,.0f})^{self.live_slope:.2f}"
        return s + f"; learned from {self.n_pooled:,} pooled events"


def _density_core(x, y, frac, bins=160):
    from scipy import ndimage
    rx = np.percentile(x, [0.5, 99.5])
    ry = np.percentile(y, [0.5, 99.5])
    H, _, _ = np.histogram2d(x, y, bins=bins, range=[rx, ry])
    H = ndimage.gaussian_filter(H, 2)
    lab, _ = ndimage.label(H > frac * H.max())
    pk = np.unravel_index(np.argmax(H), H.shape)
    m = ndimage.binary_fill_holes(lab == lab[pk])
    ix = np.clip(((x - rx[0]) / (rx[1] - rx[0]) * bins).astype(int), 0, bins - 1)
    iy = np.clip(((y - ry[0]) / (ry[1] - ry[0]) * bins).astype(int), 0, bins - 1)
    return m[ix, iy] & (x >= rx[0]) & (x <= rx[1]) & (y >= ry[0]) & (y <= ry[1])


def _debris_cut(fsc):
    """FSC-A below which events are debris: the deepest point of the smoothed log10 FSC-A histogram between
    (main peak - 1.5) and the main peak, if a debris peak lies left of it, and never below main peak - DEBRIS_LOG."""
    from scipy import ndimage
    x = np.log10(np.clip(fsc, 1e3, None))
    lo, hi = np.percentile(x, [0.5, 99.5])
    h, e = np.histogram(x, bins=120, range=(lo, hi))
    hs = ndimage.gaussian_filter1d(h.astype(float), 2)
    c = (e[:-1] + e[1:]) / 2
    pk = int(np.argmax(hs))
    win = np.flatnonzero((c >= c[pk] - 1.5) & (c <= c[pk]))
    j = win[int(np.argmin(hs[win]))]
    # a real valley: well below the main peak, with a debris peak to its left
    floor = 10 ** (c[pk] - DEBRIS_LOG)
    if 0 < j < pk and hs[j] < 0.5 * hs[pk] and hs[:j].max() > 1.5 * hs[j]:
        return float(max(10 ** c[j], floor))
    return float(floor)


def _peak_cut(v, n_sigma, log, min_ratio=None):
    """Upper cut = main peak + n_sigma x the peak's dim-side width (robust half-Gaussian), on log10 or linear."""
    from scipy import ndimage
    x = np.log10(np.clip(v, 100, None)) if log else np.asarray(v, float)
    h, e = np.histogram(x, bins=150, range=tuple(np.percentile(x, [0.5, 99.9])))
    hs = ndimage.gaussian_filter1d(h.astype(float), 2)
    pk = int(np.argmax(hs))
    mode = (e[pk] + e[pk + 1]) / 2
    left = x[x < mode]
    sig = (mode - np.median(left)) / 0.674 if left.size else (e[-1] - e[0]) / 20
    cut = mode + n_sigma * sig
    if min_ratio and not log:
        cut = max(cut, min_ratio * mode)
    return float(10 ** cut if log else cut)


def learn(arrays, channels, use_live=True) -> Gates:
    """arrays: list of (n, 4) arrays with columns fsc, ssc, width, viability (viability may be NaN)."""
    from scipy import ndimage
    from scipy.spatial import ConvexHull
    rng = np.random.default_rng(0)
    pool = np.vstack([a[rng.choice(len(a), min(len(a), POOL_PER_WELL), replace=False)] for a in arrays if len(a)])
    g = Gates(channels=channels, n_pooled=len(pool))
    # Cells: debris cut at the valley below the main log FSC-A peak, then the main FSC-A / SSC-A blob above it
    g.fsc_min = _debris_cut(pool[:, 0])
    keep = pool[:, 0] > g.fsc_min
    core = pool[keep][_density_core(pool[keep, 0], pool[keep, 1], CELLS_DENSITY_FRAC)][:, :2]
    g.scale = core.std(0)
    pts = core / g.scale
    g.hull_pts = pts[ConvexHull(pts).vertices]
    g.centre = pts.mean(0)
    cells = _cells(g, pool)
    # Single Cells: doublets and clumps are wider; keep width below its main peak + SINGLET_N_SIGMA x the
    # peak's narrow-side width (singlet width hardly changes with size, so one cut fits all sizes)
    w = pool[cells, 2]
    g.w_max = _peak_cut(w, SINGLET_N_SIGMA, log=False, min_ratio=SINGLET_MIN_RATIO)
    # Live
    if use_live:
        sing = cells & (pool[:, 2] <= g.w_max)
        v6 = np.log10(np.clip(pool[sing, 3], 100, None))
        sc = np.log10(np.clip(pool[sing, 1], 1e3, None))
        g.ssc_ref = float(10 ** np.median(sc))
        if LIVE_TILT:
            # slope of the live peak's V6 vs SSC (bigger, more granular cells carry more dye-channel signal)
            lo, hi = np.percentile(v6, [10, 70])
            core = (v6 > lo) & (v6 < hi)
            b = np.polyfit(sc[core], v6[core], 1)[0]
            g.live_slope = float(np.clip(b, 0.0, 1.0))
        resid = 10 ** (v6 - g.live_slope * (sc - np.log10(g.ssc_ref)))
        g.live_cut = _peak_cut(resid, LIVE_N_SIGMA, log=True)
    return g


def _cells(g: Gates, arr):
    from scipy.spatial import Delaunay
    q = arr[:, :2] / g.scale
    tri = Delaunay(g.hull_pts)
    return (tri.find_simplex(g.centre + (q - g.centre) / CELLS_EXPAND) >= 0) & (arr[:, 0] > g.fsc_min)


def _singlets(g: Gates, a, w):
    return w <= g.w_max


def apply(g: Gates, arr):
    """Boolean mask of live single cells for one well's (n, 4) array."""
    m = _cells(g, arr)
    m[m] = _singlets(g, arr[m, 1], arr[m, 2])
    if g.live_cut is not None:
        ssc = np.clip(arr[:, 1], 1e3, None)
        m &= arr[:, 3] < g.live_cut * (ssc / g.ssc_ref) ** g.live_slope
    return m
