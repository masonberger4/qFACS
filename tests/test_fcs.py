""".fcs + .wsp gating. The data (208 MB) is not in the repo: set QFACS_FCS_DATA to a folder holding
02-Nov-2026.wsp, Plate_001/*.fcs and Tube_001.fcs (Exp2290 Set 2) to run the comparison tests."""
import os
from pathlib import Path

import numpy as np
import pytest

fk = pytest.importorskip("flowkit")
from qfacs.fcs_io import biex, flowjo_gmean, gate_workspace, norm_plate  # noqa: E402
from qfacs.stats_io import read_table, well_of, well_stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples" / "Exp2290_Set2_Plate1"
DATA = Path(os.environ.get("QFACS_FCS_DATA", "/nonexistent"))
need_data = pytest.mark.skipif(not (DATA / "02-Nov-2026.wsp").exists(), reason="set QFACS_FCS_DATA")


def test_flowjo_gmean_on_constant_values_is_the_value():
    assert flowjo_gmean(np.full(10, 5000.0), biex()) == pytest.approx(5000, rel=1e-3)
    assert flowjo_gmean(np.array([10.0, 1000.0])) == pytest.approx(100.0)
    assert flowjo_gmean([]) is None


def test_norm_plate():
    assert norm_plate("Plate_001") == norm_plate("Plate1") == "plate1"
    assert norm_plate("Plate 12") == "plate12"


@need_data
def test_workspace_gating_matches_flowjo_export():
    tables, notes = gate_workspace(DATA / "02-Nov-2026.wsp", DATA / "Plate_001", "B5 (575)-A", "Live")
    (t,) = tables.values()
    ours = {well_of(n): v for n, v in t.rows.items()}
    ratios, counts = [], []
    for f in ("Plate1_U87.xls", "Plate1_A431.xls"):
        stats, _ = well_stats(read_table(EX / f), "B5 (575)-A", "Live")
        for s in stats:
            o = ours[s.well]
            ratios.append(o[t.headers[1]] / s.gmfi)
            counts.append(o[t.headers[0]] / s.count)
    assert len(ratios) == 96
    assert abs(np.median(ratios) - 1) < 0.005 and max(abs(np.array(ratios) - 1)) < 0.02
    assert abs(np.median(counts) - 1) < 0.005 and max(abs(np.array(counts) - 1)) < 0.02


def test_is_bead_workspace(tmp_path):
    from qfacs.fcs_io import is_bead_workspace
    beads = tmp_path / "beads.wsp"
    beads.write_text('<Workspace><Population name="Beads"/>' + "".join(
        f'<Population name="{g}" count="1"/>' for g in ("Low", "Med Low", "Med High", "High")) + "</Workspace>")
    cells = tmp_path / "cells.wsp"
    cells.write_text('<Workspace><Population name="Cells"/><Population name="Single Cells"/>'
                     '<Population name="Live"/></Workspace>')
    assert is_bead_workspace(beads)
    assert not is_bead_workspace(cells)
