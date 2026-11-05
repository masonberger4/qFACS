"""Expand Layout lines into one record per well."""
from __future__ import annotations

from . import schema as S
from .model import Issue, Setup, Well


def parse_cols(text) -> list[int]:
    """'12' -> [12]; '11, 12' -> [11, 12]; '' -> []. Raises ValueError on bad input."""
    if text is None or str(text).strip() == "":
        return []
    out = []
    for part in str(text).replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        n = float(part)
        if n != int(n):
            raise ValueError(part)
        out.append(int(n))
    return out


def well_name(row: str, col: int) -> str:
    return f"{row}{col:02d}"


def expand_wells(setup: Setup):
    """Return (wells, issues). Lines with missing required values are skipped (validate reports them)."""
    wells: dict[tuple, Well] = {}
    issues: list[Issue] = []
    for rec in setup.layout:
        r = rec["_row"]
        need = ("plate_id", "row", "cell_line", "reagent", "top_conc_ug_ml", "dilution_factor", "first_col", "n_points")
        if any(rec.get(k) in (None, "") for k in need):
            continue
        first, n, df, top = rec["first_col"], rec["n_points"], rec["dilution_factor"], rec["top_conc_ug_ml"]
        new = []
        if n < 1 or first < 1 or first + n - 1 > S.NCOLS:
            issues.append(Issue("error", "Layout", r, f"points run from column {first} to {first + n - 1}; columns must be 1-{S.NCOLS}"))
        elif df <= 1:
            issues.append(Issue("error", "Layout", r, f"dilution factor must be greater than 1, got {df:g}"))
        else:
            for k in range(n):
                c = first + k
                new.append(Well(rec["plate_id"], well_name(rec["row"], c), rec["row"], c, rec["cell_line"],
                                rec["reagent"], top / df ** k, "titration", k + 1, r))
        try:
            blanks = parse_cols(rec.get("blank_cols"))
        except ValueError:
            issues.append(Issue("error", "Layout", r, f"no-antibody column(s) '{rec.get('blank_cols')}' must be column numbers like 12 or 11,12"))
            blanks = []
        for c in blanks:
            if not 1 <= c <= S.NCOLS:
                issues.append(Issue("error", "Layout", r, f"no-antibody column {c} is outside 1-{S.NCOLS}"))
                continue
            new.append(Well(rec["plate_id"], well_name(rec["row"], c), rec["row"], c, rec["cell_line"],
                            None, 0.0, "blank", None, r))
        for w in new:
            key = (w.plate_id, w.well)
            old = wells.get(key)
            if old is None:
                wells[key] = w
            elif old.role == "blank" and w.role == "blank" and old.cell_line == w.cell_line:
                continue  # the same shared no-antibody well listed on two lines
            else:
                issues.append(Issue("error", "Layout", r,
                                    f"well {w.well} on plate {w.plate_id} is also used by Layout row {old.layout_row}"))
    return list(wells.values()), issues
