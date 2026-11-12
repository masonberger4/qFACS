"""Read a qFACS setup workbook into a Setup, reporting cells that cannot be parsed."""
from __future__ import annotations

import datetime as dt

from openpyxl import load_workbook

from . import schema as S
from .model import Issue, Setup


def _norm_header(h) -> str:
    return str(h or "").replace(" *", "").strip().lower()


def _convert(f: S.Field, v):
    """Return (value, error message or None)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None, None
    if isinstance(v, str):
        v = v.strip()
    if f.type in ("number", "int"):
        if isinstance(v, bool):
            return None, f"'{f.header}' must be a number"
        if isinstance(v, str):
            try:
                v = float(v.replace(",", ""))
            except ValueError:
                return None, f"'{f.header}' must be a number, got '{v}'"
        if f.type == "int":
            if float(v) != int(v):
                return None, f"'{f.header}' must be a whole number, got {v}"
            return int(v), None
        return float(v), None
    if f.type == "yn":
        s = str(v).strip().upper()
        if s in ("Y", "YES", "TRUE"):
            return "Y", None
        if s in ("N", "NO", "FALSE"):
            return "N", None
        return None, f"'{f.header}' must be Y or N, got '{v}'"
    if f.type == "row":
        s = str(v).strip().upper()
        if s in S.ROWS and len(s) == 1:
            return s, None
        return None, f"'{f.header}' must be a row letter A-H, got '{v}'"
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d"), None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v), None


def read_setup(path):
    """Read the workbook. Returns (Setup, issues); issues hold unreadable cells and missing sheets."""
    wb = load_workbook(path, data_only=True)
    setup = Setup(source=str(path))
    issues: list[Issue] = []
    for sh in S.SHEETS:
        if sh.name not in wb.sheetnames:
            issues.append(Issue("error", sh.name, None, "sheet is missing (start from the qfacs template)"))
            continue
        ws = wb[sh.name]
        if sh.kind == "kv":
            setup.experiment = _read_kv(ws, sh, issues)
        else:
            setattr(setup, sh.name.lower(), _read_table(ws, sh, issues))
    if _old_fit_model_set(wb):
        issues.append(Issue("warning", "Experiment", None, "the 'Fit model' setting is no longer used: every antibody is "
                            "reported with both the isotype-subtracted fit and the NS fit"))
    return setup, issues


def _old_fit_model_set(wb) -> bool:
    """True when a workbook made from an older template has a Fit model value filled in (Experiment or Reagents)."""
    if "Experiment" in wb.sheetnames:
        ws = wb["Experiment"]
        for r in range(1, ws.max_row + 1):
            if _norm_header(ws.cell(r, 1).value).startswith("fit model") and ws.cell(r, 2).value not in (None, ""):
                return True
    if "Reagents" in wb.sheetnames:
        ws = wb["Reagents"]
        for c in range(1, ws.max_column + 1):
            if _norm_header(ws.cell(S.HEADER_ROW, c).value).startswith("fit model"):
                return any(ws.cell(r, c).value not in (None, "") for r in range(S.FIRST_DATA_ROW, ws.max_row + 1))
    return False


def _read_kv(ws, sh, issues):
    by_label = {_norm_header(f.header): f for f in sh.fields}
    out = {}
    for r in range(1, ws.max_row + 1):
        f = by_label.get(_norm_header(ws.cell(r, 1).value))
        if not f:
            continue
        val, err = _convert(f, ws.cell(r, 2).value)
        if err:
            issues.append(Issue("error", sh.name, r, err))
        out[f.key] = val
    return out


def _read_table(ws, sh, issues):
    by_header = {_norm_header(h): f for f in sh.fields for h in (f.header, *f.aliases)}
    cols = {}
    for c in range(1, ws.max_column + 1):
        f = by_header.get(_norm_header(ws.cell(S.HEADER_ROW, c).value))
        if f:
            cols[f.key] = c
    for f in sh.fields:
        if f.key not in cols and f.required:
            issues.append(Issue("error", sh.name, S.HEADER_ROW, f"required column '{f.header}' not found"))
    records = []
    for r in range(S.FIRST_DATA_ROW, ws.max_row + 1):
        raw = {k: ws.cell(r, c).value for k, c in cols.items()}
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in raw.values()):
            continue
        rec = {"_row": r}
        for f in sh.fields:
            if f.key not in cols:
                rec[f.key] = None
                continue
            val, err = _convert(f, raw[f.key])
            if err:
                issues.append(Issue("error", sh.name, r, err))
            rec[f.key] = val
        records.append(rec)
    return records
