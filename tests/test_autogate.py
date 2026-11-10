"""Automatic gating on synthetic events: debris, doublets and dead cells are removed, live singlets kept."""
import numpy as np

from qfacs import autogate
from qfacs.autogate import apply, learn


def _well(rng, n=6000):
    k = {"cell": int(n * .7), "debris": int(n * .1), "doublet": int(n * .08), "dead": n - int(n * .7) - int(n * .1) - int(n * .08)}
    rows, truth = [], []
    for kind, m in k.items():
        fsc = rng.normal(6e6, 1.2e6, m)
        ssc = rng.normal(3.6e6, 0.7e6, m)
        w = rng.normal(340, 12, m)
        via = 10 ** rng.normal(4.3, 0.12, m)
        if kind == "debris":
            fsc, ssc = rng.uniform(-5e5, 8e5, m), rng.uniform(1e5, 1.5e6, m)
        elif kind == "doublet":
            w = rng.normal(470, 20, m)
        elif kind == "dead":
            via = 10 ** rng.normal(5.2, 0.2, m)
        rows.append(np.c_[fsc, ssc, w, via])
        truth += [kind == "cell"] * m
    return np.vstack(rows), np.array(truth)


def test_learned_gates_keep_live_singlets():
    rng = np.random.default_rng(1)
    wells = [_well(rng) for _ in range(6)]
    g = learn([w for w, _ in wells], dict(autogate.SUGGESTED_CHANNELS))
    arr, truth = wells[0]
    m = apply(g, arr)
    assert (m & truth).sum() / truth.sum() > 0.9       # most live singlets kept
    assert (m & ~truth).sum() / max(m.sum(), 1) < 0.03  # few debris / doublets / dead let through
    assert 2e4 < g.live_cut < 1e5


def test_no_viability_dye_skips_live_gate():
    rng = np.random.default_rng(2)
    wells = [_well(rng) for _ in range(3)]
    g = learn([w for w, _ in wells], dict(autogate.SUGGESTED_CHANNELS), use_live=False)
    assert g.live_cut is None and "Live" not in g.describe()


def test_mostly_dead_well_gates_the_dim_live_peak():
    """When ~85% of singlets are dead, the bright dead peak is the tallest; Live must still take the dim peak."""
    rng = np.random.default_rng(3)
    wells = []
    for _ in range(4):
        arr, truth = _well(rng)
        live = np.flatnonzero(truth)
        dead = rng.choice(live, int(0.85 * len(live)), replace=False)
        arr[dead, 3] = 10 ** rng.normal(5.15, 0.17, len(dead))
        truth = truth.copy()
        truth[dead] = False
        wells.append((arr, truth))
    g = learn([w for w, _ in wells], dict(autogate.SUGGESTED_CHANNELS))
    arr, truth = wells[0]
    m = apply(g, arr)
    assert "mostly dead" in g.describe()
    assert (m & truth).sum() / truth.sum() > 0.85
    assert (m & ~truth).sum() / max(m.sum(), 1) < 0.1
