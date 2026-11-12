"""Fill Mase's Exp2290_Analysis workbook from FlowJo table exports (one .xls per cell line + one bead .xls).

The template (e.g. his Exp2290_Analysis_Set2.xlsx) is edited at the XML level, so sheets, styles, merged cells,
conditional formats, charts, picture and hidden sheets stay exactly his. Only these cells change:

  qFACS-setup-new  B1 date, C5:G5 bead sample + gMFI, E10:E13 bead gMFI, E17:F20 cached values, C24/C25 bead line
                   text, A31:J35 antibody table (copied from the set's Design sheet), chart caches
  Calc Sheet       rows 2.. : Plate#, Well, Stain, Antigen, Ab conc, Cell line, gMFI, gMFI minus the line's highest
                   column-12 (no antibody) well (0 when negative), column I left empty as on his sheet
  Raw data, Sheet2, Nectin-4 are left as they are in the template.

Usage:
  python analysis_from_exports.py TEMPLATE.xlsx LAB_SETUP.xlsx EXPORT_DIR OUT.xlsx --date 2026-11-04 [--plate-sheet "Plate Maps"]
EXPORT_DIR holds 'Beads Analysis.xls' and 'Plate<N> <cell line>.xls' files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import xlrd
from openpyxl import load_workbook

PE_PER_BEAD = [474, 5359, 23843, 62336]          # lot 42618: Low, Med Low, Med High, High
ISO_LABEL = "IgG1"


def n(v):
    v = float(v)
    return int(v) if v.is_integer() else v


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("-nr", ""))


# ------------------------------------------------------------------------------------------------- inputs
def read_beads(path):
    sh = xlrd.open_workbook(path).sheet_by_index(0)
    hdr = sh.row_values(0)
    row = sh.row_values(1)
    gm = {}
    for i, h in enumerate(hdr):
        m = re.match(r"Beads/(Low|Med Low|Med High|High) \| Geometric Mean", str(h))
        if m:
            gm[m.group(1)] = row[i]
    return row[0], [gm[k] for k in ("Low", "Med Low", "Med High", "High")]


def read_line(path):
    sh = xlrd.open_workbook(path).sheet_by_index(0)
    hdr = sh.row_values(0)
    gcol = next(i for i, h in enumerate(hdr) if "Geometric Mean" in str(h))
    rows = []
    for r in range(1, sh.nrows):
        v = sh.row_values(r)
        m = re.match(r"([A-H])(\d{2})-", str(v[0]))
        if not m:
            continue                                   # Mean / SD rows
        rows.append(dict(sample=v[0], row=m.group(1), col=int(m.group(2)), gmfi=v[gcol]))
    return rows


def read_plate_maps(lab_xlsx, sheet):
    """{normalised cell line: {row letter: reagent or None}} and the 11 final concentrations."""
    ws = load_workbook(lab_xlsx, data_only=True)[sheet]
    out, line, concs = {}, None, None
    for r in range(1, ws.max_row + 1):
        a, b, c = ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 3).value
        if str(a or "").startswith("Antibody dilution block"):
            break
        if str(a or "").startswith("Final"):
            concs = [ws.cell(r, k).value for k in range(3, 14)]
            continue
        if str(a or "").startswith("PLATE"):
            line = None
            continue
        if not (isinstance(b, str) and b.strip() in list("ABCDEFGH")):
            continue
        if a not in (None, ""):
            line = norm(str(a))
        if line and line != "empty":
            out.setdefault(line, {})[b.strip()] = re.sub(r"-\d+$", "", str(c).strip()) if c else None
    return out, concs


# ------------------------------------------------------------------------------------------------- XML helpers
def istr(ref, text, style=None):
    s = f' s="{style}"' if style is not None else ""
    return f'<c r="{ref}"{s} t="inlineStr"><is><t>{escape(str(text))}</t></is></c>'


def num(ref, value, style=None, formula=None):
    s = f' s="{style}"' if style is not None else ""
    if value is None:
        return f'<c r="{ref}"{s}/>'
    f = f"<f>{escape(formula)}</f>" if formula else ""
    return f'<c r="{ref}"{s}>{f}<v>{value!r}</v></c>'


def replace_cell(xml, ref, new):
    pat = re.compile(rf'<c r="{ref}"(?:[^>]*?/>|[^>]*?>.*?</c>)', re.S)
    assert pat.search(xml), ref
    return pat.sub(lambda m: new, xml, count=1)


def cell_style(xml, ref):
    m = re.search(rf'<c r="{ref}"[^>]*? s="(\d+)"', xml)
    return m.group(1) if m else None


# ------------------------------------------------------------------------------------------------- sheets
def calc_sheet(xml, lines):
    rows, merges, r = [], [], 2
    plates = {}
    for ln in lines:
        plates.setdefault(ln["plate"], []).append(ln)
    first_line = True
    for plate, lns in plates.items():
        plate_first = r
        for ln in lns:
            first = r
            at = {(x["row"], x["col"]): first + i for i, x in enumerate(ln["rows"])}
            ref = max((x for x in ln["rows"] if x["col"] == 12), key=lambda x: x["gmfi"])
            ref_row = at[(ref["row"], ref["col"])]
            for x in ln["rows"]:
                spans = "1:9" if r == 2 else "1:8"
                cells = [num(f"A{r}", plate if r == plate_first else None, 47),
                         istr(f"B{r}", f"{x['row']}{x['col']}", 3),
                         istr(f"C{r}", x["stain"], 12), istr(f"D{r}", x["antigen"], 12),
                         num(f"E{r}", n(x["conc"]), 12)]
                fs = 54 if first_line and r == first else 47
                cells.append(istr(f"F{r}", ln["name"], fs) if r == first else num(f"F{r}", None, fs))
                cells.append(num(f"G{r}", n(x["gmfi"])))
                g = x["gmfi"] - ref["gmfi"]
                cells.append(num(f"H{r}", n(g), 12, f"G{r}-$G${ref_row}") if g >= 0 else num(f"H{r}", 0, 12))
                rows.append(f'<row r="{r}" spans="{spans}" x14ac:dyDescent="0.25">{"".join(cells)}</row>')
                r += 1
            merges.append(f'<mergeCell ref="F{first}:F{r - 1}"/>')
            first_line = False
        merges.insert(0, f'<mergeCell ref="A{plate_first}:A{r - 1}"/>')
    last = r - 1
    a, b = xml.index("<sheetData>") + len("<sheetData>"), xml.index("</sheetData>")
    header = re.match(r"<row .*?</row>", xml[a:b], re.S).group(0)
    xml = xml[:a] + header + "".join(rows) + xml[b:]
    xml = re.sub(r"<mergeCells .*?</mergeCells>", f'<mergeCells count="{len(merges)}">{"".join(merges)}</mergeCells>', xml, flags=re.S)
    xml = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:I{last}"/>', xml)
    xml = re.sub(r'<autoFilter ref="[^"]*"', f'<autoFilter ref="A1:I{last}"', xml)
    xml = re.sub(r'sqref="G2:G\d+"', f'sqref="G2:G{last}"', xml)
    xml = re.sub(r' topLeftCell="[^"]*"', "", xml)
    return re.sub(r"<selection [^>]*/>", '<selection activeCell="A2" sqref="A2"/>', xml), last


def setup_sheet(xml, date, bead_name, beads, lab_xlsx):
    m, c = np.polyfit(PE_PER_BEAD, beads, 1)
    r2 = float(np.corrcoef(PE_PER_BEAD, beads)[0, 1] ** 2)
    xml = replace_cell(xml, "B1", num("B1", (date - dt.date(1899, 12, 30)).days, cell_style(xml, "B1")))
    xml = replace_cell(xml, "C5", istr("C5", bead_name, cell_style(xml, "C5")))
    for j, col in enumerate("DEFG"):
        xml = replace_cell(xml, f"{col}5", num(f"{col}5", n(beads[j]), cell_style(xml, f"{col}5")))
        xml = replace_cell(xml, f"E{10 + j}", num(f"E{10 + j}", n(beads[j]), cell_style(xml, f"E{10 + j}")))
        xml = re.sub(rf'(<c r="E{17 + j}"[^>]*>(?:<f[^>]*>[^<]*</f>|<f[^>]*/>)<v>)[^<]*(</v>)', rf"\g<1>{PE_PER_BEAD[j]}\g<2>", xml)
        xml = re.sub(rf'(<c r="F{17 + j}"[^>]*>(?:<f[^>]*>[^<]*</f>|<f[^>]*/>)<v>)[^<]*(</v>)', rf"\g<1>{n(beads[j])}\g<2>", xml)
    xml = replace_cell(xml, "C24", istr("C24", f"y ={m:.4f}x {'-' if c < 0 else '+'} {abs(c):.2f}", cell_style(xml, "C24")))
    xml = replace_cell(xml, "C25", istr("C25", f"R² = {r2:.4f}", cell_style(xml, "C25")))
    ws = load_workbook(lab_xlsx, data_only=True)["Design"]
    r0 = next(r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 1).value or "").startswith("Antibody (all PE)"))
    for i in range(5):
        for j in range(10):
            ref = f"{'ABCDEFGHIJ'[j]}{31 + i}"
            v = ws.cell(r0 + i, j + 1).value
            st = cell_style(xml, ref)
            if v is None or v == "":
                new = f'<c r="{ref}" s="{st}"/>' if st else f'<c r="{ref}"/>'
            elif isinstance(v, (int, float)) and j >= 5:
                new = num(ref, n(v), st)
            else:
                new = istr(ref, str(v), st)
            xml = replace_cell(xml, ref, new)
    xml = re.sub(r' topLeftCell="[^"]*"', "", xml)
    return xml, (m, c, r2)


def chart_cache(xml, values):
    def fix(mt):
        vals = values.get(mt.group(1).split("!")[-1].replace("$", ""))
        if vals is None:
            return mt.group(0)
        it = iter(vals)
        return re.sub(r"<c:v>[^<]*</c:v>", lambda _: f"<c:v>{n(next(it))}</c:v>", mt.group(0))
    return re.sub(r"<c:numRef><c:f>([^<]*)</c:f>.*?</c:numRef>", fix, xml, flags=re.S)


# ------------------------------------------------------------------------------------------------- main
def collect(export_dir, lab_xlsx, plate_sheet):
    layout, concs = read_plate_maps(lab_xlsx, plate_sheet)
    lines = []
    for p in sorted(Path(export_dir).glob("Plate* *.xls")):
        m = re.match(r"Plate(\d+) (.+)\.xls$", p.name)
        plate, name = int(m.group(1)), m.group(2)
        lay = layout[norm(name)]
        rows = read_line(p)
        for x in rows:
            reagent = lay.get(x["row"])
            if reagent is None:
                x["stain"], x["antigen"], x["conc"] = "Unstained", "none", 0
            else:
                iso = reagent.lower().startswith("migg")
                x["stain"], x["antigen"] = ("Isotype", ISO_LABEL) if iso else ("Antigen", reagent)
                x["conc"] = concs[x["col"] - 1] if x["col"] <= 11 else 0
        lines.append(dict(plate=plate, name=name, rows=rows, first_row=min(x["row"] for x in rows)))
    return sorted(lines, key=lambda x: (x["plate"], x["first_row"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("lab_setup")
    ap.add_argument("export_dir")
    ap.add_argument("out")
    ap.add_argument("--date", required=True)
    ap.add_argument("--plate-sheet", default="Plate Maps")
    ap.add_argument("--set-folder", default=None, help="replace 'Set2/' in the saved path, e.g. Set3")
    a = ap.parse_args()
    lines = collect(a.export_dir, a.lab_setup, a.plate_sheet)
    bead_name, beads = read_beads(Path(a.export_dir) / "Beads Analysis.xls")
    cache = {"E17:E20": PE_PER_BEAD, "F17:F20": beads}
    for j in range(4):
        cache[f"E{10 + j}"], cache[f"G{10 + j}"] = [beads[j]], [PE_PER_BEAD[j]]
    with zipfile.ZipFile(a.template) as zin, zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zout:
        names = dict(re.findall(r'<sheet name="([^"]*)" sheetId="\d+"(?: state="\w+")? r:id="(rId\d+)"', zin.read("xl/workbook.xml").decode()))
        rels = dict(re.findall(r'<Relationship Id="(rId\d+)"[^>]*Target="(worksheets/[^"]*)"', zin.read("xl/_rels/workbook.xml.rels").decode()))
        part = {nm: "xl/" + rels[rid] for nm, rid in names.items()}
        last = fit = None
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/calcChain.xml":
                continue
            if item.filename == part["Calc Sheet"]:
                xml, last = calc_sheet(data.decode(), lines)
                data = xml.encode()
            elif item.filename == part["qFACS-setup-new"]:
                xml, fit = setup_sheet(data.decode(), dt.date.fromisoformat(a.date), bead_name, beads, a.lab_setup)
                data = xml.encode()
            elif item.filename.startswith("xl/charts/chart"):
                data = chart_cache(data.decode(), cache).encode()
            elif item.filename == "xl/_rels/workbook.xml.rels":
                data = re.sub(r'<Relationship Id="rId\d+" Type="[^"]*calcChain" Target="calcChain.xml"/>', "", data.decode()).encode()
            elif item.filename == "[Content_Types].xml":
                data = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", data.decode()).encode()
            elif item.filename == "xl/workbook.xml":
                x = data.decode()
                x = re.sub(r"<calcPr ([^/]*?)/>", lambda mt: f"<calcPr {mt.group(1).replace(' fullCalcOnLoad=\"1\"', '')} fullCalcOnLoad=\"1\"/>", x)
                if a.set_folder:
                    x = x.replace("/Analysis/Set2/", f"/Analysis/{a.set_folder}/")
                data = x.encode()
            zout.writestr(item, data)
    # the filter range is fixed after the Calc Sheet is rebuilt
    with zipfile.ZipFile(a.out) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for i, d in items:
            if i.filename == "xl/workbook.xml":
                d = re.sub(rb"'Calc Sheet'!\$A\$1:\$I\$\d+", f"'Calc Sheet'!$A$1:$I${last}".encode(), d)
            z.writestr(i, d)
    m, c, r2 = fit
    for ln in lines:
        print(f"Plate {ln['plate']} {ln['name']}: {len(ln['rows'])} wells")
    print(f"beads {bead_name} {beads}; y = {m:.4f}x {c:+.2f}, R2 {r2:.4f}; Calc Sheet rows 2-{last}")


if __name__ == "__main__":
    main()
