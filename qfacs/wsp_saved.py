"""Read the numbers FlowJo saved in a workspace (.wsp): no .fcs files and no re-gating.

For every sample FlowJo stores the event count of each gate and the value of each statistic added to a
population. With Count and Geometric Mean (<PE parameter>) added to the Live population (and Geometric Mean on
each bead gate), those saved values are exactly what FlowJo's Table Editor would export, as of the last save.
"""
from __future__ import annotations

import math
from pathlib import Path
from xml.etree import ElementTree

from .stats_io import StatsTable

BEAD_GATES = ("Low", "Med Low", "Med High", "High")


def _gmean(node, pe):
    for st in node.findall("Subpopulations/Statistic"):
        if st.get("name") == "Geometric Mean" and (st.get("id") or "").lower() == pe.lower():
            try:
                v = float(st.get("value"))
            except (TypeError, ValueError):
                return None
            return None if math.isnan(v) else v
    return None


def _walk(node, path=()):
    """Yields (gate path tuple, Population element) for every gate under node."""
    for p in node.findall("Subpopulations/Population"):
        here = path + (p.get("name"),)
        yield here, p
        yield from _walk(p, here)


def saved_tables(wsp_path, pe_param, live_gate=None):
    """Returns (cells {plate keyword: StatsTable}, beads {sample: StatsTable}, missing [sample], notes).

    cells: one row per gated sample, '<gate path> | Count' and '<gate path> | Geometric Mean (<pe>)' for the live
    gate (by name, else the deepest gate of a single Cells > Single Cells > Live chain).
    beads: samples whose gates include Low, Med Low, Med High and High, in FlowJo bead export layout.
    missing: gated samples with no saved PE Geometric Mean on the live gate (or a bead gate), or no saved counts.
    """
    root = ElementTree.parse(str(wsp_path)).getroot()
    cells, beads, missing, notes = {}, {}, [], []
    for smp in root.iterfind(".//SampleList/Sample"):
        sn = smp.find("SampleNode")
        if sn is None:
            continue
        kw = {k.get("name", "").lower(): k.get("value") for k in smp.iter("Keyword")}
        name = Path(sn.get("name") or kw.get("$fil") or "").stem
        gates = list(_walk(sn))
        if not gates:
            continue  # ungated sample
        by_leaf = {}
        for path, p in gates:
            by_leaf.setdefault(path[-1].strip().lower(), (path, p))
        if all(g.lower() in by_leaf for g in BEAD_GATES):
            headers, row, ok = [], {}, True
            for g in BEAD_GATES:
                path, p = by_leaf[g.lower()]
                gm = _gmean(p, pe_param)
                ok = ok and gm is not None
                headers += [f"{'/'.join(path)} | Count", f"{'/'.join(path)} | Geometric Mean ({pe_param})"]
                row[headers[-2]], row[headers[-1]] = int(p.get("count") or -1), gm
            if not ok:
                missing.append(name)
                continue
            t = StatsTable(str(wsp_path), headers)
            t.rows[name] = row
            beads[name] = t
            continue
        if live_gate and str(live_gate).strip().lower() in by_leaf:
            path, p = by_leaf[str(live_gate).strip().lower()]
        else:
            path, p = max(gates, key=lambda g: len(g[0]))
        count, gm = int(p.get("count") or -1), _gmean(p, pe_param)
        if count < 0 or gm is None:
            missing.append(name)
            continue
        well = kw.get("$wellid")
        if well and not name.upper().startswith(well.upper()):
            name = f"{well}-{name}"
        gp = "/".join(path)
        t = cells.setdefault(kw.get("$plateid") or "", StatsTable(str(wsp_path), [f"{gp} | Count",
                                                                                  f"{gp} | Geometric Mean ({pe_param})"]))
        if t.headers[0] != f"{gp} | Count":
            notes.append(f"{Path(wsp_path).name}: {name} is gated as {gp}, not {t.headers[0].split(' |')[0]}; skipped")
            continue
        t.rows[name] = {t.headers[0]: count, t.headers[1]: gm}
    return cells, beads, missing, notes
