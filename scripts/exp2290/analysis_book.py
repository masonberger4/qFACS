"""Write Exp2290_<set>_Analysis.xlsx: the layout of Mase's Exp2290_Analysis.xlsx (setup / Raw data / Calc Sheet),
plus both results: the qFACS engine and the QuantiBRITE ABC calculator (one calculator block per cell line)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import xlrd
from openpyxl import Workbook, load_workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.marker import Marker
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as L

from qfacs.calc import BEAD_KEYS
from qfacs.stats_io import well_of

HDR_FILL = PatternFill("solid", fgColor="2F5496")
HDR_FONT = Font(bold=True, color="FFFFFF")
YELLOW = PatternFill("solid", fgColor="FFFF00")
INPUT = PatternFill("solid", fgColor="FFF2CC")
GREEN = PatternFill("solid", fgColor="E2EFDA")
GREY = PatternFill("solid", fgColor="F2F2F2")
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=13)
WRAP = Alignment(wrap_text=True, vertical="top")
SETUP = "qFACS-setup"
CALC = "Calc Sheet"
SLOPE_CELL = f"'{SETUP}'!$E$24"
BEAD_NAMES = ("Low", "MedLow", "MedHigh", "High")
ENGINE_WEAK = ("not saturated", "poor fit", "Bmax imprecise", "Kd at search bound")
CALC_WEAK = ("Kd at the search limit", "poor fit", "non-specific term", "Kd ")


def short_notes(notes):
    """Collapse the engine's one-line-per-well 'not in the Layout' notes."""
    import re
    out, skipped = [], {}
    for n in notes:
        m = re.match(r"(\S+) ([A-H]\d\d) \((.*)\) is not in the Layout; ignored", n)
        if m:
            skipped.setdefault((m.group(1), m.group(3)), []).append(m.group(2))
        else:
            out.append(n)
    for (plate, src), ws_ in skipped.items():
        out.append(f"{plate} {ws_[0]}-{ws_[-1]} ({len(ws_)} wells, {src}) have no antibody on the plate map; not analysed")
    return out


def hdr(ws, row, labels, col=1):
    for i, t in enumerate(labels):
        c = ws.cell(row, col + i, t)
        c.fill, c.font, c.alignment = HDR_FILL, HDR_FONT, Alignment(wrap_text=True, vertical="center")


def widths(ws, ws_widths):
    for i, w in enumerate(ws_widths, 1):
        ws.column_dimensions[L(i)].width = w


def read_exports(d):
    """{(plate id, well): dict(sample, freqs, gmfi, count)} and the gate paths, from the per cell line exports."""
    out, paths = {}, None
    for f in d["exports"]:
        plate = f.name.split(" ")[0]
        sh = xlrd.open_workbook(str(f)).sheet_by_index(0)
        head = sh.row_values(0)
        paths = [h.split("|")[0].strip() for h in head[1:4]]
        for i in range(1, sh.nrows):
            v = sh.row_values(i)
            w = well_of(v[0])
            if w:
                out[(plate, w)] = dict(sample=v[0], freq=v[1:4], gmfi=v[4], count=v[5] if len(v) > 5 and v[5] != "" else None,
                                       file=f.name)
    return out, paths


def lab_antibodies(lab_xlsx):
    ws = load_workbook(lab_xlsx, data_only=True)["Design"]
    r0 = next(r for r in range(1, ws.max_row + 1) if str(ws.cell(r, 1).value or "").startswith("Antibody (all PE)"))
    rows = []
    for r in range(r0, r0 + 6):
        v = [ws.cell(r, c).value for c in range(1, 8)]
        if not v[0] or str(v[0]).startswith("Make"):
            break
        rows.append(v)
    return rows


def write_analysis(d):
    res, setup, calc, bead = d["res"], d["setup"], d["calc"], d["bead"]
    set_id, info = d["set_id"], d["info"]
    exp, paths = read_exports(d)
    wb = Workbook()
    ws_sum = wb.active
    ws_sum.title = "Summary"
    ws_set, ws_raw, ws_calc = wb.create_sheet(SETUP), wb.create_sheet("Raw data"), wb.create_sheet(CALC)

    # ------------------------------------------------------------------ wells in plate order
    wells = sorted(res.wells, key=lambda r: (int(r.well.plate_id[5:]), r.well.row, r.well.col))
    row_reagent = {(r.well.plate_id, r.well.row): r.well.reagent for r in wells if r.well.role == "titration"}
    calc_row = {(r.well.plate_id, r.well.well): i for i, r in enumerate(wells, 2)}
    iso_row = {}      # (plate, cell line) -> plate row letter of the isotype titration
    for r in wells:
        if r.well.role == "titration" and setup.reagent(r.well.reagent).get("is_isotype") == "Y":
            iso_row[(r.well.plate_id, r.well.cell_line)] = r.well.row

    # ------------------------------------------------------------------ Raw data (layout of Mase's 'Raw data')
    gate = paths[-1] if paths else "Live"
    hdr(ws_raw, 1, ["Stain", "Antigen", "Ab Concentration (ug/mL)", "Cell Line", "Sample"]
        + [f"{p} | Freq. of Parent" for p in (paths or ["Cells", "Single Cells", "Live"])]
        + [f"{gate} | Geometric Mean (B5 (575)-A)", "Plate", f"{gate} | Count"])
    for i, r in enumerate(wells, 2):
        w = r.well
        reagent = row_reagent.get((w.plate_id, w.row))
        iso = setup.reagent(reagent).get("is_isotype") == "Y"
        e = exp.get((w.plate_id, w.well), {})
        vals = ["Isotype" if iso else "Antigen", reagent, w.conc_ug_ml, w.cell_line, e.get("sample") or f"{w.well} (no data)"] \
            + list(e.get("freq", ["", "", ""])) + [e.get("gmfi"), int(w.plate_id[5:]), e.get("count")]
        for c, v in enumerate(vals, 1):
            ws_raw.cell(i, c, v)
    widths(ws_raw, [9, 9, 14, 12, 18, 14, 16, 18, 20, 7, 12])
    ws_raw.freeze_panes = "A2"
    ws_raw.row_dimensions[1].height = 45

    # ------------------------------------------------------------------ Calc Sheet (A-H as in Mase's 'Calc Sheet')
    hdr(ws_calc, 1, ["Plate#", "Stain", "Antigen", "Ab Concentration (ug/mL)", "Cell line", "Antigen (gMFI)",
                     "Antigen (unstain substracted)", "Antigen-IgG", "Well", "Calculator: PE molecules/cell (= G / bead slope)",
                     "Calculator: antibodies/cell (= J / F:P)", "F:P used", "Engine: PE/cell (log-log bead curve)",
                     "Engine: ABC (unstained subtracted)", "Engine: isotype ABC", "Engine: specific ABC", "Live events", "Flags"])
    for i, r in enumerate(wells, 2):
        w = r.well
        reagent = row_reagent.get((w.plate_id, w.row))
        rec = setup.reagent(reagent)
        iso = rec.get("is_isotype") == "Y"
        blank_r = calc_row.get((w.plate_id, f"{w.row}12"))
        ws_calc.cell(i, 1, int(w.plate_id[5:]))
        ws_calc.cell(i, 2, "Isotype" if iso else "Antigen")
        ws_calc.cell(i, 3, reagent)
        ws_calc.cell(i, 4, w.conc_ug_ml)
        ws_calc.cell(i, 5, w.cell_line)
        ws_calc.cell(i, 9, w.well)
        if r.gmfi is None:
            ws_calc.cell(i, 18, "no data")
            continue
        ws_calc.cell(i, 6, r.gmfi)
        ws_calc.cell(i, 7, f"=F{i}-$F${blank_r}")
        ir = iso_row.get((w.plate_id, w.cell_line))
        if not iso and ir and w.role == "titration" and (w.plate_id, f"{ir}{w.col:02d}") in calc_row:
            ws_calc.cell(i, 8, f"=F{i}-$F${calc_row[(w.plate_id, f'{ir}{w.col:02d}')]}")
        fp = rec.get("fp_ratio") or 1.0
        ws_calc.cell(i, 10, f"=G{i}/{SLOPE_CELL}").number_format = "#,##0"
        if not iso:
            ws_calc.cell(i, 11, f"=J{i}/L{i}").number_format = "#,##0"
            ws_calc.cell(i, 12, fp)
        for c, v in zip(range(13, 18), (r.pe, r.abc, r.iso_abc, r.specific, r.count)):
            if v is not None:
                ws_calc.cell(i, c, v).number_format = "#,##0"
        ws_calc.cell(i, 18, "; ".join(r.flags))
    widths(ws_calc, [7, 9, 9, 14, 12, 12, 14, 12, 7, 18, 18, 8, 16, 16, 14, 14, 10, 60])
    ws_calc.freeze_panes = "F2"
    ws_calc.row_dimensions[1].height = 60

    # ------------------------------------------------------------------ qFACS-setup (beads, regression, antibodies)
    ws = ws_set
    curve = bead["curve"]
    ws["A1"], ws["B1"], ws["D1"] = "DATE:", dt.date.fromisoformat(info["date"]), "Investigator:"
    ws["A2"] = f"qFACS Analysis  -  Exp2290 {set_id}"
    ws["A2"].font = TITLE
    ws["G2"], ws["H2"] = "Lot #", setup.beads[0]["kit_lot"]
    ws["A3"], ws["B3"] = "STEP 1", "Beads gMFI data from FlowJo"
    ws["C4"] = "Sample:"
    for j, n in enumerate(BEAD_NAMES):
        ws.cell(4, 4 + j, f"beads/{n} | Geometric Mean (B5 (575)-A)").alignment = WRAP
        c = ws.cell(5, 4 + j, round(curve.gmfi[BEAD_KEYS[j]], 1))
        c.fill = YELLOW
    ws["C5"] = bead["file"]
    ws["C6"] = info["bead_note"]
    ws["A8"], ws["B8"] = "STEP 2", "Lot info and the gMFI values"
    ws["E9"], ws["G9"] = "PE gMean", "PE molecules/Bead"
    for j, n in enumerate(("Low", "mid-low", "mid-high", "high")):
        ws.cell(10 + j, 3, n)
        ws.cell(10 + j, 5, f"={L(4 + j)}5")
        ws.cell(10 + j, 7, setup.beads[0][BEAD_KEYS[j]]).fill = YELLOW
    ws["A15"], ws["B15"] = "STEP 3", "Bead regression"
    hdr(ws, 16, ["X = PE molecules/Bead", "Y = PE gMFI", "log10 X", "log10 Y"], col=5)
    for j in range(4):
        r = 17 + j
        ws.cell(r, 5, f"=G{10 + j}")
        ws.cell(r, 6, f"=E{10 + j}")
        ws.cell(r, 7, f"=LOG10(E{r})")
        ws.cell(r, 8, f"=LOG10(F{r})")
    ws["A22"], ws["B22"] = "STEP 4", "Calibration used by each method"
    ws["C23"] = "ABC calculator: linear,  gMFI = m x PE + c   (only the slope m is used)"
    ws["C24"], ws["E24"] = "slope m (gMFI per PE molecule)", "=SLOPE(F17:F20,E17:E20)"
    ws["C25"], ws["E25"] = "intercept c", "=INTERCEPT(F17:F20,E17:E20)"
    ws["C26"], ws["E26"] = "R squared", "=RSQ(F17:F20,E17:E20)"
    ws["C27"] = "qFACS engine: log-log,  log10(gMFI) = slope x log10(PE) + intercept"
    ws["C28"], ws["E28"] = "slope", "=SLOPE(H17:H20,G17:G20)"
    ws["C29"], ws["E29"] = "intercept", "=INTERCEPT(H17:H20,G17:G20)"
    ws["C30"], ws["E30"] = "R squared", "=RSQ(H17:H20,G17:G20)"
    for r in (23, 27):
        ws.cell(r, 3).font = BOLD
    for r in (24, 28):
        ws.cell(r, 5).fill = GREEN
    for r in (24, 25, 28, 29):
        ws.cell(r, 5).number_format = "0.0000"
    for r in (26, 30):
        ws.cell(r, 5).number_format = "0.00000"
    ws["A32"], ws["B32"] = "STEP 5", "Antibodies bound per cell (ABC)"
    ws["C33"] = "ABC calculator:  Y(C) = Bmax·C/(Kd + C) + NS·C  on unstained-subtracted gMFI;  ABC = Bmax / m / (F:P).  No isotype."
    ws["C34"] = ("qFACS engine:  each gMFI -> PE/cell on the log-log curve; minus the unstained well; / (F:P); minus the isotype at the "
                 "same concentration;  specific ABC = Bmax·C/(Kd + C);  antigens/cell = Bmax.")
    ws["A36"] = "Antibodies (from the lab setup sheet)"
    ws["A36"].font = BOLD
    ab = lab_antibodies(d["lab_xlsx"])
    hdr(ws, 37, [str(x) for x in ab[0]] + ["F/P used", "Note"])
    for i, v in enumerate(ab[1:], 38):
        for c, x in enumerate(v, 1):
            ws.cell(i, c, x)
        rec = next((q for q in setup.reagents if (q.get("clone") or "") == v[1]), None)
        if rec:
            ws.cell(i, 8, rec.get("fp_ratio") or ("-" if rec.get("is_isotype") == "Y" else 1)).fill = INPUT
            ws.cell(i, 9, rec.get("notes"))
    r = 38 + len(ab)
    ws.cell(r, 1, "Data").font = BOLD
    ws.cell(r + 1, 1, info["data_note"])
    ws.cell(r + 2, 1, f"Lab setup sheet: {Path(d['lab_xlsx']).name.split('-', 1)[-1]}, sheet '{info['sheet']}'.")
    for i in (3, 8, 15, 22, 32):
        ws.cell(i, 1).font = ws.cell(i, 2).font = BOLD
    widths(ws, [22, 12, 30, 16, 20, 16, 18, 14, 60])
    ws.row_dimensions[4].height = 45
    ch = ScatterChart()
    ch.title = "Quantibrite PE beads"
    ch.x_axis.title, ch.y_axis.title = "PE molecules/bead", "PE gMFI"
    ch.x_axis.delete = ch.y_axis.delete = False
    s = Series(Reference(ws, min_col=6, min_row=17, max_row=20), Reference(ws, min_col=5, min_row=17, max_row=20), title="beads")
    s.marker = Marker("circle", size=7)
    s.graphicalProperties.line.solidFill = "2F5496"
    ch.series.append(s)
    ch.height, ch.width = 8, 13
    ws.add_chart(ch, "J3")

    # ------------------------------------------------------------------ calculator blocks, one sheet per antibody
    abc_cell = {}     # (cell line, reagent) -> sheet!cell of the calculator ABC, Kd, NS, R2
    reagents = [q["name"] for q in setup.reagents if q.get("is_isotype") != "Y"]
    lines = [c["cell_line"] for c in setup.cell_lines]
    for reagent in reagents:
        keys = [(ln, reagent) for ln in lines if (ln, reagent) in calc]
        if not keys:
            continue
        wsc = wb.create_sheet(f"ABC calc {reagent}")
        wsc.sheet_view.zoomScale = 85
        for b, key in enumerate(keys):
            c0 = 1 + 6 * b
            A, B, C, D = L(c0), L(c0 + 1), L(c0 + 2), L(c0 + 3)
            x = calc[key]
            f = x["fit"]
            wsc.cell(1, c0, f"{key[0]}  ·  {reagent}  -  total-binding fit").font = TITLE
            wsc.cell(2, c0, "ND: " + "; ".join(f.flags) if f.nd else "; ".join(f.flags)).font = Font(italic=True, color="C00000")
            wsc.cell(3, c0, f"Fitted parameters  (Solver changes {B}4:{B}6)").font = BOLD
            for r, (lab, val, fmt) in enumerate((("Bmax  (gMFI)", f.bmax, "#,##0.0"), ("Kd  (ug/mL)", f.kd, "0.0000"),
                                                 ("NS  (gMFI per ug/mL)", f.ns, "0.0000")), 4):
                wsc.cell(r, c0, lab)
                c = wsc.cell(r, c0 + 1, val)
                c.fill, c.number_format = YELLOW, fmt
            wsc.cell(8, c0, "Bead slope  m  (qFACS-setup)")
            c = wsc.cell(8, c0 + 1, f"={SLOPE_CELL}")
            c.number_format, c.font = "0.0000", Font(color="008000")
            wsc.cell(9, c0, "F/P ratio  (fluorophores per Ab)")
            c = wsc.cell(9, c0 + 1, x["fp"])
            c.fill, c.font, c.number_format = INPUT, Font(color="0000FF"), "0.000"
            wsc.cell(11, c0, "SSE  (Solver objective -> Min)")
            wsc.cell(11, c0 + 1, f"=SUM({D}19:{D}30)").number_format = "#,##0"
            wsc.cell(12, c0, "R squared")
            wsc.cell(12, c0 + 1, f"=1-SUM({D}19:{D}30)/DEVSQ({B}19:{B}30)").number_format = "0.0000"
            wsc.cell(14, c0, "Specific Bmax  (PE molecules/cell)")
            wsc.cell(14, c0 + 1, f"={B}4/{B}8").number_format = "#,##0"
            wsc.cell(15, c0, "ABC  (antibodies bound per cell)")
            c = wsc.cell(15, c0 + 1, f"={B}4/{B}8/{B}9")
            c.number_format, c.fill, c.font = "#,##0", GREEN, BOLD
            wsc.cell(16, c0, f"Solver: Set {B}11 to Min, changing {B}4:{B}6, all >= 0, GRG Nonlinear").font = Font(italic=True, size=9)
            hdr(wsc, 18, ["Conc (ug/mL)", "Observed gMFI", "Predicted", "Residual^2"], col=c0)
            for k, rr in enumerate(x["rows"]):
                r = 19 + k
                wsc.cell(r, c0, rr.well.conc_ug_ml).number_format = "0.000"
                wsc.cell(r, c0 + 1, f"='{CALC}'!G{calc_row[(rr.well.plate_id, rr.well.well)]}").number_format = "#,##0"
            r_blank = 19 + len(x["rows"])
            wsc.cell(r_blank, c0, 0)
            wsc.cell(r_blank, c0 + 1, 0)
            for r in range(19, r_blank + 1):
                wsc.cell(r, c0 + 2, f"=${B}$4*{A}{r}/(${B}$5+{A}{r})+${B}$6*{A}{r}").number_format = "#,##0"
                wsc.cell(r, c0 + 3, f"=({B}{r}-{C}{r})^2").number_format = "#,##0"
            ch = ScatterChart()
            ch.title = f"{key[0]} · {reagent}"
            ch.x_axis.title, ch.y_axis.title = "µg/mL", "gMFI - unstained"
            ch.x_axis.scaling.logBase = 10
            ch.x_axis.delete = ch.y_axis.delete = False
            n = len(x["rows"])
            s = Series(Reference(wsc, min_col=c0 + 1, min_row=19, max_row=18 + n), Reference(wsc, min_col=c0, min_row=19, max_row=18 + n),
                       title="observed")
            s.marker = Marker("circle", size=6)
            s.marker.graphicalProperties = GraphicalProperties(solidFill="1F3864")
            s.graphicalProperties.line.noFill = True
            ch.series.append(s)
            s = Series(Reference(wsc, min_col=c0 + 2, min_row=19, max_row=18 + n), Reference(wsc, min_col=c0, min_row=19, max_row=18 + n),
                       title="fit")
            s.marker = Marker("none")
            s.smooth = True
            s.graphicalProperties.line.solidFill = "C00000"
            ch.series.append(s)
            ch.height, ch.width = 7.5, 13.5
            wsc.add_chart(ch, f"{A}33")
            wsc.column_dimensions[A].width = 33
            for col in (B, C, D):
                wsc.column_dimensions[col].width = 13
            wsc.column_dimensions[L(c0 + 4)].width = 3
            wsc.column_dimensions[L(c0 + 5)].width = 3
            abc_cell[key] = (wsc.title, B)

    # ------------------------------------------------------------------ Summary
    ws = ws_sum
    ws["A1"] = f"Exp2290 {set_id}: antigens per cell by both methods"
    ws["A1"].font = TITLE
    ws["A2"] = ("Method 1 = qFACS engine (log-log bead curve, unstained and isotype subtracted, one-site fit).  "
                "Method 2 = QuantiBRITE ABC calculator (linear bead slope, unstained subtracted, Bmax·C/(Kd+C) + NS·C fit, no isotype).")
    ws["A3"] = info["data_note"] + "  Beads: " + info["bead_note"]
    hdr(ws, 5, ["Cell line", "Plate", "Antibody", "F/P used", "Engine: antigens/cell", "Engine: Kd (µg/mL)", "Engine: R²",
                "Engine NS-fit cross-check (antigens/cell)", "Calculator: ABC", "Calculator: Kd (µg/mL)",
                "Calculator: NS (gMFI per µg/mL)", "Calculator: R²", "Calculator vs engine", "Engine flags", "Calculator flags"])
    ws.row_dimensions[5].height = 48
    fits = sorted(res.fits, key=lambda f: (int(f.plates[0][5:]), lines.index(f.cell_line), reagents.index(f.reagent)))
    for i, f in enumerate(fits, 6):
        key = (f.cell_line, f.reagent)
        x = calc.get(key)
        ws.cell(i, 1, f.cell_line)
        ws.cell(i, 2, ", ".join(p[5:] for p in f.plates))
        ws.cell(i, 3, f.reagent)
        ws.cell(i, 4, f.reagent_rec.get("fp_ratio") or 1)
        eng = None
        if not f.points:
            ws.cell(i, 5, "no data")
        elif f.status == "ND":
            ws.cell(i, 5, "ND")
        elif f.antigens is not None:
            eng = f.antigens
            ws.cell(i, 5, round(eng)).number_format = "#,##0"
            ws.cell(i, 6, f.fit.kd).number_format = "0.00"
            ws.cell(i, 7, f.fit.r2).number_format = "0.000"
        else:
            ws.cell(i, 5, "no data")
        if f.cross_antigens is not None:
            ws.cell(i, 8, round(f.cross_antigens)).number_format = "#,##0"
        elif f.cross is not None and f.cross.nd:
            ws.cell(i, 8, "ND")
        if x:
            sheet, B = abc_cell[key]
            cf = x["fit"]
            if cf.nd:
                ws.cell(i, 9, "ND")
            else:
                ws.cell(i, 9, f"=ROUND('{sheet}'!{B}15,0)").number_format = "#,##0"
                ws.cell(i, 10, f"='{sheet}'!{B}5").number_format = "0.00"
                if eng:
                    ws.cell(i, 13, f"=I{i}/E{i}-1").number_format = "+0%;-0%;0%"
            ws.cell(i, 11, f"='{sheet}'!{B}6").number_format = "0.0"
            ws.cell(i, 12, f"='{sheet}'!{B}12").number_format = "0.000"
            ws.cell(i, 15, "; ".join(cf.flags))
        else:
            ws.cell(i, 9, "no data")
        ws.cell(i, 14, "; ".join(f.flags))
        ws.cell(i, 5).font = Font(bold=True, color="C00000" if any(q.startswith(ENGINE_WEAK) for q in f.flags) else "000000")
        ws.cell(i, 9).font = Font(bold=True, color="C00000" if x and any(q.startswith(CALC_WEAK) for q in x["fit"].flags) else "000000")
        for c in (5, 8, 9):
            ws.cell(i, c).alignment = Alignment(horizontal="right")
        if (lines.index(f.cell_line) % 2) == 1:
            for c in range(1, 16):
                ws.cell(i, c).fill = GREY
    r = 7 + len(fits)
    notes = ["Notes",
             "ND = not detected: no specific binding above the isotype (engine), or no saturable binding in the fit (calculator).",
             "Red number = that fit is flagged (not saturated, poor fit, Kd outside the tested range, mostly non-specific): read the flags before using it.",
             "Engine NS-fit cross-check: the engine's own Bmax·C/(Kd+C) + NS·C fit on ABC values (log-log bead curve), no isotype.",
             "Calculator blocks ('ABC calc ...' sheets) are live: observed gMFI links to the Calc Sheet, and Solver can be re-run on any block.",
             "Unstained subtraction uses the no-antibody well (column 12) of the same plate row, for both methods.",
             f"Full engine output (plots, per-well formulas, method): Exp2290_{set_id}_qFACS_results.xlsx."]
    notes += ["Engine warning: " + i.message for i in res.issues] + ["Engine note: " + n for n in short_notes(res.notes)]
    for k, t in enumerate(notes):
        ws.cell(r + k, 1, t)
    ws.cell(r, 1).font = BOLD
    widths(ws, [12, 6, 9, 7, 13, 11, 8, 15, 13, 11, 12, 10, 11, 70, 70])
    ws.freeze_panes = "D6"

    # ------------------------------------------------------------------ Engine fits
    ws = wb.create_sheet("Engine fits", 4)
    hdr(ws, 1, ["Cell line", "Antibody", "Plate(s)", "Model", "Status", "Antigens/cell", "Bmax 95% CI low", "Bmax 95% CI high",
                "Kd (µg/mL)", "Kd (nM)", "R²", "Top conc (µg/mL)", "Specific ABC at top conc", "Saturation",
                "NS-fit cross-check: antigens/cell", "NS-fit: Kd (µg/mL)", "NS-fit: NS (ABC per µg/mL)", "Flags"])
    for i, f in enumerate(fits, 2):
        ft = f.fit
        ci = ft.bmax_ci or (None, None)
        cr = f.cross
        vals = [f.cell_line, f.reagent, ", ".join(f.plates), f.model, f.status, f.antigens, ci[0], ci[1],
                ft.kd if f.antigens is not None else None, f.kd_nm, ft.r2 if f.antigens is not None else None, f.top_conc, f.top_specific,
                f.saturation, f.cross_antigens, cr.kd if cr and f.cross_antigens is not None else None,
                cr.ns if cr and f.cross_antigens is not None else None, "; ".join(f.flags)]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(i, c, v)
            if isinstance(v, float):
                cell.number_format = "0.00" if c in (9, 10, 11, 12, 16) else "#,##0"
    widths(ws, [12, 9, 9, 9, 9, 13, 13, 13, 10, 9, 7, 9, 13, 30, 14, 10, 12, 90])
    ws.row_dimensions[1].height = 48
    ws.freeze_panes = "C2"

    out = d["out_dir"] / f"Exp2290_{set_id}_Analysis.xlsx"
    wb.save(out)
    recalc(out)
    return out


def recalc(path):
    """Open and re-save with LibreOffice (when installed) so every formula carries its calculated value:
    openpyxl writes formulas without values, which previews and pandas show as blanks."""
    import shutil
    import subprocess
    import tempfile
    soffice = shutil.which("soffice")
    if not soffice:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([soffice, "--headless", "--calc", "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", tmp, str(path)],
                       capture_output=True, timeout=300)
        new = Path(tmp) / Path(path).name
        if not new.exists():
            return False
        shutil.copy(new, path)
    return True
