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
    ws["A2"] = ("Antigens/cell = fitted Bmax × valency (3 significant figures). Isotype model: one-site fit after isotype "
                "subtraction; NS model: total-binding fit Bmax·C/(Kd+C) + NS·C (see Fits). ND = no specific binding. "
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


def _method(ws, res: Results):
    """Plain-language description of every calculation step, pointing to the sheet and columns that hold it."""
    from .analysis import CROSS_TOL, NS_SHARE_MAX
    from .schema import fit_model_of
    st = res.settings
    exp = res.setup.experiment
    abs_ = [r for r in res.setup.reagents if r.get("is_isotype") != "Y" and r.get("name")]
    ns = [r["name"] for r in abs_ if fit_model_of(r, exp) == "NS"]
    iso = [r["name"] for r in abs_ if fit_model_of(r, exp) != "NS"]
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
        ("5. Non-specific binding: one of two fit models per antibody (Fits sheet, column Fit model)", H),
        ("Isotype model" + (f" (used for: {', '.join(iso)})" if iso else " (not used in this experiment)") + ":", Font(bold=True)),
        ("   The matched isotype's ABC at the same concentration (column O; interpolated on log concentration when "
         "concentrations differ) is subtracted: Specific ABC = ABC − isotype ABC (column P).", None),
        ("   Then the one-site fit: Specific ABC = Bmax × C / (Kd + C).", None),
        ("NS model" + (f" (used for: {', '.join(ns)})" if ns else " (not used in this experiment)") + ":", Font(bold=True)),
        ("   No isotype is subtracted (column P = ABC). Total binding is fitted instead: "
         "ABC = Bmax × C / (Kd + C) + NS × C, with Bmax, Kd and NS all ≥ 0.", None),
        ("   NS × C is the non-specific signal, which rises linearly with antibody concentration. This needs top doses "
         "well past saturation (ideally ≥ 10 × Kd).", None),
        ("The two are never combined: subtracting the isotype and also fitting NS would remove the background twice.", None),
        ("Cross-check: when the matched isotype was run, the other model is fitted to the same wells and shown on Fits "
         "(columns Cross-check ...).", None),
        ("", None),
        ("6. Fit and antigens per cell (Fits sheet)", H),
        ("Points from replicate plates are pooled per cell line × antibody. The fit is least squares; for a given Kd the "
         "best Bmax (and NS) is exact, so only Kd is searched.", None),
        ("Antigens/cell = Bmax × valency (column K; blank valency = 1, so antigens/cell = ABC). Kd in nM uses the MW "
         "(blank = 150 kDa).", None),
        ("95 % confidence intervals come from the fit's standard errors (columns M, N and P, Q; NS CI in the NS columns).", None),
        ("", None),
        ("7. Flags (Summary and Fits sheets)", H),
        (f"Not saturated: top conc below {st['saturation_k']:g} × Kd, so Bmax is extrapolated. Poor fit: R² < 0.9. "
         "Imprecise Bmax: SE > 25 % of Bmax.", None),
        ("ND: no specific binding (Bmax ≤ 0 or its CI reaches 0).", None),
        (f"NS model only: Kd below the lowest or above the top dose; non-specific > {NS_SHARE_MAX:.0%} of the top-dose "
         f"signal; NS and isotype-method results differ by > {CROSS_TOL:.0%}.", None),
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
    cols = ["Cell line", "Antibody", "Target", "Clone", "Catalog #", "Lot #", "F/P", "Valency", "Plates", "n points",
            "Antigens/cell", "Bmax (ABC)", "Bmax 95% CI low", "Bmax 95% CI high", "Kd (µg/mL)", "Kd 95% CI low",
            "Kd 95% CI high", "Kd (nM)", "R²", "Top conc (µg/mL)", "Top conc / Kd", "Specific ABC at top conc",
            "Saturation", "Status", "Flags", "Fit model", "NS (ABC per µg/mL)", "NS 95% CI low", "NS 95% CI high",
            "Non-specific ABC at top conc", "Non-specific share at top conc", "Cross-check model",
            "Cross-check antigens/cell", "Cross-check Kd (µg/mL)", "Cross-check / main"]
    _hdr(ws, 1, cols, [12, 11, 14, 10, 12, 10, 7, 8, 9, 7, 12, 12, 12, 12, 10, 10, 10, 9, 8, 10, 9, 12, 30, 10, 60,
                       9, 11, 11, 11, 12, 11, 10, 12, 10, 10])
    from openpyxl.comments import Comment
    ws["W1"].comment = Comment("Specific ABC: isotype-subtracted for the Isotype model; for the NS model, the fitted "
                               "saturable part Bmax·C/(Kd+C) at the top conc", "qfacs")
    ws["AG1"].comment = Comment("When isotype data exists: the other model fitted to the same wells (NS model -> isotype "
                                "method; Isotype model -> NS fit on the unsubtracted ABC). Never both at once.", "qfacs")
    for i, f in enumerate(res.fits, 2):
        g = f.reagent_rec
        fit = f.fit
        nd = f.status == "ND"
        ns_model = f.model == "NS"
        top_spec = f.top_specific
        if ns_model and not nd and fit.bmax is not None and f.top_conc:
            top_spec = fit.bmax * f.top_conc / (fit.kd + f.top_conc)
        cr = f.cross
        vals = [f.cell_line, f.reagent, g.get("target"), g.get("clone"), g.get("catalog"), g.get("lot"),
                g.get("fp_ratio") or ("1 (assumed)" if g.get("is_isotype") != "Y" else None),
                g.get("valency") or 1, ", ".join(f.plates), len(f.points),
                "ND" if nd else sig3(f.antigens), None if nd else fit.bmax,
                None if nd or not fit.bmax_ci else fit.bmax_ci[0], None if nd or not fit.bmax_ci else fit.bmax_ci[1],
                None if nd else fit.kd, None if nd or not fit.kd_ci else fit.kd_ci[0],
                None if nd or not fit.kd_ci else fit.kd_ci[1], None if nd else f.kd_nm, None if nd else fit.r2,
                f.top_conc, None if nd or not fit.kd else f.top_conc / fit.kd, top_spec, f.saturation, f.status,
                _flagtext(f.flags), f.model,
                fit.ns if ns_model else None, fit.ns_ci[0] if ns_model and fit.ns_ci else None,
                fit.ns_ci[1] if ns_model and fit.ns_ci else None, f.ns_top, f.ns_share_top,
                cr.model if cr else None,
                ("ND" if cr.nd else sig3(f.cross_antigens)) if cr else None,
                cr.kd if cr and not cr.nd else None,
                f.cross_antigens / f.antigens if f.cross_antigens and f.antigens else None]
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
            elif j in (27, 28, 29, 30, 33):
                c.number_format = "#,##0"
            elif j in (31, 35):
                c.number_format = "0%"
            elif j == 34:
                c.number_format = "0.000"
    ws.freeze_panes = "C2"


def _wells(ws, res: Results):
    """One row per well. Calculated columns are live Excel formulas, so each value can be traced cell by cell:
    PE gMFI (input) -> PE/cell (bead curve on the Beads sheet) -> net of the no-antibody well -> / F/P = ABC ->
    minus the isotype at the same concentration = Specific ABC."""
    from .analysis import antibody_fp
    from .schema import fit_model_of
    cols = ["Plate", "Well", "Cell line", "Reagent", "Conc (µg/mL)", "Role", "Point", "Sample", "Source file",
            "Live events", "PE gMFI", "PE/cell", "No-antibody PE/cell", "ABC", "Isotype ABC", "Specific ABC", "Flags",
            "Net PE/cell", "F/P used", "F/P used for isotype"]
    _hdr(ws, 1, cols, [8, 6, 12, 10, 10, 9, 6, 18, 20, 9, 11, 11, 11, 11, 11, 11, 50, 11, 9, 11])
    notes = {"L": "= 10^((LOG10(PE gMFI) − intercept) / slope), bead curve on the Beads sheet",
             "M": "= average PE/cell of the no-antibody well(s) of the same row (or cell line)",
             "N": "= Net PE/cell ÷ F/P used",
             "O": "= isotype Net PE/cell at the same concentration (interpolated on log10 conc when the "
                  "concentrations differ) ÷ F/P used for isotype",
             "P": "= ABC − Isotype ABC (Isotype model); = ABC for NS-model antibodies, whose fit includes "
                  "non-specific binding (an isotype, if run, is shown for the cross-check only)",
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
        name = setup.reagent(w.reagent).get("matched_isotype")
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
        ns_model = bool(reag) and not is_iso and fit_model_of(reag, setup.experiment) == "NS"
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
                iso_fp = setup.reagent(reag.get("matched_isotype")).get("fp_ratio") or fp
                iso_abc = f"={iso_formula(r, i)}/T{i}"
                spec = f"=N{i}" if ns_model else f"=N{i}-O{i}"
            elif not is_iso and r.specific is not None:
                spec = f"=N{i}"                               # no isotype to subtract (flagged)
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


def _plots(wb, res: Results):
    if not res.fits:
        return
    data = wb.create_sheet("Plot_Data")
    ws = wb.create_sheet("Plots", 1)
    ws["A1"] = ("Specific ABC vs antibody concentration, with the one-site fit (log concentration axis). "
                "NS-model antibodies: total ABC with the Bmax·C/(Kd+C) + NS·C fit.")
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
                data.cell(3 + k, c0 + 3, f.fit.predict(x))
            n_fit = 40
        ch = ScatterChart()
        ch.title = f"{f.cell_line} · {f.reagent}" + (" (NS fit)" if f.model == "NS" else "") + (" (ND)" if f.status == "ND" else "")
        ch.x_axis.title, ch.y_axis.title = "µg/mL", "ABC (total)" if f.model == "NS" else "Specific ABC"
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
