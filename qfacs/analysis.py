"""Turn a setup plus FlowJo exports into antigens per cell.

Steps (README has the full description):
1. Bead curve per bead run.  2. Per well: gMFI -> PE/cell; ABC = (PE - same-row no-antibody PE) / F:P.
3. Every antibody is fitted with both models, each reported in full as its own row of Results.fits:
   Isotype: subtract the matched isotype's ABC at the same concentration (same cell line, log-concentration
   interpolation), then one-site fit Bmax*C/(Kd+C). Needs a matched isotype that was run.
   NS: no isotype subtraction; total-binding fit Bmax*C/(Kd+C) + NS*C on ABC.
   The two are never combined (that would remove the background twice). Without isotype data only the NS row
   exists, and it is flagged.
4. Antigens/cell = Bmax x valency.
QC conditions become flags; nothing is excluded automatically.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .calc import BeadCurve, FitResult, fit_beads, ns_fit, one_site_fit
from .model import Issue, Setup, Well
from .stats_io import bead_gmfis, read_table, well_stats
from .validate import isotype_mismatch, isotype_picker, validate
from .wellmap import expand_wells

DEFAULTS = dict(min_live_events=1000, bead_r2_min=0.98, saturation_k=5.0, mw_kda=150.0, valency=1.0)


@dataclass
class WellResult:
    well: Well
    sample: str | None = None
    source: str | None = None
    count: float | None = None
    gmfi: float | None = None
    pe: float | None = None
    blank_pe: float | None = None
    net_pe: float | None = None        # PE minus the no-antibody background
    abc: float | None = None
    iso_abc: float | None = None
    iso_name: str | None = None        # isotype subtracted from this well (matched, or the only one on the cell line)
    specific: float | None = None      # ABC - isotype ABC (input of the Isotype fit); None without isotype data
    flags: list = field(default_factory=list)


@dataclass
class FitRow:
    cell_line: str
    reagent: str
    reagent_rec: dict
    plates: list
    points: list            # [(conc, y)]: y = specific ABC (Isotype row) or ABC (NS row)
    fit: FitResult
    antigens: float | None = None
    top_conc: float | None = None
    top_specific: float | None = None
    kd_nm: float | None = None
    saturation: str = ""
    flags: list = field(default_factory=list)
    model: str = "Isotype"           # "Isotype" | "NS"
    ns_top: float | None = None      # NS model: non-specific ABC at the top conc (NS x top conc)
    ns_share_top: float | None = None  # NS model: share of the fitted top-dose signal that is non-specific
    cross: FitResult | None = None   # the other model's fit for the same cell line x antibody, when it exists
    cross_antigens: float | None = None
    ns_vs_iso: float | None = None   # NS antigens/cell / isotype-subtracted antigens/cell (same on both rows)

    @property
    def status(self):
        if self.fit.nd:
            return "ND"
        return "fitted" if self.antigens is not None else "not fitted"


@dataclass
class Results:
    setup: Setup
    issues: list
    notes: list
    beads: dict              # bead_run -> BeadCurve
    wells: list              # WellResult
    fits: list               # FitRow
    settings: dict
    data_files: list = field(default_factory=list)  # one dict per cell export: file, plate, cell line, wells, antibodies

    @property
    def by_pair(self) -> dict:
        """(cell line, antibody) -> {"Isotype": FitRow, "NS": FitRow}; the Isotype row is absent without isotype data."""
        out = {}
        for f in self.fits:
            out.setdefault((f.cell_line, f.reagent), {})[f.model] = f
        return out


FP_ASSUMED = "F/P assumed 1 (blank in setup)"
DEFAULT_FP = 1.0


def antibody_fp(reag) -> tuple[float, bool]:
    """F/P used to turn PE per cell into ABC, and whether the default (1, a 1:1 conjugate) was assumed."""
    fp = reag.get("fp_ratio") if reag else None
    return (fp, False) if fp else (DEFAULT_FP, True)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _setting(exp, key):
    v = exp.get(key)
    return DEFAULTS[key] if v in (None, "") else v


def match_plate(path, plates):
    """Plate for a data file: file name starts with the Plate ID or the plate's data folder/prefix."""
    stem = _norm(Path(path).stem)
    hits = []
    for p in plates:
        for key in (p.get("plate_id"), p.get("data_folder")):
            k = _norm(Path(str(key)).name) if key else ""
            if k and stem.startswith(k):
                hits.append(p["plate_id"])
                break
    if len(set(hits)) == 1:
        return hits[0]
    if len(plates) == 1 and not hits:
        return plates[0]["plate_id"]
    return None


def match_cell_line(path, plate, setup, wells):
    """Cell line named in an export's file name ('Plate1 U87 MG.xls', 'Plate1_U87.xls' -> 'U87 MG'), or None.

    Looks only at the plate's own cell lines when the plate is known. Matching ignores case, spaces and
    punctuation, and accepts a shortened name ('U87' for 'U87 MG') when it fits one line only.
    """
    rest = _norm(Path(path).stem)
    if plate:
        pk = _norm(plate)
        rest = rest[len(pk):] if rest.startswith(pk) else rest
        cands = list(dict.fromkeys(w.cell_line for w in wells if w.plate_id == plate))
    else:
        cands = [c["cell_line"] for c in setup.cell_lines if c.get("cell_line")]
    if not rest:
        return None
    src = {c.get("cell_line"): c.get("source_id") for c in setup.cell_lines}
    keys = {c: [k for k in (_norm(c), _norm(src.get(c))) if k] for c in cands}
    inside = [c for c, ks in keys.items() if any(k in rest for k in ks)]
    if inside:
        return max(inside, key=lambda c: len(_norm(c)))
    short = [c for c, ks in keys.items() if len(rest) >= 3 and any(k.startswith(rest) for k in ks)]
    return short[0] if len(short) == 1 else None


def analyze(setup: Setup, cell_files, bead_files, file_plate: dict | None = None, bead_run_files: dict | None = None,
            parse_issues=None) -> Results:
    """cell_files / bead_files: paths to FlowJo exports. file_plate / bead_run_files: explicit assignments."""
    issues = list(parse_issues or []) + validate(setup)
    notes: list[str] = []
    exp = setup.experiment
    settings = {k: _setting(exp, k) for k in ("min_live_events", "bead_r2_min", "saturation_k")}
    pe_param, gate = exp.get("pe_parameter"), exp.get("live_gate")
    res = Results(setup, issues, notes, {}, [], [], settings)
    if any(i.level == "error" for i in issues):
        return res

    # ---- beads
    runs = {b["bead_run"]: b for b in setup.beads}
    assign = dict(bead_run_files or {})
    unassigned = [f for f in bead_files if f not in assign.values()]
    for f in list(unassigned):
        for run, b in runs.items():
            if b.get("data_file") and _norm(Path(b["data_file"]).stem) == _norm(Path(f).stem):
                assign[run] = f
                unassigned.remove(f)
    free_runs = [r for r in runs if r not in assign]
    if len(free_runs) == 1 and len(unassigned) == 1:
        assign[free_runs[0]] = unassigned.pop()
    for f in unassigned:
        notes.append(f"bead file {Path(f).name} not matched to a bead run (set 'Bead data file' on the Beads sheet)")
    for run, f in assign.items():
        try:
            g = bead_gmfis(read_table(f), pe_param)
        except ValueError as e:
            issues.append(Issue("error", "Beads", runs[run]["_row"], str(e)))
            continue
        res.beads[run] = fit_beads(run, {k: runs[run][k] for k in g}, g, settings["bead_r2_min"], Path(f).name)
        if res.beads[run].qc != "PASS":
            issues.append(Issue("warning", "Beads", runs[run]["_row"], f"bead run {run}: {res.beads[run].qc}"))

    # ---- cell exports -> per-well stats; each file is tied to a plate and, from its name, a cell line
    wells, _ = expand_wells(setup)
    layout_at = {(w.plate_id, w.well): w for w in wells}
    stats = {}
    for f in cell_files:
        p = (file_plate or {}).get(f) or match_plate(f, setup.plates)
        line = match_cell_line(f, p, setup, wells)
        if not p and line:
            on = sorted({w.plate_id for w in wells if w.cell_line == line})
            p = on[0] if len(on) == 1 else None
        if not p:
            issues.append(Issue("warning", "Data", None, f"{Path(f).name}: could not tell which plate it belongs to; "
                                "skipped (name it '<Plate ID> <cell line>.xls', e.g. 'Plate1 A431.xls')"))
            continue
        try:
            ws, n = well_stats(read_table(f), pe_param, gate)
        except ValueError as e:
            issues.append(Issue("error", "Data", None, str(e)))
            continue
        notes += n
        used, wrong = [], []
        for st in ws:
            lw = layout_at.get((p, st.well))
            if line and lw and lw.cell_line != line:
                wrong.append(f"{st.well} ({lw.cell_line})")
                continue
            key = (p, st.well)
            if key in stats:
                notes.append(f"{p} {st.well}: found in {stats[key].source} and {st.source}; used the first")
                continue
            stats[key] = st
            if lw:
                used.append(lw)
        if wrong:
            issues.append(Issue("warning", "Data", None, f"{Path(f).name} is named for {line} but holds wells the Layout "
                                f"gives to another cell line: {', '.join(wrong)}; those wells were skipped"))
        lines = sorted({w.cell_line for w in used})
        if not line and len(lines) > 1:
            notes.append(f"{Path(f).name}: no cell line in the file name; wells assigned by the Layout ({', '.join(lines)})")
        res.data_files.append(dict(
            file=Path(f).name, plate=p, cell_line=line or ", ".join(lines) or "?", named=bool(line),
            wells=len(used), extra=len(ws) - len(used) - len(wrong),
            antibodies=", ".join(dict.fromkeys(w.reagent for w in sorted(used, key=lambda w: (w.row, w.col)) if w.reagent))))
    plates = {p["plate_id"]: p for p in setup.plates}
    min_events = settings["min_live_events"]
    wr_by = {}
    for w in wells:
        r = WellResult(w)
        s = stats.get((w.plate_id, w.well))
        curve = res.beads.get(plates[w.plate_id]["bead_run"])
        if s is None:
            r.flags.append("no data")
        else:
            r.sample, r.source, r.count, r.gmfi = s.sample, s.source, s.count, s.gmfi
            if s.count is not None and s.count < min_events:
                r.flags.append(f"low events ({s.count:.0f} < {min_events})")
            if curve is None:
                r.flags.append("no bead curve")
            elif s.gmfi is not None:
                r.pe = curve.pe_per_cell(s.gmfi)
                if s.gmfi > curve.gmfi_max:
                    r.flags.append("above High bead (extrapolated)")
                elif s.gmfi < curve.gmfi_min:
                    r.flags.append("below Low bead (extrapolated)")
        wr_by[(w.plate_id, w.well)] = r
    res.wells = sorted(wr_by.values(), key=lambda r: (r.well.plate_id, r.well.row, r.well.col))
    off = defaultdict(list)
    for (plate, well), s in stats.items():
        if (plate, well) not in wr_by:
            off[(s.source, plate)].append(well)
    for (src, plate), ws_ in off.items():
        notes.append(f"{src}: {len(ws_)} well(s) of {plate} not in the Layout, ignored ({ws_[0]}-{ws_[-1]})")

    # ---- background (no-antibody wells) and ABC
    blanks = defaultdict(list)       # (plate, row) and (plate, cell line) -> PE values
    for r in res.wells:
        if r.well.role == "blank" and r.pe is not None:
            blanks[(r.well.plate_id, "row", r.well.row)].append(r.pe)
            blanks[(r.well.plate_id, "line", r.well.cell_line)].append(r.pe)
    for r in res.wells:
        if r.well.role != "titration" or r.pe is None:
            continue
        b = blanks.get((r.well.plate_id, "row", r.well.row)) or blanks.get((r.well.plate_id, "line", r.well.cell_line))
        if b:
            r.blank_pe = sum(b) / len(b)
        else:
            r.flags.append("no no-antibody well: background not subtracted")
        reag = setup.reagent(r.well.reagent)
        r.net_pe = r.pe - (r.blank_pe or 0.0)
        if reag.get("is_isotype") == "Y":
            # isotype with blank F/P stays in PE units (see isotype subtraction below)
            r.abc = r.net_pe / reag["fp_ratio"] if reag.get("fp_ratio") else None
        else:
            fp, assumed = antibody_fp(reag)
            r.abc = r.net_pe / fp
            if assumed:
                r.flags.append(FP_ASSUMED)

    # ---- isotype subtraction
    pick_iso = isotype_picker(setup, wells)
    iso_pts = defaultdict(list)  # (isotype, cell line, plate) -> [(conc, abc)]
    for r in res.wells:
        if r.net_pe is not None and setup.reagent(r.well.reagent).get("is_isotype") == "Y":
            # kept in PE units; converted with the isotype's F/P, or the antibody's when the isotype F/P is blank
            iso_pts[(r.well.reagent, r.well.cell_line, r.well.plate_id)].append((r.well.conc_ug_ml, r.net_pe))
    for r in res.wells:
        reag = setup.reagent(r.well.reagent) if r.well.reagent else None
        if r.abc is None or reag.get("is_isotype") == "Y":
            continue
        iso, auto = pick_iso(r.well.reagent, r.well.cell_line)
        r.iso_name = iso
        pts = iso_pts.get((iso, r.well.cell_line, r.well.plate_id)) or [
            p for (i, line, _), v in iso_pts.items() if i == iso and line == r.well.cell_line for p in v]
        if not iso:
            r.flags.append(NO_ISO)
        elif not pts:
            r.flags.append(ISO_MISSING)
        else:
            iso_pe, outside = interp_log(pts, r.well.conc_ug_ml)
            iso_fp = setup.reagent(iso).get("fp_ratio")
            if iso_fp:
                r.iso_abc = iso_pe / iso_fp
            else:
                r.iso_abc = iso_pe / antibody_fp(reag)[0]
                r.flags.append(ISO_FP)
            if outside:
                r.flags.append("concentration outside isotype range (nearest isotype point used)")
            r.specific = r.abc - r.iso_abc

    # ---- fits per cell line x antibody (replicate plates pooled)
    groups = defaultdict(list)
    for r in res.wells:
        reag = setup.reagent(r.well.reagent) if r.well.reagent else None
        if r.well.role == "titration" and reag and reag.get("is_isotype") != "Y":
            groups[(r.well.cell_line, r.well.reagent)].append(r)
    for (line, name), rs in sorted(groups.items()):
        reag = setup.reagent(name)
        plate_ids = sorted({r.well.plate_id for r in rs})
        iso_pts_ = sorted((r.well.conc_ug_ml, r.specific) for r in rs if r.specific is not None)
        abc_pts = sorted((r.well.conc_ug_ml, r.abc) for r in rs if r.abc is not None)
        rows = {}
        if iso_pts_:
            rows["Isotype"] = _fit_row("Isotype", line, name, reag, plate_ids, iso_pts_, settings)
        rows["NS"] = _fit_row("NS", line, name, reag, plate_ids, abc_pts, settings)
        i_row, n_row = rows.get("Isotype"), rows["NS"]

        # the two results side by side
        if i_row:
            i_row.cross, i_row.cross_antigens = n_row.fit, n_row.antigens
            n_row.cross, n_row.cross_antigens = i_row.fit, i_row.antigens
            if i_row.antigens is not None and n_row.antigens is not None:
                i_row.ns_vs_iso = n_row.ns_vs_iso = n_row.antigens / i_row.antigens
                d = n_row.ns_vs_iso - 1
                if abs(d) > CROSS_TOL:
                    for fr in rows.values():
                        fr.flags.append(f"NS fit is {d:+.0%} vs isotype-subtracted antigens/cell")
            elif (i_row.antigens is None) != (n_row.antigens is None) and len(abc_pts) >= 5:
                got, other = ("NS fit", "isotype-subtracted") if n_row.antigens is not None else ("isotype-subtracted", "NS fit")
                for fr in rows.values():
                    fr.flags.append(f"models disagree: {got} gives a value, {other} is ND")

        # isotype flags: on the isotype-subtracted row, or on the NS row when that is the only one
        iso_name, auto = pick_iso(name, line)
        iso_rec = setup.reagent(iso_name) if iso_name else None
        if i_row:
            if auto:
                i_row.flags.append(f"matched isotype blank: used {iso_name} (the only isotype on this cell line)")
            if iso_rec and isotype_mismatch(reag, iso_rec):
                i_row.flags.append(f"isotype mismatch with {iso_name}")
            if any(ISO_FP in r.flags for r in rs):
                i_row.flags.append(ISO_FP)
            miss = sum(1 for r in rs if r.abc is not None and r.specific is None)
            if miss:
                i_row.flags.append(f"isotype data missing for {miss} well(s): left out of the isotype-subtracted fit")
        elif not iso_rec:
            n_row.flags.append(NO_ISO)
        elif abc_pts:
            n_row.flags.append(ISO_MISSING)

        # flags that hold for both models
        shared = []
        if any(FP_ASSUMED in r.flags for r in rs):
            shared.append(FP_ASSUMED)
        low = [r.well.well for r in rs if any(f.startswith("low events") for f in r.flags)]
        if low:
            shared.append(f"low events in {len(low)} well(s)")
        nodata = [r.well.well for r in rs if "no data" in r.flags]
        if nodata:
            shared.append(f"no data for {len(nodata)} well(s)")
        top = [r for r in rs if r.well.point == 1]
        if any("above High bead (extrapolated)" in r.flags for r in top):
            shared.append("note: top-dose signal above High bead")
        for p in plate_ids:
            c = res.beads.get(plates[p]["bead_run"])
            if c and c.qc != "PASS":
                shared.append(f"bead curve {c.bead_run}: {c.qc}")
        for fr in rows.values():
            fr.flags += shared
            res.fits.append(fr)
    return res


MODELS = ("Isotype", "NS")
MODEL_LABEL = {"Isotype": "isotype subtracted", "NS": "NS fit"}
NO_ISO = "no matched isotype: NS fit only"
ISO_MISSING = "isotype data missing: NS fit only"
ISO_FP = "isotype F/P unknown: subtracted in PE units (assumes equal F/P)"


def _fit_row(model, line, name, reag, plate_ids, pts, settings) -> FitRow:
    """Fit one model for one cell line x antibody and attach that model's own QC flags."""
    fit = _fit(model, pts)
    fr = FitRow(line, name, reag, plate_ids, pts, fit, model=model)
    ns = model == "NS"
    fr.flags += [f for f in fit.flags if not fit.nd or f.startswith("too few")]
    if pts:
        fr.top_conc = max(c for c, _ in pts)
        fr.top_specific = sum(v for c, v in pts if c == fr.top_conc) / sum(1 for c, _ in pts if c == fr.top_conc)
    if fit.bmax is not None and not fit.nd:
        fr.antigens = fit.bmax * (reag.get("valency") or DEFAULTS["valency"])
        fr.kd_nm = fit.kd * 1000 / (reag.get("mw_kda") or DEFAULTS["mw_kda"])
        ratio = fr.top_conc / fit.kd
        k = settings["saturation_k"]
        fr.saturation = "plateau reached" if ratio >= k else f"not saturated (top conc {ratio:.1f}× Kd < {k:g}×): Bmax extrapolated"
        if fr.saturation != "plateau reached":
            fr.flags.append(fr.saturation)
        if fit.r2 is not None and fit.r2 < 0.9:
            fr.flags.append(f"poor fit (R² {fit.r2:.2f})")
        if fit.bmax_se and fit.bmax_se / fit.bmax > 0.25:
            fr.flags.append("Bmax CI wide (SE > 25%; Bmax and NS trade off: add doses past saturation)" if ns else
                            "Bmax imprecise (SE > 25%)")
        if fit.at_bound:
            fr.flags.append("Kd at search bound: check curve")
        if ns:
            fr.flags += _ns_flags(fr, pts)
    elif fit.nd and len(pts) >= (5 if ns else 4):
        fr.flags.append("ND: no saturable binding above the non-specific line (NS fit)" if ns else
                        "ND: no specific binding above isotype")
    if ns and fit.ns is not None and fr.top_conc:
        fr.ns_top = fit.ns * fr.top_conc
        total = fit.predict(fr.top_conc)
        fr.ns_share_top = fr.ns_top / total if total else None
    return fr


CROSS_TOL = 0.25          # NS fit vs isotype-subtracted antigens/cell: flag a larger relative difference
NS_SHARE_MAX = 0.5        # flag when non-specific binding is more than this share of the top-dose signal


def _fit(model, pts):
    if model == "NS":
        return ns_fit(*zip(*pts)) if len(pts) >= 5 else ns_fit([], [])
    return one_site_fit(*zip(*pts)) if len(pts) >= 4 else one_site_fit([], [])


def _ns_flags(fr: FitRow, pts) -> list:
    """QC for the NS (total-binding) fit: Kd inside the doses tested, NS not dominating the top dose."""
    fit, out = fr.fit, []
    doses = [c for c, _ in pts if c > 0]
    if doses and fit.kd < min(doses):
        out.append(f"Kd ({fit.kd:.3g} µg/mL) below the lowest dose ({min(doses):.3g}): Kd poorly defined")
    if doses and fit.kd > max(doses):
        out.append(f"Kd ({fit.kd:.3g} µg/mL) above the top dose ({max(doses):.3g}): Bmax and NS not separable")
    total = fit.predict(fr.top_conc) if fr.top_conc else None
    if total and fit.ns is not None and fit.ns * fr.top_conc / total > NS_SHARE_MAX:
        out.append(f"non-specific is {fit.ns * fr.top_conc / total:.0%} of the top-dose signal")
    return out


def interp_log(pts, conc):
    """Linear interpolation of ABC on log10 concentration; clamps outside the range. Returns (value, outside)."""
    by = defaultdict(list)
    for c, v in pts:
        if c > 0:
            by[c].append(v)
    xs = sorted(by)
    ys = [sum(by[c]) / len(by[c]) for c in xs]
    if conc <= xs[0] * (1 - 1e-9):
        return ys[0], True
    if conc >= xs[-1] * (1 + 1e-9):
        return ys[-1], True
    lc = math.log10(conc)
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if x0 <= conc <= x1:
            if x1 == x0:
                return y0, False
            t = (lc - math.log10(x0)) / (math.log10(x1) - math.log10(x0))
            return y0 + t * (y1 - y0), False
    return ys[-1], False
