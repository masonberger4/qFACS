"""One QuantiBRITE_ABC_calculator.xlsx per cell line.

Takes Mase's calculator workbook as it is and, for each cell line of a set, fills a copy with
  Beads tab    the set's bead gMFI (lot PE/bead unchanged)
  antigen tab  the 11 concentrations and the Live gMFI minus the cell line's highest no-antibody well (0 where
               negative), plus (0, 0): the 'Antigen (unstain substracted)' column of Mase's Calc Sheet, which is
               what his own solved tabs hold; the antibody's F/P; and Bmax, Kd, NS at the minimum-SSE fit (what
               Solver is asked to find)
Tabs for antibodies that were not run on the cell line are removed. Everything else (styles, Solver setup,
instructions) is the original's: the workbook is edited at the XML level, not rebuilt.

    python calc_books.py SET_ID LAB_SETUP.xlsx OUT_DIR BEAD_EXPORT CALCULATOR.xlsx

OUT_DIR is the set's folder as left by run_set.py; the files go to OUT_DIR/abc_calculator/.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import xlrd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abc_calc  # noqa: E402
from replicas import n, num, replace_cell  # noqa: E402
from run_set import run  # noqa: E402

from qfacs.calc import BEAD_KEYS  # noqa: E402


def set_value(xml, ref, value):
    """Change a cell's stored number, keeping its style and formula."""
    pat = re.compile(rf'(<c r="{ref}"[^>]*>(?:<f[^>]*>[^<]*</f>)?<v>)[^<]*(</v>)')
    assert pat.search(xml), ref
    return pat.sub(lambda m: f"{m.group(1)}{n(value)!r}{m.group(2)}", xml, count=1)


def beads_sheet(xml, pe, gmfi, slope, intercept, r2):
    for i in range(4):
        xml = set_value(xml, f"B{4 + i}", pe[i])
        xml = set_value(xml, f"C{4 + i}", gmfi[i])
    for ref, v in (("B9", slope), ("B10", intercept), ("B11", r2)):
        xml = set_value(xml, ref, v)
    return xml


def antigen_sheet(xml, name, c, slope, selected):
    fit, conc, y = c["fit"], np.asarray(c["conc"], float), np.asarray(c["y"], float)
    assert len(conc) == 12, f"{name}: the calculator table holds 11 concentrations plus zero, got {len(conc)}"
    kd = fit.kd if np.isfinite(fit.kd) else 0.0
    pred = fit.bmax * conc / (kd + conc) + fit.ns * conc if kd + conc.min() > 0 else fit.ns * conc
    res2 = (y - pred) ** 2
    sse, dev = float(res2.sum()), float(((y - y.mean()) ** 2).sum())
    for ref, v in (("B4", fit.bmax), ("B5", kd), ("B6", fit.ns), ("B8", slope), ("B9", c["fp"]), ("B11", sse),
                   ("B14", fit.bmax / slope), ("B15", fit.bmax / slope / c["fp"])):
        xml = set_value(xml, ref, v)
    if dev > 0:
        xml = set_value(xml, "B12", 1 - sse / dev)
    else:           # every well at or below the unstained well: Excel's R squared formula divides by zero
        xml = replace_cell(xml, "B12", '<c r="B12" s="9" t="e"><f>1-SUM(D19:D30)/DEVSQ(B19:B30)</f><v>#DIV/0!</v></c>')
    for i in range(12):
        r = 19 + i
        row = (num(f"A{r}", n(conc[i]), 19) + num(f"B{r}", n(y[i]), 20)
               + num(f"C{r}", float(pred[i]), 21, f"$B$4*A{r}/($B$5+A{r})+$B$6*A{r}")
               + num(f"D{r}", float(res2[i]), 21, f"(B{r}-C{r})^2"))
        xml = re.sub(rf'(<row r="{r}"[^>]*>).*?(</row>)', lambda m: m.group(1) + row + m.group(2), xml, count=1, flags=re.S)
    title = f'<c r="A1" s="22" t="inlineStr"><is><t>{name}  -  total-binding fit</t></is></c>'
    xml = replace_cell(xml, "A1", title)                # the template's EGFR tab is still titled DLL3
    xml = xml.replace(' tabSelected="1"', "")
    if selected:
        xml = xml.replace("<sheetView ", '<sheetView tabSelected="1" ', 1)
    return xml


def write_book(template, out, bead, fits):
    """fits: {tab name: calc entry} for the antibodies run on this cell line."""
    with zipfile.ZipFile(template) as zin:
        wb = zin.read("xl/workbook.xml").decode()
        rels = zin.read("xl/_rels/workbook.xml.rels").decode()
        sheets = re.findall(r'<sheet name="([^"]*)" sheetId="\d+" r:id="(rId\d+)"/>', wb)
        target = dict(re.findall(r'<Relationship Id="(rId\d+)"[^>]*Target="(worksheets/[^"]*)"', rels))
        keep = [i for i, (name, _) in enumerate(sheets) if name in ("Instructions", "Beads") or name in fits]
        missing = set(fits) - {s[0] for s in sheets}
        assert not missing, f"no tab in the calculator for {missing}"
        dropped = {"xl/" + target[rid] for i, (_, rid) in enumerate(sheets) if i not in keep}
        first_antigen = next(sheets[i][0] for i in keep if sheets[i][0] in fits)

        # workbook.xml: sheet list, Solver names (renumbered to the remaining tabs), full recalculation on open
        for i, (name, rid) in enumerate(sheets):
            if i not in keep:
                wb = re.sub(rf'<sheet name="{re.escape(name)}"[^>]*/>', "", wb)
                rels = re.sub(rf'<Relationship Id="{rid}"[^>]*/>', "", rels)

        def rename(m):
            old = int(m.group(1))
            return f'localSheetId="{keep.index(old)}"' if old in keep else "DROP"
        wb = re.sub(r'localSheetId="(\d+)"', rename, wb)
        wb = re.sub(r"<definedName [^>]*DROP[^>]*>[^<]*</definedName>", "", wb)
        wb = re.sub(r'<calcPr calcId="(\d+)"/>', r'<calcPr calcId="\1" fullCalcOnLoad="1"/>', wb)
        rels = re.sub(r'<Relationship Id="rId\d+"[^>]*Target="calcChain.xml"/>', "", rels)
        names = [sheets[i][0] for i in keep]
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                fn = item.filename
                if fn == "xl/calcChain.xml" or fn in dropped:
                    continue
                data = zin.read(fn)
                if fn == "xl/workbook.xml":
                    data = wb.encode()
                elif fn == "xl/_rels/workbook.xml.rels":
                    data = rels.encode()
                elif fn == "[Content_Types].xml":
                    x = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", data.decode())
                    for d in dropped:
                        x = re.sub(rf'<Override PartName="/{re.escape(d)}"[^>]*/>', "", x)
                    data = x.encode()
                elif fn == "docProps/app.xml":
                    x = re.sub(r"<vt:i4>\d+</vt:i4>", f"<vt:i4>{len(names)}</vt:i4>", data.decode())
                    x = re.sub(r"<TitlesOfParts>.*?</TitlesOfParts>", '<TitlesOfParts><vt:vector size="%d" baseType="lpstr">%s</vt:vector></TitlesOfParts>'
                               % (len(names), "".join(f"<vt:lpstr>{s}</vt:lpstr>" for s in names)), x, flags=re.S)
                    data = x.encode()
                else:
                    for name, rid in sheets:
                        if fn != "xl/" + target[rid]:
                            continue
                        if name == "Beads":
                            data = beads_sheet(data.decode(), bead["pe"], bead["gmfi"], bead["slope"], bead["intercept"], bead["r2"]).encode()
                        elif name in fits:
                            data = antigen_sheet(data.decode(), name, fits[name], bead["slope"], name == first_antigen).encode()
                zout.writestr(item, data)


def highest_unstained(export):
    """Largest Live gMFI among the column-12 (no antibody) wells of a per cell line export."""
    sh = xlrd.open_workbook(str(export)).sheet_by_index(0)
    col = next(c for c in range(sh.ncols) if "Geometric Mean" in str(sh.cell_value(0, c)))
    vals = [sh.cell_value(r, col) for r in range(1, sh.nrows) if re.match(r"[A-H]12\b", str(sh.cell_value(r, 0)))]
    assert vals, f"{export}: no column-12 wells"
    return max(vals)


def main(set_id, lab_xlsx, out_dir, bead_export, template):
    d = run(set_id, lab_xlsx, out_dir, bead_export)
    curve = d["bead"]["curve"]
    bead = dict(pe=[curve.pe[k] for k in BEAD_KEYS], gmfi=[curve.gmfi[k] for k in BEAD_KEYS],
                slope=d["bead"]["slope"], intercept=d["bead"]["intercept"], r2=d["bead"]["r2"])
    plate = {x["cell_line"]: x["plate"] for x in d["layout"]}
    exports = {f.stem: f for f in d["exports"]}
    by_line = {}
    for (line, reagent), c in d["calc"].items():
        if c["isotype"]:
            continue
        top = highest_unstained(exports[f"Plate{plate[line]} {line}"])
        y = [max(r.gmfi - top, 0.0) for r in c["rows"]] + [0.0]
        fit = abc_calc.abc(abc_calc.fit_total_binding(c["conc"], y), bead["slope"], c["fp"])
        by_line.setdefault(line, {})[reagent] = dict(c, y=y, fit=fit, blank=top)
    folder = Path(out_dir) / "abc_calculator"
    folder.mkdir(parents=True, exist_ok=True)
    for line in sorted(by_line, key=lambda x: (plate[x], x.lower())):
        out = folder / f"QuantiBRITE_ABC_calculator Plate{plate[line]} {line}.xlsx"
        write_book(template, out, bead, by_line[line])
        print(f"{out.name}: " + "; ".join(f"{r} ABC {c['fit'].abc:,.0f} (Bmax {c['fit'].bmax:,.0f}, Kd {c['fit'].kd:.3g}, NS {c['fit'].ns:.3g}, F/P {c['fp']})"
                                           for r, c in by_line[line].items()))


if __name__ == "__main__":
    main(*sys.argv[1:6])
