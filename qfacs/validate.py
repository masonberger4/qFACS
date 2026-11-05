"""Check a Setup for missing values, broken references and QC conditions.

Errors block the analysis. Warnings are flags that travel with the results.
"""
from __future__ import annotations

import re
from collections import defaultdict

from . import schema as S
from .model import Issue, Setup
from .wellmap import expand_wells

WELL_RE = re.compile(r"^([A-Ha-h])\s*0?([1-9]|1[0-2])$")


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower().replace("κ", "k").replace("kappa", "k"))


def _dups(records, key, sheet, issues, label):
    seen = {}
    for rec in records:
        v = rec.get(key)
        if v in (None, ""):
            continue
        if v in seen:
            issues.append(Issue("error", sheet, rec["_row"], f"{label} '{v}' is also on row {seen[v]}"))
        else:
            seen[v] = rec["_row"]


def _required(sheet: S.Sheet, records, issues):
    for rec in records:
        for f in sheet.fields:
            if f.required and rec.get(f.key) in (None, ""):
                issues.append(Issue("error", sheet.name, rec["_row"], f"'{f.header}' is required"))


def validate(setup: Setup) -> list[Issue]:
    issues: list[Issue] = []
    exp = setup.experiment

    # ---- Experiment
    if not exp.get("experiment_id"):
        issues.append(Issue("error", "Experiment", None, "Experiment ID is required"))
    if not exp.get("pe_parameter"):
        issues.append(Issue("warning", "Experiment", None, "PE parameter is blank; it is needed to read gMFI from the data"))
    if not exp.get("live_gate"):
        issues.append(Issue("warning", "Experiment", None, "Live gate name is blank; it is needed to read gMFI from exports"))
    if exp.get("fixed_after_staining") == "Y":
        issues.append(Issue("warning", "Experiment", None,
                            "cells fixed after staining: BD lists fixation as a factor that can affect quantitation"))
    elif not exp.get("fixed_after_staining"):
        issues.append(Issue("warning", "Experiment", None, "fixation (Y/N) not recorded"))

    # ---- Beads
    _required(S.BEADS, setup.beads, issues)
    _dups(setup.beads, "bead_run", "Beads", issues, "bead run")
    if not setup.beads:
        issues.append(Issue("error", "Beads", None, "no bead run entered; a Quantibrite curve is needed for PE molecules"))
    for b in setup.beads:
        vals = [b.get(k) for k in ("pe_low", "pe_med_low", "pe_med_high", "pe_high")]
        if all(v is not None for v in vals):
            if any(v <= 0 for v in vals):
                issues.append(Issue("error", "Beads", b["_row"], "PE/bead values must be positive"))
            elif not all(a < c for a, c in zip(vals, vals[1:])):
                issues.append(Issue("error", "Beads", b["_row"], "PE/bead values must rise Low < Med-Low < Med-High < High"))
    bead_ids = {b["bead_run"] for b in setup.beads if b.get("bead_run")}

    # ---- Reagents
    _required(S.REAGENTS, setup.reagents, issues)
    _dups(setup.reagents, "name", "Reagents", issues, "reagent")
    reagents = {r["name"]: r for r in setup.reagents if r.get("name")}
    for r in setup.reagents:
        for k, label in (("fp_ratio", "F/P"), ("valency", "valency"), ("mw_kda", "MW")):
            if r.get(k) is not None and r[k] <= 0:
                issues.append(Issue("error", "Reagents", r["_row"], f"{label} must be positive"))
        mi = r.get("matched_isotype")
        if mi:
            iso = reagents.get(mi)
            if iso is None:
                issues.append(Issue("error", "Reagents", r["_row"], f"matched isotype '{mi}' is not a reagent Name"))
            elif iso.get("is_isotype") != "Y":
                issues.append(Issue("error", "Reagents", r["_row"], f"matched isotype '{mi}' is not marked as an isotype control"))
            elif r.get("is_isotype") != "Y":
                _isotype_match(r, iso, issues)

    # ---- Cell lines, plates
    _required(S.CELL_LINES, setup.cell_lines, issues)
    _dups(setup.cell_lines, "cell_line", "Cell_Lines", issues, "cell line")
    lines = {c["cell_line"]: c for c in setup.cell_lines if c.get("cell_line")}
    _required(S.PLATES, setup.plates, issues)
    _dups(setup.plates, "plate_id", "Plates", issues, "plate")
    plates = {p["plate_id"]: p for p in setup.plates if p.get("plate_id")}
    for p in setup.plates:
        if p.get("bead_run") and p["bead_run"] not in bead_ids:
            issues.append(Issue("error", "Plates", p["_row"], f"bead run '{p['bead_run']}' is not on the Beads sheet"))

    # ---- Layout
    _required(S.LAYOUT, setup.layout, issues)
    if not setup.layout:
        issues.append(Issue("error", "Layout", None, "no plate rows entered"))
    for rec in setup.layout:
        r = rec["_row"]
        if rec.get("plate_id") and rec["plate_id"] not in plates:
            issues.append(Issue("error", "Layout", r, f"plate '{rec['plate_id']}' is not on the Plates sheet"))
        if rec.get("reagent") and rec["reagent"] not in reagents:
            issues.append(Issue("error", "Layout", r, f"reagent '{rec['reagent']}' is not on the Reagents sheet"))
        if rec.get("cell_line") and rec["cell_line"] not in lines:
            issues.append(Issue("warning", "Layout", r, f"cell line '{rec['cell_line']}' is not on the Cell_Lines sheet"))
        if rec.get("top_conc_ug_ml") is not None and rec["top_conc_ug_ml"] <= 0:
            issues.append(Issue("error", "Layout", r, "top concentration must be positive"))
    wells, well_issues = expand_wells(setup)
    issues += well_issues

    # usage: which reagents run on which cell lines, and is there a no-antibody well per line and plate
    used = defaultdict(set)          # reagent -> {cell lines}
    blank = set()                    # (plate, cell line) with a no-antibody well
    for w in wells:
        if w.role == "blank":
            blank.add((w.plate_id, w.cell_line))
        else:
            used[w.reagent].add(w.cell_line)
    first_row = {}
    for rec in setup.layout:
        first_row.setdefault((rec.get("plate_id"), rec.get("cell_line")), rec["_row"])
    for (plate, line), row in first_row.items():
        if plate and line and (plate, line) not in blank:
            issues.append(Issue("warning", "Layout", row,
                                f"{line} on plate {plate} has no no-antibody well; autofluorescence cannot be subtracted"))

    for name, line_set in used.items():
        r = reagents.get(name)
        if not r:
            continue
        if r.get("is_isotype") == "Y":
            continue
        mi = r.get("matched_isotype")
        if not mi:
            issues.append(Issue("warning", "Reagents", r["_row"], f"{name} has no matched isotype; isotype background is not subtracted"))
            continue
        for line in sorted(line_set - used.get(mi, set())):
            issues.append(Issue("warning", "Reagents", r["_row"],
                                f"{name} runs on {line} but its matched isotype {mi} does not"))
    for r in setup.reagents:
        if r.get("name") and r["name"] not in used:
            issues.append(Issue("warning", "Reagents", r["_row"], f"{r['name']} is not used in the Layout"))

    # ---- Controls
    _required(S.CONTROLS, setup.controls, issues)
    types = set()
    for c in setup.controls:
        row = c["_row"]
        if c.get("type"):
            if c["type"] not in S.CONTROL_TYPES:
                issues.append(Issue("error", "Controls", row, f"type '{c['type']}' must be one of {', '.join(S.CONTROL_TYPES)}"))
            types.add((c["type"], c.get("cell_line")))
        has_well = bool(c.get("plate_id") or c.get("well"))
        if not has_well and not c.get("data_file"):
            issues.append(Issue("error", "Controls", row, "give a plate and well, or a data file"))
        if has_well:
            if c.get("plate_id") and c["plate_id"] not in plates:
                issues.append(Issue("error", "Controls", row, f"plate '{c['plate_id']}' is not on the Plates sheet"))
            if not c.get("plate_id") or not WELL_RE.match(str(c.get("well") or "")):
                issues.append(Issue("error", "Controls", row, "a control well needs a Plate ID and a well like A12"))
        if c.get("cell_line") and c["cell_line"] not in lines:
            issues.append(Issue("warning", "Controls", row, f"cell line '{c['cell_line']}' is not on the Cell_Lines sheet"))
    if not any(t == "PE only" for t, _ in types):
        issues.append(Issue("warning", "Controls", None, "no PE-only control; unmixing PE will not be possible"))
    for c in setup.cell_lines:
        if c.get("reporter") and not any(t == "Reporter only" and line in (None, c.get("cell_line")) for t, line in types):
            issues.append(Issue("warning", "Cell_Lines", c["_row"],
                                f"{c['cell_line']} carries {c['reporter']} but has no reporter-only control for unmixing"))
    return issues


def isotype_mismatch(ab: dict, iso: dict):
    """True when host or isotype differ, False when they match, None when either is blank."""
    if not (ab.get("host") and ab.get("isotype") and iso.get("host") and iso.get("isotype")):
        return None
    return _norm(ab["host"]) != _norm(iso["host"]) or _norm(ab["isotype"]) != _norm(iso["isotype"])


def _isotype_match(ab: dict, iso: dict, issues):
    """Flag an antibody whose matched isotype differs in host species or isotype."""
    missing = [lbl for d, lbl in ((ab, ab["name"]), (iso, iso["name"])) if not d.get("host") or not d.get("isotype")]
    if missing:
        issues.append(Issue("warning", "Reagents", ab["_row"],
                            f"cannot check the isotype match for {ab['name']}: host or isotype blank for {', '.join(missing)}"))
        return
    if isotype_mismatch(ab, iso):
        issues.append(Issue("warning", "Reagents", ab["_row"],
                            f"isotype mismatch: {ab['name']} is {ab['host']} {ab['isotype']} but {iso['name']} is "
                            f"{iso['host']} {iso['isotype']}"))


def summarize(issues: list[Issue]) -> str:
    e = sum(i.level == "error" for i in issues)
    w = sum(i.level == "warning" for i in issues)
    return f"{e} error(s), {w} warning(s)"
