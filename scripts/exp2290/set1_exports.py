"""Set 1 has no .fcs files: rebuild the per cell line FlowJo exports from the table Mase pasted into
Exp2290_Analysis.xlsx ('Raw data' = sample, gate frequencies and Live gMFI; 'Calc Sheet' = plate numbers).

Usage: python set1_exports.py Exp2290_Analysis.xlsx Exp2290_qFACS_Setup.xlsx OUT_DIR
"""
import sys
from collections import OrderedDict
from pathlib import Path

from openpyxl import load_workbook

from gate_export import write_xls
from sets import SETS, read_plate_maps

analysis, lab, out = sys.argv[1:4]
wb = load_workbook(analysis, data_only=True)
plate_of, cur = {}, None
for r in wb["Calc Sheet"].iter_rows(min_row=2, values_only=True):
    cur = r[0] or cur
    plate_of.setdefault(r[4], cur)
ws = wb["Raw data"]
head = [c.value for c in ws[1]]
paths = [h.split("|")[0].strip() for h in head[5:8]]          # Cells, Cells/Single Cells, Cells/Single Cells/LD
groups = OrderedDict()
for r in ws.iter_rows(min_row=2, values_only=True):
    freq = [f if isinstance(f, str) else f"{100 * f:.1f} %" for f in r[5:8]]   # one cell was typed as 0.928
    groups.setdefault(r[3], []).append(dict(sample=r[4], freq=freq, gmfi=float(r[8]), count=None))
layout = read_plate_maps(lab, SETS["Set1"]["sheet"])
for raw_name, rows in groups.items():
    plate = plate_of[raw_name]
    letters = {x["sample"][0] for x in rows}
    names = {x["cell_line"] for x in layout if x["plate"] == plate and x["row"] in letters}
    assert len(names) == 1 and len(rows) == 48, (raw_name, plate, names, len(rows))
    name = names.pop()
    f = write_xls(sorted(rows, key=lambda x: x["sample"]), paths, Path(out) / f"Plate{plate} {name}.xls")
    print(f"{f}: {len(rows)} wells ('{raw_name}' in the Analysis workbook)")
