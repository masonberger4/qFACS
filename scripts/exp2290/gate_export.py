"""Helpers that write a FlowJo-style table export (.xls) in the layout of FlowJo's own 'Plate1 A549.xls':

    sample | Cells freq | Cells/Single Cells freq | .../Live freq | .../Live gMFI (PE) | .../Live Count
    ... one row per well ..., then Mean and SD.

Used by wsp_export.py, replicas.py and set1_exports.py. The part that re-applied a workspace's gates to .fcs files
was removed: gating is done by hand in FlowJo.
"""
from __future__ import annotations

import statistics
from pathlib import Path

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

def write_xls(rows, paths, path, pe=PE, with_count=True, count_first=False):
    """FlowJo table export layout. rows: sample, freq (list of % or text), gmfi, count (optional).
    count_first puts the Live Count column before the gMFI, the order of the table in Mase's Set 2 / Set 3 workspaces."""
    import xlwt
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sheet0")
    head = [""] + [f"{p} | Freq. of Parent" for p in paths] + [f"{paths[-1]} | Geometric Mean ({pe})"]
    has_count = with_count and any(r.get("count") is not None for r in rows)   # the FlowJo original has no Count column
    g_col, c_col = len(paths) + 1, len(paths) + 2
    if has_count:
        head.append(f"{paths[-1]} | Count")
        if count_first:
            head[-2:] = head[-1], head[-2]
            g_col, c_col = c_col, g_col
    ws.row(0).set_cell_text(0, "")          # FlowJo writes an empty text cell in A1, not a blank
    for c, h in enumerate(head[1:], 1):
        ws.write(0, c, h)
    for i, r in enumerate(rows, 1):
        ws.write(i, 0, r["sample"])
        for c, f in enumerate(r["freq"], 1):
            ws.write(i, c, f if isinstance(f, str) else pct(f))
        ws.write(i, g_col, fj_round(r["gmfi"]))
        if has_count:
            ws.write(i, c_col, r.get("count"))
    n = len(rows)

    def num(f):                 # FlowJo takes Mean and SD over the values as the table shows them (rounded)
        f = (f if isinstance(f, str) else pct(f)).replace("%", "").strip()
        return float(f) if f else None
    for k, (label, fn) in enumerate((("Mean", statistics.fmean), ("SD", lambda v: statistics.stdev(v) if len(v) > 1 else 0.0))):
        ws.write(n + 1 + k, 0, label)
        for c in range(len(paths)):
            vals = [num(r["freq"][c]) for r in rows if num(r["freq"][c]) is not None]
            ws.write(n + 1 + k, c + 1, pct(fn(vals)) if vals else "")
        g = [fj_round(r["gmfi"]) for r in rows if r["gmfi"] is not None]
        ws.write(n + 1 + k, g_col, fj_round(fn(g)) if g else "")
        if has_count:
            cts = [r["count"] for r in rows if r.get("count") is not None]
            ws.write(n + 1 + k, c_col, float(round(fn(cts))) if cts else "")
    if has_count and not count_first:       # FlowJo sets no column widths; only widen our own variant
        ws.col(0).width = 5000
        for c in range(1, len(head)):
            ws.col(c).width = 9000
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return str(path)
