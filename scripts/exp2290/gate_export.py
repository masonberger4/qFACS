"""Apply a FlowJo workspace's Cells > Single Cells > Live gates to a plate's .fcs files and write one
FlowJo-style table export (.xls) per cell line (workspace group), like FlowJo's own 'Plate1 A549.xls':

    sample | Cells freq | Cells/Single Cells freq | .../Live freq | .../Live gMFI (PE) | .../Live Count
    ... one row per well ..., then Mean and SD.

Usage: python gate_export.py WSP FCS_DIR OUT_DIR PLATE_LABEL [--name "wsp group=file name" ...]
"""
from __future__ import annotations

import argparse
import statistics
import warnings
from pathlib import Path

import numpy as np

from qfacs.fcs_io import biex, flowjo_gmean
from qfacs.stats_io import well_of

PE = "B5 (575)-A"
SKIP_GROUPS = {"all samples", "compensation"}


def fj_round(v):
    """FlowJo shows gMFI as whole numbers above 1000 and 3 significant figures below."""
    if v is None:
        return ""
    return float(round(v)) if abs(v) >= 1000 else float(f"{v:.3g}")


def pct(v):
    if v is None:
        return ""
    if v >= 99.95:
        return "100 %"
    return f"{v:.2f} %" if v < 9.995 else f"{v:.1f} %"


def gate_plate(wsp_path, fcs_dir, pe=PE):
    """Returns ({group: [row dict]}, gate path list). Row: sample, freqs per gate, count, gmfi."""
    import flowkit as fk
    warnings.filterwarnings("ignore")
    wsp = fk.Workspace(str(wsp_path), fcs_samples=str(fcs_dir))
    groups = [g for g in wsp.get_sample_groups() if g.lower() not in SKIP_GROUPS]
    out, paths = {}, None
    for g in groups:
        rows = []
        for sid in sorted(wsp.get_sample_ids(group_name=g)):
            wsp.analyze_samples(sample_id=sid, use_mp=False)
            sample = wsp.get_sample(sid)
            gates = sorted(wsp.get_gate_ids(sid), key=lambda gp: len(gp[1]))  # Cells, Single Cells, Live
            n_parent = sample.event_count
            row = {"sample": Path(sid).stem, "freq": []}
            names = []
            for gname, gpath in gates:
                mem = wsp.get_gate_membership(sid, gname, gate_path=gpath)
                n = int(mem.sum())
                row["freq"].append(100.0 * n / n_parent if n_parent else None)
                n_parent = n
                names.append("/".join(list(gpath[1:]) + [gname]))
            try:
                tr = wsp.get_transform(sid, pe)
            except Exception:
                tr = None
            x = sample.get_events(source="raw")[mem, sample.pnn_labels.index(pe)]
            row["count"] = n
            row["gmfi"] = flowjo_gmean(x, tr or biex())
            rows.append(row)
            paths = names
        out[g] = sorted(rows, key=lambda r: well_of(r["sample"]) or r["sample"])
    return out, paths


def write_xls(rows, paths, path, pe=PE, with_count=True):
    """FlowJo table export layout. rows: sample, freq (list of % or text), gmfi, count (optional)."""
    import xlwt
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sheet0")
    head = [""] + [f"{p} | Freq. of Parent" for p in paths] + [f"{paths[-1]} | Geometric Mean ({pe})"]
    has_count = with_count and any(r.get("count") is not None for r in rows)   # the FlowJo original has no Count column
    if has_count:
        head.append(f"{paths[-1]} | Count")
    ws.row(0).set_cell_text(0, "")          # FlowJo writes an empty text cell in A1, not a blank
    for c, h in enumerate(head[1:], 1):
        ws.write(0, c, h)
    for i, r in enumerate(rows, 1):
        ws.write(i, 0, r["sample"])
        for c, f in enumerate(r["freq"], 1):
            ws.write(i, c, f if isinstance(f, str) else pct(f))
        ws.write(i, len(paths) + 1, fj_round(r["gmfi"]))
        if has_count:
            ws.write(i, len(paths) + 2, r.get("count"))
    n = len(rows)

    def num(f):
        if isinstance(f, str):
            f = f.replace("%", "").strip()
            return float(f) if f else None
        return f
    for k, (label, fn) in enumerate((("Mean", statistics.fmean), ("SD", lambda v: statistics.stdev(v) if len(v) > 1 else 0.0))):
        ws.write(n + 1 + k, 0, label)
        for c in range(len(paths)):
            vals = [num(r["freq"][c]) for r in rows if num(r["freq"][c]) is not None]
            ws.write(n + 1 + k, c + 1, pct(fn(vals)) if vals else "")
        g = [r["gmfi"] for r in rows if r["gmfi"] is not None]
        ws.write(n + 1 + k, len(paths) + 1, fj_round(fn(g)) if g else "")
        if has_count:
            cts = [r["count"] for r in rows if r.get("count") is not None]
            ws.write(n + 1 + k, len(paths) + 2, float(round(fn(cts))) if cts else "")
    if has_count:                           # FlowJo sets no column widths; only widen our own variant
        ws.col(0).width = 5000
        for c in range(1, len(head)):
            ws.col(c).width = 9000
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return str(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wsp")
    ap.add_argument("fcs_dir")
    ap.add_argument("out_dir")
    ap.add_argument("plate")
    ap.add_argument("--name", action="append", default=[], help='"workspace group=cell line name for the file"')
    a = ap.parse_args()
    rename = dict(x.split("=", 1) for x in a.name)
    groups, paths = gate_plate(a.wsp, a.fcs_dir)
    for g, rows in groups.items():
        f = write_xls(rows, paths, Path(a.out_dir) / f"{a.plate} {rename.get(g, g)}.xls")
        gm = [r["gmfi"] for r in rows]
        print(f"{f}: {len(rows)} wells, gates {paths[-1]}, live events {min(r['count'] for r in rows)}-{max(r['count'] for r in rows)}, "
              f"gMFI {min(gm):.0f}-{max(gm):.0f}")


if __name__ == "__main__":
    main()
