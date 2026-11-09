"""Write the per-experiment results workbook."""
from __future__ import annotations

import datetime as dt
import math

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.marker import Marker
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import __version__
from .analysis import Results
from .template import BOX, HDR_FILL, HDR_FONT, TITLE_FONT

RED = PatternFill("solid", fgColor="FFC7CE")
GRN = PatternFill("solid", fgColor="C6EFCE")
WARN = Font(bold=True, color="C00000")


def sig3(v):
    if v is None or v == 0:
        return v
    return round(v, 2 - int(math.floor(math.log10(abs(v)))))


def _hdr(ws, row, labels, widths=None):
    for j, lab in enumerate(labels, 1):
        c = ws.cell(row, j, lab)
        c.fill, c.font, c.border = HDR_FILL, HDR_FONT, BOX
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[row].height = 32
    for j, w in enumerate(widths or [], 1):
        ws.column_dimensions[get_column_letter(j)].width = w


def _flagtext(flags):
    return "; ".join(dict.fromkeys(flags)) or "OK"


def write_results(res: Results, path):
    wb = Workbook()
    _summary(wb.active, res)
    _fits(wb.create_sheet("Fits"), res)
    _wells(wb.create_sheet("Wells"), res)
    _beads(wb.create_sheet("Beads"), res)
    _plots(wb, res)
    _issues(wb.create_sheet("Issues"), res)
    wb.save(path)
    return path


def _summary(ws, res: Results):
    ws.title = "Summary"
    exp = res.setup.experiment
    ws["A1"] = f"Antigens per cell: {exp.get('experiment_id') or ''}"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Antigens/cell = one-site fit Bmax × valency (3 significant figures). ND = no specific binding above isotype. "
                "Flags are QC notes; no values were excluded.")
    ws["A2"].font = Font(italic=True, color="808080")
    r = 3
    lots = {b.get("bead_run"): b.get("kit_lot") for b in res.setup.beads}
    for run, c in res.beads.items():
        ws.cell(r, 1, f"Bead run {run} (lot {lots.get(run) or '?'}): {c.qc}, slope {c.slope:.4f}, R² {c.r2:.5f}")
        if c.qc != "PASS":
            ws.cell(r, 1).font = WARN
        r += 1
    if exp.get("fixed_after_staining") == "Y":
        ws.cell(r, 1, "Cells fixed after staining: BD lists fixation as a factor that can affect quantitation.").font = WARN
        r += 1
    errors = [i for i in res.issues if i.level == "error"]
    if errors:
        ws.cell(r, 1, f"{len(errors)} setup/data error(s): see the Issues sheet. No results were calculated.").font = WARN
        return
    r += 1
    lines = list(dict.fromkeys(f.cell_line for f in res.fits))
    abs_ = list(dict.fromkeys(f.reagent for f in res.fits))
    by = {(f.cell_line, f.reagent): f for f in res.fits}
    na = len(abs_)
    ws.cell(r, 1, "Antigens per cell").font = Font(bold=True, size=12)
    ws.cell(r, na + 3, "Flags").font = Font(bold=True, size=12)
    r += 1
    _hdr(ws, r, ["Cell line"] + abs_)
    for j, a in enumerate(["Cell line"] + abs_, na + 3):
        c = ws.cell(r, j, a)
        c.fill, c.font, c.border = HDR_FILL, HDR_FONT, BOX
    first = r + 1
    for i, line in enumerate(lines):
        rr = first + i
        ws.cell(rr, 1, line).font = Font(bold=True)
        ws.cell(rr, na + 3, line).font = Font(bold=True)
        for j, a in enumerate(abs_, 2):
            f = by.get((line, a))
            v = "" if f is None else ("ND" if f.status == "ND" else sig3(f.antigens) if f.antigens is not None else "not fitted")
            c = ws.cell(rr, j, v)
            c.number_format, c.border = "#,##0", BOX
            c.alignment = Alignment(horizontal="right")
            fc = ws.cell(rr, j + na + 1, "" if f is None else _flagtext(f.flags))
            fc.border = BOX
            fc.alignment = Alignment(wrap_text=True, vertical="top")
    last = first + len(lines) - 1
    rng = f"{get_column_letter(na + 4)}{first}:{get_column_letter(2 * na + 3)}{last}"
    tl = f"{get_column_letter(na + 4)}{first}"
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{tl}="OK"'], fill=GRN))
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND({tl}<>"OK",{tl}<>"")'], fill=RED))
    ws.column_dimensions["A"].width = 16
    for j in range(2, na + 2):
        ws.column_dimensions[get_column_letter(j)].width = 13
    ws.column_dimensions[get_column_letter(na + 2)].width = 3
    ws.column_dimensions[get_column_letter(na + 3)].width = 16
    for j in range(na + 4, 2 * na + 4):
        ws.column_dimensions[get_column_letter(j)].width = 36
    ws.cell(last + 2, 1, f"qfacs {__version__}, {dt.datetime.now():%Y-%m-%d %H:%M}, setup: {res.setup.source}").font = Font(color="808080")


def _fits(ws, res: Results):
    cols = ["Cell line", "Antibody", "Target", "Clone", "Catalog #", "Lot #", "F/P", "Valency", "Plates", "n points",
            "Antigens/cell", "Bmax (ABC)", "Bmax 95% CI low", "Bmax 95% CI high", "Kd (µg/mL)", "Kd 95% CI low",
            "Kd 95% CI high", "Kd (nM)", "R²", "Top conc (µg/mL)", "Top conc / Kd", "Specific ABC at top conc",
            "Saturation", "Status", "Flags"]
    _hdr(ws, 1, cols, [12, 11, 14, 10, 12, 10, 7, 8, 9, 7, 12, 12, 12, 12, 10, 10, 10, 9, 8, 10, 9, 12, 30, 10, 60])
    for i, f in enumerate(res.fits, 2):
        g = f.reagent_rec
        fit = f.fit
        nd = f.status == "ND"
        vals = [f.cell_line, f.reagent, g.get("target"), g.get("clone"), g.get("catalog"), g.get("lot"),
                g.get("fp_ratio") or ("1 (assumed)" if g.get("is_isotype") != "Y" else None),
                g.get("valency") or 1, ", ".join(f.plates), len(f.points),
                "ND" if nd else sig3(f.antigens), None if nd else fit.bmax,
                None if nd or not fit.bmax_ci else fit.bmax_ci[0], None if nd or not fit.bmax_ci else fit.bmax_ci[1],
                None if nd else fit.kd, None if nd or not fit.kd_ci else fit.kd_ci[0],
                None if nd or not fit.kd_ci else fit.kd_ci[1], None if nd else f.kd_nm, None if nd else fit.r2,
                f.top_conc, None if nd or not fit.kd else f.top_conc / fit.kd, f.top_specific, f.saturation, f.status,
                _flagtext(f.flags)]
        for j, v in enumerate(vals, 1):
            c = ws.cell(i, j, v)
            c.border = BOX
            if j in (12, 13, 14, 22):
                c.number_format = "#,##0"
            elif j in (11,):
                c.number_format = "#,##0"
            elif j in (15, 16, 17, 18, 20, 21):
                c.number_format = "0.000"
            elif j == 19:
                c.number_format = "0.0000"
    ws.freeze_panes = "C2"


def _wells(ws, res: Results):
    cols = ["Plate", "Well", "Cell line", "Reagent", "Conc (µg/mL)", "Role", "Point", "Sample", "Source file",
            "Live events", "PE gMFI", "PE/cell", "No-antibody PE/cell", "ABC", "Isotype ABC", "Specific ABC", "Flags"]
    _hdr(ws, 1, cols, [8, 6, 12, 10, 10, 9, 6, 18, 20, 9, 11, 11, 11, 11, 11, 11, 50])
    for i, r in enumerate(res.wells, 2):
        w = r.well
        vals = [w.plate_id, w.well, w.cell_line, w.reagent or "", w.conc_ug_ml, w.role, w.point, r.sample, r.source,
                r.count, r.gmfi, r.pe, r.blank_pe, r.abc, r.iso_abc, r.specific, _flagtext(r.flags)]
        for j, v in enumerate(vals, 1):
            c = ws.cell(i, j, v)
            if j == 5:
                c.number_format = "0.000"
            elif 10 <= j <= 16:
                c.number_format = "#,##0"
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:Q{len(res.wells) + 1}"


def _beads(ws, res: Results):
    cols = ["Bead run", "Source file", "Level", "PE/bead (lot)", "gMFI", "log10 PE", "log10 gMFI", "Back-calc. PE/bead",
            "% recovery", "Slope", "Intercept", "R²", "QC"]
    _hdr(ws, 1, cols, [9, 22, 10, 12, 10, 9, 9, 13, 10, 9, 9, 9, 40])
    r = 2
    from .calc import BEAD_KEYS, BEAD_LABELS
    for run, c in res.beads.items():
        for k in BEAD_KEYS:
            vals = [run, c.source, BEAD_LABELS[k], c.pe[k], c.gmfi[k], math.log10(c.pe[k]), math.log10(c.gmfi[k]),
                    c.pe_per_cell(c.gmfi[k]), c.recovery[k], c.slope, c.intercept, c.r2, c.qc]
            for j, v in enumerate(vals, 1):
                cell = ws.cell(r, j, v)
                cell.number_format = {4: "#,##0", 5: "#,##0", 8: "#,##0", 9: "0.0%", 12: "0.00000"}.get(j, "0.0000" if j in (6, 7, 10, 11) else "General")
            r += 1
    ws.cell(r + 1, 1, "Curve: log10(gMFI) = slope × log10(PE/bead) + intercept;  PE/cell = 10^((log10 gMFI − intercept) / slope).")


def _plots(wb, res: Results):
    if not res.fits:
        return
    data = wb.create_sheet("Plot_Data")
    ws = wb.create_sheet("Plots", 1)
    ws["A1"] = "Specific ABC vs antibody concentration, with the one-site fit (log concentration axis)"
    ws["A1"].font = TITLE_FONT
    for i, f in enumerate(res.fits):
        c0 = 1 + 4 * i
        data.cell(1, c0, f"{f.cell_line} {f.reagent}")
        for j, lab in enumerate(["conc", "specific ABC", "fit conc", "fit"]):
            data.cell(2, c0 + j, lab)
        for k, (x, y) in enumerate(f.points):
            data.cell(3 + k, c0, x)
            data.cell(3 + k, c0 + 1, y)
        n_fit = 0
        if f.antigens is not None and f.points:
            xs = [p[0] for p in f.points]
            lo, hi = math.log10(min(xs) / 1.5), math.log10(max(xs) * 1.5)
            for k in range(40):
                x = 10 ** (lo + (hi - lo) * k / 39)
                data.cell(3 + k, c0 + 2, x)
                data.cell(3 + k, c0 + 3, f.fit.bmax * x / (f.fit.kd + x))
            n_fit = 40
        ch = ScatterChart()
        ch.title = f"{f.cell_line} · {f.reagent}" + (" (ND)" if f.status == "ND" else "")
        ch.x_axis.title, ch.y_axis.title = "µg/mL", "Specific ABC"
        ch.x_axis.scaling.logBase = 10
        ch.x_axis.delete = ch.y_axis.delete = False
        n = len(f.points)
        if n:
            s = Series(Reference(data, min_col=c0 + 1, min_row=3, max_row=2 + n), Reference(data, min_col=c0, min_row=3, max_row=2 + n),
                       title="data")
            s.marker = Marker("circle", size=6)
            s.marker.graphicalProperties = GraphicalProperties(solidFill="1F3864")
            s.marker.graphicalProperties.line.solidFill = "1F3864"
            s.graphicalProperties.line.noFill = True
            ch.series.append(s)
        if n_fit:
            s = Series(Reference(data, min_col=c0 + 3, min_row=3, max_row=2 + n_fit),
                       Reference(data, min_col=c0 + 2, min_row=3, max_row=2 + n_fit), title="fit")
            s.marker = Marker("none")
            s.smooth = True
            s.graphicalProperties.line.solidFill = "C00000"
            s.graphicalProperties.line.width = 19050
            ch.series.append(s)
        ch.height, ch.width = 7, 11
        ws.add_chart(ch, f"{get_column_letter(1 + 8 * (i % 3))}{3 + 15 * (i // 3)}")
    data.sheet_state = "hidden"


def _issues(ws, res: Results):
    _hdr(ws, 1, ["Level", "Where", "Row", "Message"], [9, 12, 6, 120])
    r = 2
    for i in sorted(res.issues, key=lambda i: (i.level != "error", i.sheet, i.row or 0)):
        ws.cell(r, 1, i.level)
        ws.cell(r, 2, i.sheet)
        ws.cell(r, 3, i.row)
        ws.cell(r, 4, i.message)
        if i.level == "error":
            ws.cell(r, 1).font = WARN
        r += 1
    for n in res.notes:
        ws.cell(r, 1, "note")
        ws.cell(r, 2, "Data")
        ws.cell(r, 4, n)
        r += 1
