"""Automatic Cells > Single Cells > Live gating for plates with no FlowJo workspace.

Like a hand-gated FlowJo group, one set of gates is learned per plate and cell line (from all of that line's wells
pooled) and the same gates are applied to every well:

- Cells: the main FSC-A / SSC-A population. The convex hull of the 2D density above 2% of its peak, enlarged 10%
  about its centre, minus debris below 20% of the FSC-A mode.
- Single Cells: SSC-W within median +/- 4 MAD of the cells, in 20 SSC-A slices (doublets are wider).
- Live: viability dye low. Cut = mode + 2.5 x the dim-side width of the main (live) peak, on log10 of the dye.

Checked against Mase's hand gates on CHO-EGFR (05-Nov-2026.wsp, 48 wells): PE gMFI median 0.8% off, 90% of
wells within 2.4%, max 4.5%.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Suggested channels (BD FACSDiscover A8 raw detectors); overridable on the Experiment sheet.
SUGGESTED_CHANNELS = dict(gate_fsc="FSC-A", gate_ssc="SSC (Violet)-A", gate_width="SSC (Violet)-W",
                          gate_viability="V6 (515)-A")
CELLS_DENSITY_FRAC = 0.02
CELLS_EXPAND = 1.1
DEBRIS_FRAC = 0.2
SINGLET_K = 4.0
SINGLET_SLICES = 20
LIVE_N_SIGMA = 2.5
POOL_PER_WELL = 3000


@dataclass
class Gates:
    channels: dict
    hull_pts: np.ndarray = None          # hull vertices (scaled)
    scale: np.ndarray = None
    centre: np.ndarray = None
    fsc_min: float = 0.0
    slice_edges: np.ndarray = None
    w_lo: np.ndarray = None
    w_hi: np.ndarray = None
    live_cut: float | None = None
    n_pooled: int = 0
    notes: list = field(default_factory=list)

    def describe(self):
        c = self.channels
        s = (f"Cells on {c['gate_fsc']} / {c['gate_ssc']} (FSC-A > {self.fsc_min:,.0f}); "
             f"Single Cells on {c['gate_ssc']} vs {c['gate_width']} (+/- {SINGLET_K:g} MAD)")
        if self.live_cut is not None:
            s += f"; Live {c['gate_viability']} < {self.live_cut:,.0f}"
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


def learn(arrays, channels, use_live=True) -> Gates:
    """arrays: list of (n, 4) arrays with columns fsc, ssc, width, viability (viability may be NaN)."""
    from scipy import ndimage
    from scipy.spatial import ConvexHull
    rng = np.random.default_rng(0)
    pool = np.vstack([a[rng.choice(len(a), min(len(a), POOL_PER_WELL), replace=False)] for a in arrays if len(a)])
    g = Gates(channels=channels, n_pooled=len(pool))
    # Cells
    core = pool[_density_core(pool[:, 0], pool[:, 1], CELLS_DENSITY_FRAC)][:, :2]
    g.scale = core.std(0)
    pts = core / g.scale
    g.hull_pts = pts[ConvexHull(pts).vertices]
    g.centre = pts.mean(0)
    f = pool[:, 0]
    h, e = np.histogram(f, bins=200, range=tuple(np.percentile(f, [0.5, 99.5])))
    hs = ndimage.gaussian_filter1d(h.astype(float), 2)
    pk = int(np.argmax(hs))
    valley = e[int(np.argmin(hs[:pk + 1]))] if pk > 0 else e[0]
    g.fsc_min = float(max(valley, DEBRIS_FRAC * (e[pk] + e[pk + 1]) / 2))
    cells = _cells(g, pool)
    # Single Cells
    a, w = pool[cells, 1], pool[cells, 2]
    g.slice_edges = np.quantile(a, np.linspace(0, 1, SINGLET_SLICES + 1))
    lo, hi = [], []
    for i in range(SINGLET_SLICES):
        m = (a >= g.slice_edges[i]) & (a <= g.slice_edges[i + 1])
        med = np.median(w[m])
        mad = 1.4826 * np.median(np.abs(w[m] - med))
        lo.append(med - SINGLET_K * mad)
        hi.append(med + SINGLET_K * mad)
    g.w_lo, g.w_hi = np.array(lo), np.array(hi)
    # Live
    if use_live:
        sing = cells.copy()
        sing[cells] = _singlets(g, a, w)
        x = np.log10(np.clip(pool[sing, 3], 100, None))
        h, e = np.histogram(x, bins=150, range=tuple(np.percentile(x, [0.5, 99.9])))
        hs = ndimage.gaussian_filter1d(h.astype(float), 2)
        pk = int(np.argmax(hs))
        mode = (e[pk] + e[pk + 1]) / 2
        left = x[x < mode]
        sig = (mode - np.median(left)) / 0.674 if left.size else 0.1
        g.live_cut = float(10 ** (mode + LIVE_N_SIGMA * sig))
    return g


def _cells(g: Gates, arr):
    from scipy.spatial import Delaunay
    q = arr[:, :2] / g.scale
    tri = Delaunay(g.hull_pts)
    return (tri.find_simplex(g.centre + (q - g.centre) / CELLS_EXPAND) >= 0) & (arr[:, 0] > g.fsc_min)


def _singlets(g: Gates, a, w):
    i = np.clip(np.searchsorted(g.slice_edges, a) - 1, 0, SINGLET_SLICES - 1)
    return (w >= g.w_lo[i]) & (w <= g.w_hi[i])


def apply(g: Gates, arr):
    """Boolean mask of live single cells for one well's (n, 4) array."""
    m = _cells(g, arr)
    m[m] = _singlets(g, arr[m, 1], arr[m, 2])
    if g.live_cut is not None:
        m &= arr[:, 3] < g.live_cut
    return m
