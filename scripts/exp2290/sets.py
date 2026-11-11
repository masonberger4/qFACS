"""Exp2290 sets: read Mase's lab setup sheets (Design + dated Plate Maps) and build a qFACS setup workbook.

Each set is one lab setup sheet:
  Set1  Exp2290_qFACS_Setup.xlsx   'Plate Maps 10.19.26'  FlowJo gMFI table (Exp2290_Analysis.xlsx 'Raw data')
  Set2  Exp2290_qFACS_Setup2.xlsx  'Plate Maps 10.28.26'  Plate_001-004 .fcs + 02-Nov-2026*.wsp
  Set3  Exp2290_qFACS_Setup3.xlsx  'Plate Maps'           Kasumi 2 HT55 + CHO EGFR .fcs + .wsp (Plate 2 not supplied)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from qfacs.model import Setup  # noqa: E402

BEAD_LOT = dict(kit_lot="42618", lot_expiry="2022-10-31", pe_low=474, pe_med_low=5359, pe_med_high=23843, pe_high=62336)
BEADS_OCT20 = dict(low=1661, med_low=16383, med_high=72239, high=197572)   # FlowJo export of the 20-Oct-2026 tube

SETS = {
    "Set1": dict(sheet="Plate Maps 10.19.26", date="2026-10-20", live_gate="LD", bead_date="2026-10-20",
                 bead_note="Tube_001 acquired 20-Oct-2026 (FlowJo export 'Quantbrite PE Beads.xls', also in Exp2290_Analysis.xlsx)",
                 data_note="No .fcs supplied: gMFI from the FlowJo table in Exp2290_Analysis.xlsx ('Raw data')."),
    "Set2": dict(sheet="Plate Maps 10.28.26", date="2026-10-29", live_gate="Live", bead_date="2026-10-20",
                 bead_note="No bead tube was supplied for Set 2 (acquired 29-Oct-2026): the 20-Oct-2026 tube is used. Confirm.",
                 data_note="Plate_001-004 .fcs gated with 02-Nov-2026 (, 2, 3, 4).wsp (Cells > Single Cells > Live)."),
    "Set3": dict(sheet="Plate Maps", date="2026-11-04", live_gate="Live", bead_date="2026-11-05",
                 bead_note="Tube_001 acquired 05-Nov-2026 (FlowJo export 'Beads Analysis.xls')",
                 data_note="Kasumi 2 HT55 (Plate 1) and CHO EGFR (Plate 3) .fcs gated with their .wsp. "
                           "Plate 2 (CFPAC-1 / ZR-75-1) data was not supplied."),
}

REAGENT_NAMES = {"cd58": "CD58", "cd276": "B7H3", "dll3": "DLL3", "egfr": "EGFR", "mouse": "mIgG1"}
REAGENT_EXTRA = {
    "CD58": dict(host="Mouse", isotype="IgG1, κ"),
    "B7H3": dict(host="Mouse", isotype="IgG1, κ"),
    "EGFR": dict(host="Mouse", isotype="IgG1, κ"),
    "DLL3": dict(host="Rabbit", isotype="(chimeric)"),
    "mIgG1": dict(host="Mouse", isotype="IgG1, κ"),
}
# Mase, 2026-11-05: DLL3 (Novus NBP3-45128PE lot D224308) F/P 1.357 from the vial label (the Set 1 sheet says 0.8).
FP_OVERRIDE = {"DLL3": (1.357, "F/P 1.357 from the vial label (Mase, 2026-11-05); the Set 1 Design sheet lists 0.8")}


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def read_antibodies(xlsx):
    """Antibody table on the Design sheet -> list of reagent dicts (qFACS Reagents sheet keys)."""
    ws = load_workbook(xlsx, data_only=True)["Design"]
    hdr = next(r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 1).value or "").startswith("Antibody (all PE)"))
    out = []
    for r in range(hdr + 1, hdr + 8):
        label = ws.cell(r, 1).value
        if not label or str(label).startswith("Make"):
            break
        key = re.split(r"[ ,(]", str(label).strip().lower())[0]
        name = REAGENT_NAMES.get(key)
        if not name:
            continue
        iso = name == "mIgG1"
        fp = _num(ws.cell(r, 7).value)
        note = ""
        if name in FP_OVERRIDE:
            sheet_fp = fp
            fp, note = FP_OVERRIDE[name]
            note += f" (this sheet: {sheet_fp if sheet_fp is not None else 'blank'})"
        elif iso:
            note = "F/P not given ('-' on the Design sheet): isotype subtracted in PE units"
        elif fp is None:
            note = "F/P blank on the Design sheet: treated as 1 (1:1 PE conjugate) and flagged"
        lot = ws.cell(r, 5).value
        out.append(dict(name=name, target=None if iso else str(label).strip(), is_isotype="Y" if iso else "N",
                        clone=ws.cell(r, 2).value, catalog=str(ws.cell(r, 3).value or "") or None, vendor=ws.cell(r, 4).value,
                        lot=str(lot) if lot not in (None, "") and not isinstance(lot, (int, float)) else None,
                        stock_ug_ml=_num(ws.cell(r, 6).value if not isinstance(lot, (int, float)) else lot),
                        fp_ratio=fp, matched_isotype=None if iso else "mIgG1", notes=note, **REAGENT_EXTRA[name]))
    return out


def read_plate_maps(xlsx, sheet):
    """'PLATE n' blocks -> [dict(plate, row, cell_line, reagent, concs)] for rows that hold a reagent."""
    ws = load_workbook(xlsx, data_only=True)[sheet]
    rows, plate, concs, line = [], None, None, None
    for r in range(1, ws.max_row + 1):
        a, b = ws.cell(r, 1).value, ws.cell(r, 2).value
        m = re.match(r"PLATE\s+(\d+)", str(a or ""))
        if m:
            plate, line = int(m.group(1)), None
            continue
        if str(a or "").startswith("Antibody dilution block"):
            break
        if str(a or "").startswith("Final"):
            concs = [_num(ws.cell(r, c).value) for c in range(3, 14)]
            continue
        if plate is None or not (isinstance(b, str) and len(b.strip()) == 1 and b.strip() in "ABCDEFGH"):
            continue
        if a not in (None, ""):
            line = str(a).strip()
        first = ws.cell(r, 3).value
        if not first or not line or line.lower() == "empty":
            continue
        reagent = re.sub(r"-\d+$", "", str(first).strip())
        rows.append(dict(plate=plate, row=b.strip(), cell_line=line, reagent=reagent, concs=list(concs)))
    return rows


def build_setup(set_id, lab_xlsx, bead_file):
    info = SETS[set_id]
    layout = read_plate_maps(lab_xlsx, info["sheet"])
    reagents = read_antibodies(lab_xlsx)
    used = {x["reagent"] for x in layout}
    s = Setup()
    s.experiment = dict(experiment_id=f"Exp2290_{set_id}", date=info["date"], instrument="BD FACSDiscover A8",
                        pe_parameter="B5 (575)-A", live_gate=info["live_gate"], fixed_after_staining="Y",
                        min_live_events=1000, bead_r2_min=0.98, saturation_k=5,
                        notes=f"Built from {Path(lab_xlsx).name} sheet '{info['sheet']}'. {info['data_note']}")
    s.beads = [dict(bead_run=f"Beads_{info['bead_date']}", data_file=Path(bead_file).name, notes=info["bead_note"], **BEAD_LOT)]
    s.reagents = [r for r in reagents if r["name"] in used]
    lines = []
    for x in layout:
        if x["cell_line"] not in lines:
            lines.append(x["cell_line"])
    s.cell_lines = [dict(cell_line=n) for n in lines]
    s.plates = [dict(plate_id=f"Plate{p}", bead_run=s.beads[0]["bead_run"], acquired=info["date"], data_folder=f"Plate{p}")
                for p in sorted({x["plate"] for x in layout})]
    for x in layout:
        c = x["concs"]
        s.layout.append(dict(plate_id=f"Plate{x['plate']}", row=x["row"], cell_line=x["cell_line"], reagent=x["reagent"],
                             top_conc_ug_ml=c[0], dilution_factor=round(c[0] / c[1], 6), first_col=1, n_points=11, blank_cols="12"))
    return s, layout
