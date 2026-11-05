"""Convert an older qFACS setup workbook (Exp2281 style: Design / Cell Lines / Plate Maps sheets)
into the qfacs setup template.

    python scripts/convert_legacy_setup.py Exp2281_qFACS_Setup.xlsx out.xlsx \
        [--plate-sheet "Plate Maps 10.19.26"] [--panel legacy/excel_v1/qFACS_Plate1.xlsx]

Only values recorded in the source files are copied. Lot-specific values that the source lacks
(bead PE/bead, missing F/P) stay blank so the validator asks for them.
--panel takes host species / isotype and missing lot numbers from the v1 workbook's Antibody_Panel.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qfacs.model import Setup  # noqa: E402
from qfacs.template import write_setup  # noqa: E402


def _txt(v):
    return None if v is None or str(v).strip() in ("", "-") else str(v).strip()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _key(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def match_code(code: str, design_names: list[str]) -> str | None:
    """Map a plate-map code (CD58, B7H3, mIgG1) to a Design antibody name."""
    k = _key(code)
    hits = [n for n in design_names if k and k in _key(n)]
    if len(hits) == 1:
        return hits[0]
    m = re.match(r"^m(igg\w*)$", k)  # mIgG1 -> 'Mouse IgG1,k isotype'
    if m:
        hits = [n for n in design_names if "mouse" in n.lower() and m.group(1) in _key(n)]
        if len(hits) == 1:
            return hits[0]
    return None


def read_design(ws):
    exp = None
    m = re.search(r"exp\s*(\d+)", str(ws["A1"].value or ""), re.I)
    if m:
        exp = f"Exp{m.group(1)}"
    hdr = next(r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 1).value or "").lower().startswith("antibody"))
    cols = {str(ws.cell(hdr, c).value or "").strip().lower(): c for c in range(1, ws.max_column + 1)}
    def col(prefix):
        return next((c for h, c in cols.items() if h.startswith(prefix)), None)
    abs_ = []
    r = hdr + 1
    while _txt(ws.cell(r, 1).value) and _txt(ws.cell(r, col("clone")).value):
        g = lambda p: ws.cell(r, col(p)).value if col(p) else None
        abs_.append(dict(design_name=_txt(g("antibody")), clone=_txt(g("clone")), catalog=_txt(g("catalog")),
                         vendor=_txt(g("vendor")), lot=_txt(g("lot")), stock=_num(g("stock")), fp=_num(g("f/p"))))
        r += 1
    return exp, abs_


def read_panel(path):
    """v1 Antibody_Panel rows by Name: host/isotype and lot."""
    ws = load_workbook(path, data_only=True)["Antibody_Panel"]
    out = {}
    for r in range(5, ws.max_row + 1):
        name = _txt(ws.cell(r, 1).value)
        if not name:
            continue
        hi = _txt(ws.cell(r, 8).value) or ""
        host, _, iso = hi.partition(" ")
        lot = _txt(ws.cell(r, 7).value)
        out[name] = dict(target=_txt(ws.cell(r, 2).value), host=host or None, isotype=iso.strip() or None,
                         lot=None if lot and "not visible" in lot else lot)
    return out


def read_plate_maps(ws):
    """Yield plate blocks: (plate_no, set_no, conc by column, [(row letter, cell line, tokens by column)])."""
    blocks, cur = [], None
    for r in range(1, ws.max_row + 1):
        a = _txt(ws.cell(r, 1).value)
        m = re.match(r"plate\s*(\d+)\s*\(set\s*(\d+)\)", a or "", re.I)
        if m:
            cur = dict(plate=int(m.group(1)), set=int(m.group(2)), conc={}, rows=[], line=None)
            blocks.append(cur)
            continue
        if cur is None:
            continue
        if a and a.lower().startswith("final"):
            cur["conc"] = {c - 2: _num(ws.cell(r, c).value) for c in range(3, 15)}
            continue
        letter = _txt(ws.cell(r, 2).value)
        if letter and len(letter) == 1 and letter.upper() in "ABCDEFGH":
            if a:
                cur["line"] = a
            tokens = {c - 2: _txt(ws.cell(r, c).value) for c in range(3, 15)}
            cur["rows"].append((letter.upper(), cur["line"], tokens))
    return blocks


def convert(src, plate_sheet=None, panel=None) -> tuple[Setup, list[str]]:
    wb = load_workbook(src, data_only=True)
    notes = []
    exp_id, design = read_design(wb["Design"])
    if plate_sheet is None:
        dated = [n for n in wb.sheetnames if n.lower().startswith("plate maps ")]
        plate_sheet = dated[-1] if dated else "Plate Maps"
    notes.append(f"plate layout taken from sheet '{plate_sheet}'")
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2})", plate_sheet)
    acquired = f"20{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None
    pan = read_panel(panel) if panel else {}

    s = Setup()
    s.experiment = dict(experiment_id=exp_id, date=acquired, instrument="BD FACSDiscover A8", live_gate="Live",
                        fixed_after_staining="Y" if _protocol_fixes(wb) else None,
                        notes=f"Converted from {Path(src).name} ({plate_sheet})")
    if panel:
        try:
            s.experiment["pe_parameter"] = _txt(load_workbook(panel, data_only=True)["Setup"]["B8"].value)
        except KeyError:
            pass

    blocks = [b for b in read_plate_maps(wb[plate_sheet]) if any(l and l.lower() != "empty" for _, l, _ in b["rows"])]
    codes = sorted({t.rsplit("-", 1)[0] for b in blocks for _, _, toks in b["rows"] for t in toks.values()
                    if t and t.lower() != "bkg"})
    names = [d["design_name"] for d in design]
    isotype_names = []
    for code in codes:
        dn = match_code(code, names)
        d = next((x for x in design if x["design_name"] == dn), {})
        if not d:
            notes.append(f"plate-map code '{code}' has no match on the Design sheet; reagent left mostly blank")
        p = pan.get(code, {})
        is_iso = "isotype" in (dn or "").lower() or "isotype" in (p.get("target") or "").lower()
        lot = d.get("lot") or p.get("lot")
        if lot and not d.get("lot"):
            notes.append(f"{code}: lot {lot} taken from the v1 panel")
        s.reagents.append(dict(name=code, target=None if is_iso else (dn or p.get("target")), is_isotype="Y" if is_iso else "N",
                               host=p.get("host"), isotype=p.get("isotype"), clone=d.get("clone"), vendor=d.get("vendor"),
                               catalog=d.get("catalog"), lot=lot, stock_ug_ml=d.get("stock"), fp_ratio=d.get("fp")))
        if is_iso:
            isotype_names.append(code)
    if len(isotype_names) == 1:
        for r in s.reagents:
            if r["is_isotype"] == "N":
                r["matched_isotype"] = isotype_names[0]
    for r in s.reagents:
        if r["fp_ratio"] is None:
            notes.append(f"{r['name']}: F/P not on the Design sheet; enter it from the vial or CoA")

    ws = wb["Cell Lines"]
    for r in range(3, ws.max_row + 1):
        name, fp = _txt(ws.cell(r, 1).value), _txt(ws.cell(r, 2).value)
        if name and fp and fp.isdigit():
            s.cell_lines.append(dict(cell_line=name, source_id=f"FP# {fp}"))

    sets = sorted({b["set"] for b in blocks})
    for k in sets:
        s.beads.append(dict(bead_run=f"Set{k}", notes="Enter the kit lot and PE/bead values from the lot flyer"))
    for b in blocks:
        pid = f"Plate{b['plate']}"
        s.plates.append(dict(plate_id=pid, bead_run=f"Set{b['set']}", acquired=acquired))
        for letter, line, toks in b["rows"]:
            if not line or line.lower() == "empty":
                continue
            blanks = [c for c, t in toks.items() if t and t.lower() == "bkg"]
            ab_cols = sorted(c for c, t in toks.items() if t and t.lower() != "bkg")
            if not ab_cols:
                continue
            code = toks[ab_cols[0]].rsplit("-", 1)[0]
            first, n = ab_cols[0], len(ab_cols)
            c0, c1 = b["conc"].get(first), b["conc"].get(first + 1)
            s.layout.append(dict(plate_id=pid, row=letter, cell_line=line, reagent=code, top_conc_ug_ml=c0,
                                 dilution_factor=round(c0 / c1, 6) if c0 and c1 else None, first_col=first, n_points=n,
                                 blank_cols=",".join(str(c) for c in blanks) or None))
    return s, notes


def _protocol_fixes(wb) -> bool:
    if "Protocol" not in wb.sheetnames:
        return False
    return any("pfa" in str(c.value or "").lower() for row in wb["Protocol"].iter_rows() for c in row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--plate-sheet")
    ap.add_argument("--panel")
    a = ap.parse_args()
    setup, notes = convert(a.src, a.plate_sheet, a.panel)
    write_setup(a.out, setup)
    for n in notes:
        print("note:", n)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
