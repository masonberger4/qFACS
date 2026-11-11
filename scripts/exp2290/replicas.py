"""Exact-layout replicas of Mase's two hand-made files, for a set gated from .fcs + .wsp:

  <OUT>/cell_line_exports/Plate<N> <cell line>.xls   same layout as FlowJo's 'Plate1 A549.xls'
                                                     (sample, 3 x Freq. of Parent, Live gMFI, then Mean and SD)
  <OUT>/Exp2290_Analysis_<set>.xlsx                  Mase's Exp2290_Analysis.xlsx itself with the set's numbers:
                                                     'qFACS-setup-new' (date, beads, regression, antibody table),
                                                     'Raw data' and 'Calc Sheet'. Styles, charts, picture, hidden
                                                     sheets and conditional formats are the original's (the workbook
                                                     is edited at the XML level, not rebuilt).
  <OUT>/cell_line_exports_with_counts/               the same exports plus a Live Count column (for the engine's QC)

Usage:
  python replicas.py Set2 LAB_SETUP.xlsx Exp2290_Analysis.xlsx OUT_DIR --beads 1661 16383 72239 197572 \
      --bead-name "Tube_001 (20-Oct-2026)" --plate 1 "02-Nov-2026.wsp" Plate_001/ [--name "wsp group=cell line"]
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_export import fj_round, gate_plate, pct, write_xls  # noqa: E402
from sets import BEAD_LOT, SETS, read_plate_maps  # noqa: E402

from qfacs.stats_io import well_of  # noqa: E402

ISO_LABEL = "IgG1"          # Mase's label for the mIgG1 isotype rows


def collect(set_id, lab_xlsx, plates, rename):
    """Gate every plate. Returns [dict(plate, name, paths, rows)] in Mase's order (plate, then cell line name)."""
    layout = {(x["plate"], x["row"]): x for x in read_plate_maps(lab_xlsx, SETS[set_id]["sheet"])}
    lines = []
    for plate, wsp, fcs_dir in plates:
        groups, paths = gate_plate(wsp, fcs_dir)
        for g, rows in groups.items():
            out = []
            for r in rows:
                well = well_of(r["sample"])
                lay = layout.get((plate, well[0]))
                col = int(well[1:])
                if lay is None:
                    stain, antigen, conc = "Unstained", "none", 0.0
                else:
                    iso = lay["reagent"].lower().startswith("migg")
                    stain, antigen = ("Isotype", ISO_LABEL) if iso else ("Antigen", lay["reagent"])
                    conc = lay["concs"][col - 1] if col <= 11 else 0.0
                out.append(dict(sample=r["sample"], well=well, row=well[0], col=col, freq=[pct(f) for f in r["freq"]],
                                gmfi=fj_round(r["gmfi"]), raw=r, count=r["count"], stain=stain, antigen=antigen, conc=conc))
            lines.append(dict(plate=plate, name=rename.get(g, g), paths=paths, rows=out))
    return sorted(lines, key=lambda x: (x["plate"], x["name"].lower()))


# ---------------------------------------------------------------------------------------------- xlsx XML helpers
def istr(ref, text, style=None):
    s = f' s="{style}"' if style is not None else ""
    sp = ' xml:space="preserve"' if text != text.strip() else ""
    return f'<c r="{ref}"{s} t="inlineStr"><is><t{sp}>{escape(str(text))}</t></is></c>'


def num(ref, value, style=None, formula=None):
    s = f' s="{style}"' if style is not None else ""
    f = f"<f>{escape(formula)}</f>" if formula else ""
    return f'<c r="{ref}"{s}>{f}<v>{value!r}</v></c>' if value is not None else f'<c r="{ref}"{s}/>'


def n(v):
    """Whole numbers without '.0', like Excel writes them."""
    return int(v) if float(v).is_integer() else float(v)


def replace_cell(xml, ref, new):
    """Swap one <c r="REF" .../> or <c r="REF" ...>...</c> for new XML (the cell must exist)."""
    pat = re.compile(rf'<c r="{ref}"(?:[^>]*?/>|[^>]*?>.*?</c>)', re.S)
    assert pat.search(xml), ref
    return pat.sub(lambda m: new, xml, count=1)


def cell_style(xml, ref):
    m = re.search(rf'<c r="{ref}"[^>]*? s="(\d+)"', xml)
    return m.group(1) if m else None


def swap_rows(xml, rows_xml):
    """Keep row 1 (the header) and everything outside <sheetData>; replace the data rows."""
    a, b = xml.index("<sheetData>") + len("<sheetData>"), xml.index("</sheetData>")
    header = re.match(r"<row .*?</row>", xml[a:b], re.S).group(0)
    return xml[:a] + header + "".join(rows_xml) + xml[b:]


def raw_sheet(xml, lines):
    rows, r = [], 2
    for ln in lines:
        for x in ln["rows"]:
            cells = [istr(f"A{r}", x["stain"], 3), istr(f"B{r}", x["antigen"], 3), num(f"C{r}", n(x["conc"]), 44 if x["conc"] else 3),
                     istr(f"D{r}", ln["name"], 3), istr(f"E{r}", x["sample"])]
            cells += [istr(f"{c}{r}", f) for c, f in zip("FGH", x["freq"])]
            cells.append(num(f"I{r}", n(x["gmfi"])))
            rows.append(f'<row r="{r}" spans="1:9" x14ac:dyDescent="0.25">{"".join(cells)}</row>')
            r += 1
    xml = swap_rows(xml, rows)
    paths = lines[0]["paths"]
    for col, text in zip("FGHI", [f"{p} | Freq. of Parent" for p in paths] + [f"{paths[-1]} | Geometric Mean (B5 (575)-A)"]):
        xml = replace_cell(xml, f"{col}1", istr(f"{col}1", text, cell_style(xml, f"{col}1")))
    xml = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:I{r - 1}"/>', xml)
    return re.sub(r"<selection [^>]*/>", '<selection activeCell="A2" sqref="A2"/>', xml)


def calc_sheet(xml, lines):
    """A Plate# (merged per cell line), B-F as Raw data, G = F - highest unstained well of the line (0 if negative),
    H = F - isotype gMFI at the same concentration: the formulas Mase used on his sheet."""
    rows, merges, r = [], [], 2
    for ln in lines:
        first = r
        at = {x["well"]: first + i for i, x in enumerate(ln["rows"])}
        blanks = [x for x in ln["rows"] if x["col"] == 12]
        ref = max(blanks, key=lambda x: x["gmfi"])
        iso_row = next((x["row"] for x in ln["rows"] if x["stain"] == "Isotype"), None)
        for x in ln["rows"]:
            cells = [num(f"A{r}", ln["plate"] if r == first else None, 47), istr(f"B{r}", x["stain"], 12),
                     istr(f"C{r}", x["antigen"], 12), num(f"D{r}", n(x["conc"]), 12), istr(f"E{r}", ln["name"], 12),
                     num(f"F{r}", n(x["gmfi"]), 12)]
            g = x["gmfi"] - ref["gmfi"]
            cells.append(num(f"G{r}", n(g), 12, f"F{r}-$F${at[ref['well']]}") if g >= 0 else num(f"G{r}", 0, 12))
            if iso_row and x["stain"] != "Unstained":
                iso = next(q for q in ln["rows"] if q["row"] == iso_row and q["col"] == x["col"])
                cells.append(num(f"H{r}", n(x["gmfi"] - iso["gmfi"]), None, f"F{r}-$F${at[iso['well']]}"))
            rows.append(f'<row r="{r}" spans="1:8" x14ac:dyDescent="0.25">{"".join(cells)}</row>')
            r += 1
        merges.append(f'<mergeCell ref="A{first}:A{r - 1}"/>')
    last = r - 1
    xml = swap_rows(xml, rows)
    xml = re.sub(r"<mergeCells .*?</mergeCells>", f'<mergeCells count="{len(merges)}">{"".join(merges)}</mergeCells>', xml, flags=re.S)
    xml = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:H{last}"/>', xml)
    xml = xml.replace('sqref="F2:F577"', f'sqref="F2:F{last}"').replace('sqref="G1:G433 G530:G1048576"', 'sqref="G1:G1048576"')
    xml = re.sub(r'<conditionalFormatting sqref="G434:G529">.*?</conditionalFormatting>', "", xml, flags=re.S)
    xml = re.sub(r' topLeftCell="[^"]*"', "", xml)
    return re.sub(r"<selection [^>]*/>", '<selection activeCell="A2" sqref="A2"/>', xml)


def setup_sheet(xml, set_id, lab_xlsx, beads, bead_name):
    date = dt.date.fromisoformat(SETS[set_id]["date"])
    pe = [BEAD_LOT[k] for k in ("pe_low", "pe_med_low", "pe_med_high", "pe_high")]
    m, c = np.polyfit(pe, beads, 1)
    r2 = float(np.corrcoef(pe, beads)[0, 1] ** 2)
    xml = replace_cell(xml, "B1", num("B1", (date - dt.date(1899, 12, 30)).days, cell_style(xml, "B1")))
    xml = replace_cell(xml, "C5", istr("C5", bead_name))
    for j, col in enumerate("DEFG"):
        xml = replace_cell(xml, f"{col}5", num(f"{col}5", n(beads[j])))
        xml = replace_cell(xml, f"E{10 + j}", num(f"E{10 + j}", n(beads[j]), cell_style(xml, f"E{10 + j}")))
        xml = replace_cell(xml, f"G{10 + j}", num(f"G{10 + j}", n(pe[j]), cell_style(xml, f"G{10 + j}")))
        # E17:F20 keep their formulas (=G10.., =E10..); only the stored values change
        xml = re.sub(rf'(<c r="E{17 + j}"[^>]*>(?:<f[^>]*>[^<]*</f>|<f[^>]*/>)<v>)[^<]*(</v>)', rf"\g<1>{n(pe[j])}\g<2>", xml)
        xml = re.sub(rf'(<c r="F{17 + j}"[^>]*>(?:<f[^>]*>[^<]*</f>|<f[^>]*/>)<v>)[^<]*(</v>)', rf"\g<1>{n(beads[j])}\g<2>", xml)
    xml = replace_cell(xml, "C24", istr("C24", f"y ={m:.4f}x {'-' if c < 0 else '+'} {abs(c):.5g}", cell_style(xml, "C24")))
    xml = replace_cell(xml, "C25", istr("C25", f"R² = {r2:.4f}", cell_style(xml, "C25")))
    # antibody table, exactly as on this set's Design sheet (header row 31, antibodies in rows 32-35)
    ws = load_workbook(lab_xlsx, data_only=True)["Design"]
    r0 = next(r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 1).value or "").startswith("Antibody (all PE)"))
    for i in range(5):
        for j in range(10):
            ref = f"{'ABCDEFGHIJ'[j]}{31 + i}"
            v = ws.cell(r0 + i, j + 1).value
            st = cell_style(xml, ref)
            if v is None or v == "":
                new = f'<c r="{ref}" s="{st}"/>'
            elif isinstance(v, (int, float)) and j >= 5:      # A-E are text columns (a catalog number stays text)
                new = num(ref, n(v), st)
            else:
                new = istr(ref, str(v), st)
            xml = replace_cell(xml, ref, new)
    return re.sub(r' topLeftCell="[^"]*"', "", xml), (m, c, r2)


def chart_cache(xml, values):
    """Refresh the numbers stored inside a chart ({cell or range: [values]})."""
    def fix(m):
        vals = values.get(m.group(1).split("!")[-1].replace("$", ""))
        if vals is None:
            return m.group(0)
        it = iter(vals)
        return re.sub(r"<c:v>[^<]*</c:v>", lambda _: f"<c:v>{n(next(it))}</c:v>", m.group(0))
    return re.sub(r"<c:numRef><c:f>([^<]*)</c:f>.*?</c:numRef>", fix, xml, flags=re.S)


def fill_analysis(template, out, set_id, lab_xlsx, lines, beads, bead_name):
    pe = [BEAD_LOT[k] for k in ("pe_low", "pe_med_low", "pe_med_high", "pe_high")]
    cache = {"E17:E20": pe, "F17:F20": beads}
    for j in range(4):
        cache[f"E{10 + j}"], cache[f"G{10 + j}"] = [beads[j]], [pe[j]]
    with zipfile.ZipFile(template) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        names = dict(re.findall(r'<sheet name="([^"]*)"[^>]*r:id="(rId\d+)"', zin.read("xl/workbook.xml").decode()))
        rels = dict(re.findall(r'<Relationship Id="(rId\d+)"[^>]*Target="(worksheets/[^"]*)"', zin.read("xl/_rels/workbook.xml.rels").decode()))
        part = {name: "xl/" + rels[rid] for name, rid in names.items()}
        fit = None
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/calcChain.xml":
                continue                     # formulas moved: let Excel rebuild its calculation chain
            if item.filename == part["Raw data"]:
                data = raw_sheet(data.decode(), lines).encode()
            elif item.filename == part["Calc Sheet"]:
                data = calc_sheet(data.decode(), lines).encode()
            elif item.filename == part["qFACS-setup-new"]:
                xml, fit = setup_sheet(data.decode(), set_id, lab_xlsx, beads, bead_name)
                data = xml.encode()
            elif item.filename.startswith("xl/charts/chart"):
                data = chart_cache(data.decode(), cache).encode()
            elif item.filename == "xl/_rels/workbook.xml.rels":
                data = re.sub(r'<Relationship Id="rId\d+" Type="[^"]*calcChain" Target="calcChain.xml"/>', "", data.decode()).encode()
            elif item.filename == "[Content_Types].xml":
                data = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", data.decode()).encode()
            elif item.filename == "xl/workbook.xml":
                data = data.decode().replace('<calcPr calcId="191028"/>', '<calcPr calcId="191028" fullCalcOnLoad="1"/>').encode()
            zout.writestr(item, data)
    return fit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("set_id")
    ap.add_argument("lab_setup")
    ap.add_argument("template", help="Mase's Exp2290_Analysis.xlsx")
    ap.add_argument("out_dir")
    ap.add_argument("--plate", nargs=3, action="append", metavar=("N", "WSP", "FCS_DIR"), required=True)
    ap.add_argument("--name", action="append", default=[], help='"workspace group=cell line name"')
    ap.add_argument("--beads", nargs=4, type=float, required=True, metavar=("LOW", "MEDLOW", "MEDHIGH", "HIGH"))
    ap.add_argument("--bead-name", required=True)
    a = ap.parse_args()
    out = Path(a.out_dir)
    lines = collect(a.set_id, a.lab_setup, [(int(p), w, d) for p, w, d in a.plate], dict(x.split("=", 1) for x in a.name))
    for ln in lines:
        rows = [x["raw"] for x in ln["rows"]]          # unrounded, so Mean and SD are FlowJo's (from full precision)
        name = f"Plate{ln['plate']} {ln['name']}.xls"
        write_xls(rows, ln["paths"], out / "cell_line_exports" / name, with_count=False)
        write_xls(rows, ln["paths"], out / "cell_line_exports_with_counts" / name)
        print(f"{name}: {len(rows)} wells, gMFI {min(x['gmfi'] for x in rows):.0f}-{max(x['gmfi'] for x in rows):.0f}")
    book = out / f"Exp2290_Analysis_{a.set_id}.xlsx"
    m, c, r2 = fill_analysis(a.template, book, a.set_id, a.lab_setup, lines, a.beads, a.bead_name)
    print(f"{book}: {len(lines)} cell lines, {sum(len(x['rows']) for x in lines)} wells; bead line y = {m:.4f}x {c:+.2f}, R2 {r2:.4f}")


if __name__ == "__main__":
    main()
