"""Write the per-experiment results workbook."""
from __future__ import annotations

import datetime as dt
import math

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.layout import Layout, ManualLayout
from openpyxl.chart.marker import Marker
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.text import RichText
from openpyxl.drawing.line import LineProperties
from openpyxl.drawing.text import CharacterProperties, Paragraph, ParagraphProperties
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
    _method(wb.create_sheet("Method"), res)
    _fits(wb.create_sheet("Fits"), res)
    _wells(wb.create_sheet("Wells"), res)
    _beads(wb.create_sheet("Beads"), res)
    _data_files(wb.create_sheet("Data files"), res)
    _plots(wb, res)
    _issues(wb.create_sheet("Issues"), res)
    wb.save(path)
    return path


def _summary(ws, res: Results):
    ws.title = "Summary"
    exp = res.setup.experiment
    ws["A1"] = f"Antigens per cell: {exp.get('experiment_id') or ''}"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Antigens/cell = fitted Bmax × valency (3 significant figures), by both methods. Isotype subtracted: "
                "one-site fit after subtracting the matched isotype. NS fit: total-binding fit Bmax·C/(Kd+C) + NS·C, no "
                "isotype. Details on Fits and Method. ND = no specific binding. Flags are QC notes; no values were excluded.")
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
    pairs = res.by_pair
    na = len(abs_)

    def table(r, title, cell, fmt="#,##0", flag=None):
        """One cell line x antibody table at row r (values from cell(pair)), flags to its right. Returns the next row."""
        ws.cell(r, 1, title).font = Font(bold=True, size=12)
        if flag:
            ws.cell(r, na + 3, "Flags").font = Font(bold=True, size=12)
        r += 1
        _hdr(ws, r, ["Cell line"] + abs_)
        first = r + 1
        if flag:
            for j, a in enumerate(["Cell line"] + abs_, na + 3):
                c = ws.cell(r, j, a)
                c.fill, c.font, c.border = HDR_FILL, HDR_FONT, BOX
        for i, line in enumerate(lines):
            rr = first + i
            ws.cell(rr, 1, line).font = Font(bold=True)
            if flag:
                ws.cell(rr, na + 3, line).font = Font(bold=True)
            for j, a in enumerate(abs_, 2):
                pair = pairs.get((line, a))
                c = ws.cell(rr, j, "" if pair is None else cell(pair))
                c.number_format, c.border = fmt, BOX
                c.alignment = Alignment(horizontal="right")
                if flag:
                    fc = ws.cell(rr, j + na + 1, "" if pair is None else flag(pair))
                    fc.border = BOX
                    fc.alignment = Alignment(wrap_text=True, vertical="top")
        last = first + len(lines) - 1
        if flag:
            rng = f"{get_column_letter(na + 4)}{first}:{get_column_letter(2 * na + 3)}{last}"
            tl = f"{get_column_letter(na + 4)}{first}"
            ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{tl}="OK"'], fill=GRN))
            ws.conditional_formatting.add(rng, FormulaRule(formula=[f'AND({tl}<>"OK",{tl}<>"")'], fill=RED))
        return last + 2

    def value(model):
        def cell(pair):
            f = pair.get(model)
            if f is None:
                return "no isotype"
            return "ND" if f.status == "ND" else sig3(f.antigens) if f.antigens is not None else "not fitted"
        return cell

    def flags(model):
        return lambda pair: _flagtext(pair[model].flags) if model in pair else "no isotype data: see NS fit"

    def ratio(pair):
        f = pair.get("NS")
        return round(f.ns_vs_iso, 2) if f and f.ns_vs_iso is not None else "-"

    r = table(r, "Antigens per cell: isotype subtracted", value("Isotype"), flag=flags("Isotype"))
    r = table(r, "Antigens per cell: NS fit (no isotype subtraction)", value("NS"), flag=flags("NS"))
    r = table(r, "NS fit ÷ isotype subtracted", ratio, fmt="0.00")
    ws.column_dimensions["A"].width = 16
    for j in range(2, na + 2):
        ws.column_dimensions[get_column_letter(j)].width = 13
    ws.column_dimensions[get_column_letter(na + 2)].width = 3
    ws.column_dimensions[get_column_letter(na + 3)].width = 16
    for j in range(na + 4, 2 * na + 4):
        ws.column_dimensions[get_column_letter(j)].width = 36
    ws.cell(r, 1, f"qfacs {__version__}, {dt.datetime.now():%Y-%m-%d %H:%M}, setup: {res.setup.source}").font = Font(color="808080")


def _method(ws, res: Results):
    """Plain-language description of every calculation step, pointing to the sheet and columns that hold it."""
    from .analysis import CROSS_TOL, NS_SHARE_MAX
    st = res.settings
    no_iso = sorted({f.reagent for f in res.fits if f.model == "NS" and f.cross is None})
    H = Font(bold=True, size=12, color="1F3864")
    lines = [
        ("How antigens per cell are calculated", TITLE_FONT),
        ("Each step names the sheet and columns where its numbers are. Nothing is excluded automatically: QC problems "
         "become flags.", None),
        ("", None),
        ("1. Bead curve (Beads sheet)", H),
        ("The four Quantibrite PE bead peaks (gMFI, column E) are matched to the lot's PE molecules per bead (column D).", None),
        ("A straight line is fitted on log scales: log10(gMFI) = slope × log10(PE/bead) + intercept (columns J, K).", None),
        (f"QC: R² (column L) must be at least {st['bead_r2_min']:g}, and each bead must back-calculate to 80-120 % of its "
         "lot value (column I). Otherwise every result on that plate is flagged.", None),
        ("", None),
        ("2. PE molecules per cell (Wells sheet)", H),
        ("PE gMFI of the live gate (column K) is converted with the bead curve: PE/cell = 10^((log10 gMFI − intercept) / "
         "slope) (column L).", None),
        (f"Wells with fewer than {st['min_live_events']:g} live events (column J) are flagged; gMFI outside the bead range "
         "is flagged as extrapolated.", None),
        ("", None),
        ("3. Background (Wells sheet)", H),
        ("The no-antibody wells (cells + buffer) of the same plate row are averaged (column M) and subtracted: "
         "Net PE/cell = PE/cell − no-antibody PE/cell (column R). This removes autofluorescence.", None),
        ("", None),
        ("4. Antibodies bound per cell, ABC (Wells sheet)", H),
        ("ABC = Net PE/cell ÷ F/P (column N), where F/P = PE molecules per antibody from the Reagents sheet (column S). "
         "A blank F/P is taken as 1 and flagged.", None),
        ("", None),
        ("5. Non-specific binding: two methods, both reported for every antibody (Fits sheet, column Fit model)", H),
        ("Isotype subtracted:", Font(bold=True)),
        ("   The matched isotype's ABC at the same concentration (column O; interpolated on log concentration when "
         "concentrations differ) is subtracted: Specific ABC = ABC − isotype ABC (column P).", None),
        ("   Then the one-site fit: Specific ABC = Bmax × C / (Kd + C).", None),
        ("NS fit:", Font(bold=True)),
        ("   No isotype is subtracted. Total binding (ABC, column N) is fitted instead: "
         "ABC = Bmax × C / (Kd + C) + NS × C, with Bmax, Kd and NS all ≥ 0.", None),
        ("   NS × C is the non-specific signal, which rises linearly with antibody concentration. This needs top doses "
         "well past saturation (ideally ≥ 10 × Kd).", None),
        ("The two are never combined: subtracting the isotype and also fitting NS would remove the background twice.", None),
        ("A blank 'Matched isotype' uses the only isotype control run on that cell line, and says so in the flags.", None),
        ("An antibody with no isotype to use, or whose isotype has no data, gets the NS fit only and is flagged"
         + (f" (here: {', '.join(no_iso)})." if no_iso else " (none in this experiment)."), None),
        ("", None),
        ("6. Fit and antigens per cell (Fits sheet: one row per cell line × antibody × fit model)", H),
        ("Points from replicate plates are pooled per cell line × antibody. The fit is least squares; for a given Kd the "
         "best Bmax (and NS) is exact, so only Kd is searched.", None),
        ("Antigens/cell = Bmax × valency (blank valency = 1, so antigens/cell = ABC). Kd in nM uses the MW "
         "(blank = 150 kDa).", None),
        ("95 % confidence intervals come from the fit's standard errors (Bmax, Kd and, on NS rows, NS).", None),
        ("Summary shows both results per cell line × antibody and their ratio (NS fit ÷ isotype subtracted).", None),
        ("", None),
        ("7. Flags (Summary and Fits sheets)", H),
        (f"Not saturated: top conc below {st['saturation_k']:g} × Kd, so Bmax is extrapolated. Poor fit: R² < 0.9. "
         "Imprecise Bmax: SE > 25 % of Bmax.", None),
        ("ND: no specific binding (Bmax ≤ 0 or its CI reaches 0).", None),
        (f"NS fit only: Kd below the lowest or above the top dose; non-specific > {NS_SHARE_MAX:.0%} of the top-dose signal.", None),
        (f"Both rows: the two methods differ by > {CROSS_TOL:.0%}, or one gives a value where the other is ND.", None),
        ("Also flagged: missing or mismatched isotype, F/P assumed 1, low events, missing wells, bead QC, top dose above the "
         "High bead.", None),
        ("", None),
        ("Setup and data problems are listed on the Issues sheet.", Font(italic=True, color="808080")),
    ]
    for i, (text, font) in enumerate(lines, 1):
        c = ws.cell(i, 1, text)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if font:
            c.font = font
    ws.column_dimensions["A"].width = 130


def _fits(ws, res: Results):
    """One row per cell line x antibody x fit model: the isotype-subtracted row, then the NS-fit row."""
    from openpyxl.comments import Comment
    N0, K3, R4, PCT = "#,##0", "0.000", "0.0000", "0%"
    cols = [  # header, width, number format
        ("Cell line", 12, None), ("Antibody", 11, None), ("Fit model", 16, None), ("Target", 14, None), ("Clone", 10, None),
        ("Catalog #", 12, None), ("Lot #", 10, None), ("F/P", 7, None), ("Valency", 8, None), ("Plates", 9, None),
        ("n points", 7, None), ("Antigens/cell", 12, N0), ("Bmax (ABC)", 12, N0), ("Bmax 95% CI low", 12, N0),
        ("Bmax 95% CI high", 12, N0), ("Kd (µg/mL)", 10, K3), ("Kd 95% CI low", 10, K3), ("Kd 95% CI high", 10, K3),
        ("Kd (nM)", 9, K3), ("R²", 8, R4), ("Top conc (µg/mL)", 10, K3), ("Top conc / Kd", 9, K3),
        ("Specific ABC at top conc", 12, N0), ("Saturation", 30, None), ("Status", 10, None), ("Flags", 60, None),
        ("NS (ABC per µg/mL)", 11, N0), ("NS 95% CI low", 11, N0), ("NS 95% CI high", 11, N0),
        ("Non-specific ABC at top conc", 12, N0), ("Non-specific share at top conc", 11, PCT),
        ("Other model antigens/cell", 12, N0), ("NS fit ÷ isotype subtracted", 11, "0.00")]
    _hdr(ws, 1, [c[0] for c in cols], [c[1] for c in cols])
    at = {c[0]: get_column_letter(j) for j, c in enumerate(cols, 1)}
    ws[at["Fit model"] + "1"].comment = Comment(
        "Isotype subtracted: one-site fit of ABC − isotype ABC. NS fit: Bmax·C/(Kd+C) + NS·C on ABC, no isotype. "
        "Every antibody has both rows; without isotype data only the NS fit row.", "qfacs")
    ws[at["Specific ABC at top conc"] + "1"].comment = Comment(
        "Isotype subtracted: ABC − isotype ABC at the top conc. NS fit: the fitted saturable part Bmax·C/(Kd+C) at "
        "the top conc.", "qfacs")
    ws[at["Other model antigens/cell"] + "1"].comment = Comment(
        "Antigens/cell from the other fit model for the same cell line and antibody (its own row has the details).", "qfacs")
    for i, f in enumerate(res.fits, 2):
        g = f.reagent_rec
        fit = f.fit
        nd = f.status == "ND"
        ns_model = f.model == "NS"
        top_spec = f.top_specific
        if ns_model:
            top_spec = fit.bmax * f.top_conc / (fit.kd + f.top_conc) if not nd and fit.bmax is not None and f.top_conc else None
        cr = f.cross
        vals = [f.cell_line, f.reagent, "NS fit" if ns_model else "Isotype subtracted",
                g.get("target"), g.get("clone"), g.get("catalog"), g.get("lot"),
                g.get("fp_ratio") or ("1 (assumed)" if g.get("is_isotype") != "Y" else None),
                g.get("valency") or 1, ", ".join(f.plates), len(f.points),
                "ND" if nd else sig3(f.antigens), None if nd else fit.bmax,
                None if nd or not fit.bmax_ci else fit.bmax_ci[0], None if nd or not fit.bmax_ci else fit.bmax_ci[1],
                None if nd else fit.kd, None if nd or not fit.kd_ci else fit.kd_ci[0],
                None if nd or not fit.kd_ci else fit.kd_ci[1], None if nd else f.kd_nm, None if nd else fit.r2,
                f.top_conc, None if nd or not fit.kd else f.top_conc / fit.kd, top_spec, f.saturation, f.status,
                _flagtext(f.flags),
                fit.ns if ns_model and not nd else None, fit.ns_ci[0] if ns_model and not nd and fit.ns_ci else None,
                fit.ns_ci[1] if ns_model and not nd and fit.ns_ci else None,
                f.ns_top if not nd else None, f.ns_share_top if not nd else None,
                ("ND" if cr.nd else sig3(f.cross_antigens)) if cr else ("no isotype" if ns_model else None),
                f.ns_vs_iso]
        for j, v in enumerate(vals, 1):
            c = ws.cell(i, j, v)
            c.border = BOX
            if cols[j - 1][2]:
                c.number_format = cols[j - 1][2]
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{len(res.fits) + 1}"


def _wells(ws, res: Results):
    """One row per well. Calculated columns are live Excel formulas, so each value can be traced cell by cell:
    PE gMFI (input) -> PE/cell (bead curve on the Beads sheet) -> net of the no-antibody well -> / F/P = ABC ->
    minus the isotype at the same concentration = Specific ABC. ABC feeds the NS fit, Specific ABC the isotype fit."""
    from .analysis import antibody_fp
    cols = ["Plate", "Well", "Cell line", "Reagent", "Conc (µg/mL)", "Role", "Point", "Sample", "Source file",
            "Live events", "PE gMFI", "PE/cell", "No-antibody PE/cell", "ABC", "Isotype ABC", "Specific ABC", "Flags",
            "Net PE/cell", "F/P used", "F/P used for isotype"]
    _hdr(ws, 1, cols, [8, 6, 12, 10, 10, 9, 6, 18, 20, 9, 11, 11, 11, 11, 11, 11, 50, 11, 9, 11])
    notes = {"L": "= 10^((LOG10(PE gMFI) − intercept) / slope), bead curve on the Beads sheet",
             "M": "= average PE/cell of the no-antibody well(s) of the same row (or cell line)",
             "N": "= Net PE/cell ÷ F/P used. Input of the NS fit.",
             "O": "= isotype Net PE/cell at the same concentration (interpolated on log10 conc when the "
                  "concentrations differ) ÷ F/P used for isotype",
             "P": "= ABC − Isotype ABC. Input of the isotype-subtracted fit; blank when there is no isotype data "
                  "(NS fit only)",
             "R": "= PE/cell − No-antibody PE/cell",
             "S": "Input: F/P of the reagent from the setup workbook (1 when left blank)",
             "T": "Input: the isotype's F/P, or the antibody's F/P when the isotype's is blank"}
    from openpyxl.comments import Comment
    for col, text in notes.items():
        ws[f"{col}1"].comment = Comment(text, "qfacs")
    setup = res.setup
    row_of = {id(r): i for i, r in enumerate(res.wells, 2)}
    bead_row = {run: 2 + 4 * k for k, run in enumerate(res.beads)}      # first Beads sheet row of each bead run
    plate_run = {p["plate_id"]: p.get("bead_run") for p in setup.plates}
    blanks, iso = {}, {}
    for r in res.wells:
        w = r.well
        if w.role == "blank" and r.pe is not None:
            blanks.setdefault((w.plate_id, "row", w.row), []).append(r)
            blanks.setdefault((w.plate_id, "line", w.cell_line), []).append(r)
        if r.net_pe is not None and w.reagent and setup.reagent(w.reagent).get("is_isotype") == "Y" and w.conc_ug_ml > 0:
            iso.setdefault((w.reagent, w.cell_line, w.plate_id), []).append(r)

    def avg(rs, col="R"):
        return "AVERAGE(" + ",".join(f"{col}{row_of[id(x)]}" for x in rs) + ")"

    def iso_formula(r, i):
        """Isotype net PE at this well's concentration, as a formula over the isotype wells' Net PE/cell cells."""
        w = r.well
        name = r.iso_name
        rs = iso.get((name, w.cell_line, w.plate_id)) or [
            x for (n, line, _), v in iso.items() if n == name and line == w.cell_line for x in v]
        by = {}
        for x in rs:
            by.setdefault(x.well.conc_ug_ml, []).append(x)
        xs = sorted(by)
        c = w.conc_ug_ml
        if c <= xs[0] * (1 + 1e-9):
            return avg(by[xs[0]])
        if c >= xs[-1] * (1 - 1e-9):
            return avg(by[xs[-1]])
        for x0, x1 in zip(xs, xs[1:]):
            if x0 <= c <= x1:
                if abs(c - x0) <= 1e-9 * x0:
                    return avg(by[x0])
                if abs(c - x1) <= 1e-9 * x1:
                    return avg(by[x1])
                e0, e1 = f"E{row_of[id(by[x0][0])]}", f"E{row_of[id(by[x1][0])]}"
                return (f"({avg(by[x0])}+({avg(by[x1])}-{avg(by[x0])})*(LOG10(E{i})-LOG10({e0}))"
                        f"/(LOG10({e1})-LOG10({e0})))")
        return avg(by[xs[-1]])

    for i, r in enumerate(res.wells, 2):
        w = r.well
        reag = setup.reagent(w.reagent) if w.reagent else None
        is_iso = bool(reag) and reag.get("is_isotype") == "Y"
        b = bead_row.get(plate_run.get(w.plate_id))
        pe = f"=10^((LOG10(K{i})-Beads!$K${b})/Beads!$J${b})" if r.pe is not None and b else r.pe
        blank = net = abc = iso_abc = spec = fp = iso_fp = None
        if w.role == "titration" and r.pe is not None:
            bl = blanks.get((w.plate_id, "row", w.row)) or blanks.get((w.plate_id, "line", w.cell_line))
            blank = ("=" + avg(bl, "L")) if bl else None
            net = f"=L{i}-M{i}" if bl else f"=L{i}"
            fp = reag.get("fp_ratio") if is_iso else antibody_fp(reag)[0]
            if r.abc is not None:
                abc = f"=R{i}/S{i}"
            if not is_iso and r.iso_abc is not None:
                iso_fp = setup.reagent(r.iso_name).get("fp_ratio") or fp
                iso_abc = f"={iso_formula(r, i)}/T{i}"
                spec = f"=N{i}-O{i}"
        vals = [w.plate_id, w.well, w.cell_line, w.reagent or "", w.conc_ug_ml, w.role, w.point, r.sample, r.source,
                r.count, r.gmfi, pe, blank, abc, iso_abc, spec, _flagtext(r.flags), net, fp, iso_fp]
        for j, v in enumerate(vals, 1):
            c = ws.cell(i, j, v)
            if j == 5:
                c.number_format = "0.000"
            elif 10 <= j <= 16 or j == 18:
                c.number_format = "#,##0"
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:T{len(res.wells) + 1}"


def _beads(ws, res: Results):
    """Bead curve. Everything after the lot values and gMFIs is a live Excel formula."""
    cols = ["Bead run", "Source file", "Level", "PE/bead (lot)", "gMFI", "log10 PE", "log10 gMFI", "Back-calc. PE/bead",
            "% recovery", "Slope", "Intercept", "R²", "QC"]
    _hdr(ws, 1, cols, [9, 22, 10, 12, 10, 9, 9, 13, 10, 9, 9, 9, 40])
    r = 2
    from .calc import BEAD_KEYS, BEAD_LABELS
    for run, c in res.beads.items():
        a, z = r, r + len(BEAD_KEYS) - 1
        for k in BEAD_KEYS:
            vals = [run, c.source, BEAD_LABELS[k], c.pe[k], c.gmfi[k], f"=LOG10(D{r})", f"=LOG10(E{r})",
                    f"=10^((G{r}-K{r})/J{r})", f"=H{r}/D{r}", f"=SLOPE($G${a}:$G${z},$F${a}:$F${z})",
                    f"=INTERCEPT($G${a}:$G${z},$F${a}:$F${z})", f"=RSQ($G${a}:$G${z},$F${a}:$F${z})", c.qc]
            for j, v in enumerate(vals, 1):
                cell = ws.cell(r, j, v)
                cell.number_format = {4: "#,##0", 5: "#,##0", 8: "#,##0", 9: "0.0%", 12: "0.00000"}.get(j, "0.0000" if j in (6, 7, 10, 11) else "General")
            r += 1
    ws.cell(r + 1, 1, "Curve: log10(gMFI) = slope × log10(PE/bead) + intercept;  PE/cell = 10^((log10 gMFI − intercept) / slope).")


def _chart_text(size, bold=False):
    cp = CharacterProperties(sz=size, b=bold, solidFill="404040")
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), endParaRPr=cp)])


def _style_chart(ch):
    """Keep the title, axis titles and legend outside the plot area (Excel overlays them unless told not to)."""
    grey = LineProperties(solidFill="D9D9D9", w=9525)
    ch.title.overlay = False
    for par in ch.title.tx.rich.p:
        par.pPr = ParagraphProperties(defRPr=CharacterProperties(sz=1200, b=True, solidFill="262626"))
    for ax in (ch.x_axis, ch.y_axis):
        ax.delete = False
        ax.title.overlay = False
        for par in ax.title.tx.rich.p:
            par.pPr = ParagraphProperties(defRPr=CharacterProperties(sz=1000, b=False, solidFill="404040"))
        ax.tickLblPos = "low"  # labels stay at the bottom / left edge, not at the zero crossing
        ax.txPr = _chart_text(900)
        ax.majorGridlines.spPr = GraphicalProperties(ln=grey)
        ax.spPr = GraphicalProperties(ln=LineProperties(solidFill="7F7F7F", w=9525))
    ch.y_axis.number_format = "#,##0"
    ch.y_axis.scaling.min = 0
    ch.legend.position = "b"
    ch.legend.overlay = False
    ch.legend.txPr = _chart_text(900)
    # fixed plot area: room for the title above, axis titles left and below, legend at the bottom
    ch.plot_area.layout = Layout(manualLayout=ManualLayout(layoutTarget="inner", xMode="edge", yMode="edge",
                                                           x=0.15, y=0.13, w=0.80, h=0.58))


def _plots(wb, res: Results):
    """One line of charts per cell line x antibody: isotype subtracted on the left, NS fit on the right."""
    if not res.fits:
        return
    data = wb.create_sheet("Plot_Data")
    ws = wb.create_sheet("Plots", 1)
    ws["A1"] = ("Left: specific ABC (isotype subtracted) with the one-site fit. Right: total ABC with the NS fit "
                "Bmax·C/(Kd+C) + NS·C (dashed: its saturable part). Log concentration axis.")
    ws["A1"].font = TITLE_FONT

    def curve(ch, xcol, ycol, n, title, color, width=19050, dash=None):
        s = Series(Reference(data, min_col=ycol, min_row=3, max_row=2 + n),
                   Reference(data, min_col=xcol, min_row=3, max_row=2 + n), title=title)
        s.marker = Marker("none")
        s.smooth = True
        s.graphicalProperties.line.solidFill = color
        s.graphicalProperties.line.width = width
        if dash:
            s.graphicalProperties.line.dashStyle = dash
        ch.series.append(s)

    pair_row = {key: k for k, key in enumerate(res.by_pair)}
    for i, f in enumerate(res.fits):
        ns = f.model == "NS"
        c0 = 1 + 5 * i
        data.cell(1, c0, f"{f.cell_line} {f.reagent} {f.model}")
        for j, lab in enumerate(["conc", "ABC" if ns else "specific ABC", "fit conc", "fit", "saturable part"]):
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
                data.cell(3 + k, c0 + 3, f.fit.predict(x))
                if ns:
                    data.cell(3 + k, c0 + 4, f.fit.bmax * x / (f.fit.kd + x))
            n_fit = 40
        ch = ScatterChart()
        ch.title = (f"{f.cell_line} · {f.reagent}: " + ("NS fit" if ns else "isotype subtracted")
                    + (" (ND)" if f.status == "ND" else ""))
        ch.x_axis.title, ch.y_axis.title = "Concentration (µg/mL)", "ABC (total)" if ns else "Specific ABC"
        ch.x_axis.scaling.logBase = 10
        if f.points:  # whole decades around the data, so the curve fills the plot
            xs = [p[0] for p in f.points if p[0] > 0]
            ch.x_axis.scaling.min = 10 ** math.floor(math.log10(min(xs)))
            ch.x_axis.scaling.max = 10 ** math.ceil(math.log10(max(xs) * 1.5))
        _style_chart(ch)
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
            curve(ch, c0 + 2, c0 + 3, n_fit, "fit", "C00000")
            if ns:
                curve(ch, c0 + 2, c0 + 4, n_fit, "saturable part", "7F7F7F", 12700, "dash")
        ch.height, ch.width = 9, 14
        ws.add_chart(ch, f"{'J' if ns else 'A'}{3 + 19 * pair_row[(f.cell_line, f.reagent)]}")
    data.sheet_state = "hidden"


def _data_files(ws, res: Results):
    ws.append(["FlowJo export", "Plate", "Cell line", "Cell line from", "Wells used", "Wells not in Layout", "Antibodies (by row)"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for d in res.data_files:
        ws.append([d["file"], d["plate"], d["cell_line"], "file name" if d["named"] else "Layout", d["wells"], d["extra"],
                   d["antibodies"]])
    for col, w in zip("ABCDEFG", (34, 10, 16, 14, 11, 18, 40)):
        ws.column_dimensions[col].width = w


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
