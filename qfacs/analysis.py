"""Turn a setup plus FlowJo exports into antigens per cell.

Steps (README has the full description):
1. Bead curve per bead run.  2. Per well: gMFI -> PE/cell; ABC = (PE - same-row no-antibody PE) / F:P.
3. Subtract the matched isotype's ABC at the same concentration (same cell line, log-concentration interpolation).
4. One-site fit per cell line x antibody; antigens/cell = Bmax x valency.
QC conditions become flags; nothing is excluded automatically.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .calc import BeadCurve, FitResult, fit_beads, one_site_fit
from .model import Issue, Setup, Well
from .stats_io import bead_gmfis, read_table, well_stats
from .validate import isotype_mismatch, validate
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
    abc: float | None = None
    iso_abc: float | None = None
    specific: float | None = None
    flags: list = field(default_factory=list)


@dataclass
class FitRow:
    cell_line: str
    reagent: str
    reagent_rec: dict
    plates: list
    points: list            # [(conc, specific ABC)]
    fit: FitResult
    antigens: float | None = None
    top_conc: float | None = None
    top_specific: float | None = None
    kd_nm: float | None = None
    saturation: str = ""
    flags: list = field(default_factory=list)

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

    # ---- cell exports -> per-well stats
    plate_of = {}
    for f in cell_files:
        p = (file_plate or {}).get(f) or match_plate(f, setup.plates)
        if not p:
            notes.append(f"{Path(f).name}: could not tell which plate it belongs to; skipped (name it '<Plate ID>_...')")
            continue
        plate_of[f] = p
    stats = {}
    for f, plate in plate_of.items():
        try:
            ws, n = well_stats(read_table(f), pe_param, gate)
        except ValueError as e:
            issues.append(Issue("error", "Data", None, str(e)))
            continue
        notes += n
        for s in ws:
            key = (plate, s.well)
            if key in stats:
                notes.append(f"{plate} {s.well}: found in {stats[key].source} and {s.source}; used the first")
                continue
            stats[key] = s

    wells, _ = expand_wells(setup)
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
    for (plate, well), s in stats.items():
        if (plate, well) not in wr_by:
            notes.append(f"{plate} {well} ({s.source}) is not in the Layout; ignored")

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
        r.abc = (r.pe - (r.blank_pe or 0.0)) / reag["fp_ratio"]

    # ---- isotype subtraction
    iso_pts = defaultdict(list)  # (isotype, cell line, plate) -> [(conc, abc)]
    for r in res.wells:
        if r.abc is not None and setup.reagent(r.well.reagent).get("is_isotype") == "Y":
            iso_pts[(r.well.reagent, r.well.cell_line, r.well.plate_id)].append((r.well.conc_ug_ml, r.abc))
    for r in res.wells:
        reag = setup.reagent(r.well.reagent) if r.well.reagent else None
        if r.abc is None or reag.get("is_isotype") == "Y":
            continue
        iso = reag.get("matched_isotype")
        pts = iso_pts.get((iso, r.well.cell_line, r.well.plate_id)) or [
            p for (i, line, _), v in iso_pts.items() if i == iso and line == r.well.cell_line for p in v]
        if not iso:
            r.specific = r.abc
            r.flags.append("no matched isotype: not subtracted")
        elif not pts:
            r.specific = r.abc
            r.flags.append("isotype data missing: not subtracted")
        else:
            r.iso_abc, outside = interp_log(pts, r.well.conc_ug_ml)
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
        pts = [(r.well.conc_ug_ml, r.specific) for r in rs if r.specific is not None]
        fr = FitRow(line, name, reag, sorted({r.well.plate_id for r in rs}), sorted(pts), one_site_fit(*zip(*pts)) if len(pts) >= 4 else one_site_fit([], []))
        fit = fr.fit
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
                fr.flags.append("Bmax imprecise (SE > 25%)")
            if fit.at_bound:
                fr.flags.append("Kd at search bound: check curve")
        elif fit.nd and len(pts) >= 4:
            fr.flags.append("ND: no specific binding above isotype")
        iso_rec = setup.reagent(reag.get("matched_isotype")) if reag.get("matched_isotype") else None
        if iso_rec and isotype_mismatch(reag, iso_rec):
            fr.flags.append(f"isotype mismatch with {reag.get('matched_isotype')}")
        if any(r for r in rs if "no matched isotype: not subtracted" in r.flags):
            fr.flags.append("no matched isotype: not subtracted")
        elif any(r for r in rs if "isotype data missing: not subtracted" in r.flags):
            fr.flags.append("isotype data missing: not subtracted")
        low = [r.well.well for r in rs if any(f.startswith("low events") for f in r.flags)]
        if low:
            fr.flags.append(f"low events in {len(low)} well(s)")
        nodata = [r.well.well for r in rs if "no data" in r.flags]
        if nodata:
            fr.flags.append(f"no data for {len(nodata)} well(s)")
        top = [r for r in rs if r.well.point == 1]
        if any("above High bead (extrapolated)" in r.flags for r in top):
            fr.flags.append("note: top-dose signal above High bead")
        for p in fr.plates:
            c = res.beads.get(plates[p]["bead_run"])
            if c and c.qc != "PASS":
                fr.flags.append(f"bead curve {c.bead_run}: {c.qc}")
        res.fits.append(fr)
    return res


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
