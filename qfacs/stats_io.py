"""Read FlowJo table exports (.xls, .xlsx, .csv, .txt/.tsv).

A FlowJo table export has one row per sample and one column per '<gate path> | <statistic>',
plus summary rows (Mean, SD, ...) at the bottom, which are dropped.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

SUMMARY_ROWS = {"mean", "sd", "median", "cv", "min", "max", "rsd", "robust sd", "robust cv"}
WELL_RE = re.compile(r"^\s*([A-Ha-h])\s*0?([1-9]|1[0-2])(?!\d)")


@dataclass
class StatsTable:
    path: str
    headers: list                      # column headers after the sample column
    rows: dict = field(default_factory=dict)  # sample name -> {header: raw value}

    def columns(self, stat_prefix: str):
        """Headers whose statistic starts with stat_prefix, as (header, gate path)."""
        out = []
        for h in self.headers:
            gate, stat = split_header(h)
            if stat.lower().startswith(stat_prefix.lower()):
                out.append((h, gate))
        return out


def split_header(h: str):
    if "|" in h:
        g, s = h.split("|", 1)
        return g.strip(), s.strip()
    return "", h.strip()


def to_number(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("%", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def well_of(sample: str):
    """'E01-Sample_049' -> 'E01'. None when the name does not start with a well ID."""
    m = WELL_RE.match(str(sample))
    return f"{m.group(1).upper()}{int(m.group(2)):02d}" if m else None


def _grid(path: Path):
    ext = path.suffix.lower()
    if ext == ".xls":
        try:
            import xlrd
            sh = xlrd.open_workbook(str(path)).sheet_by_index(0)
            return [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
        except Exception:
            pass  # FlowJo sometimes writes tab-separated text with an .xls name
    if ext in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        ws = load_workbook(path, data_only=True, read_only=True).worksheets[0]
        return [list(r) for r in ws.iter_rows(values_only=True)]
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    delim = "\t" if text.count("\t") > text.count(",") else ","
    return list(csv.reader(text.splitlines(), delimiter=delim))


def read_table(path) -> StatsTable:
    path = Path(path)
    grid = [r for r in _grid(path) if any(v not in (None, "") for v in r)]
    if not grid:
        raise ValueError(f"{path.name}: empty file")
    headers = ["" if h is None else str(h).strip() for h in grid[0][1:]]
    t = StatsTable(str(path), headers)
    for r in grid[1:]:
        name = "" if r[0] is None else str(r[0]).strip()
        if not name or name.lower() in SUMMARY_ROWS:
            continue
        t.rows[name] = {h: (r[i + 1] if i + 1 < len(r) else None) for i, h in enumerate(headers)}
    return t


def pick_gmfi_column(t: StatsTable, pe_parameter: str | None, gate_name: str | None):
    """Choose the PE geometric-mean column. Returns (header, gate path, note or None) or raises ValueError."""
    cands = t.columns("Geometric Mean")
    if pe_parameter:
        cands = [(h, g) for h, g in cands if pe_parameter.lower() in h.lower()]
    if not cands:
        raise ValueError(f"{Path(t.path).name}: no 'Geometric Mean' column" + (f" for {pe_parameter}" if pe_parameter else ""))
    if gate_name:
        named = [(h, g) for h, g in cands if g.split("/")[-1].strip().lower() == gate_name.lower()]
        if len(named) == 1:
            return named[0][0], named[0][1], None
    if len(cands) == 1:
        h, g = cands[0]
        note = None
        if gate_name and g.split("/")[-1].strip().lower() != gate_name.lower():
            note = f"{Path(t.path).name}: live gate is named '{g.split('/')[-1]}', not '{gate_name}'; used it as the only PE gMFI column"
        return h, g, note
    raise ValueError(f"{Path(t.path).name}: several PE gMFI columns ({', '.join(g for _, g in cands)}); set the live gate name")


@dataclass
class WellStat:
    sample: str
    well: str
    gmfi: float | None
    count: float | None
    gate: str
    source: str


def well_stats(t: StatsTable, pe_parameter, gate_name):
    """Per-well PE gMFI and live count from a cell export. Returns (stats, notes)."""
    notes = []
    h, gate, note = pick_gmfi_column(t, pe_parameter, gate_name)
    if note:
        notes.append(note)
    count_h = next((x for x in t.headers if split_header(x) == (gate, "Count")), None)
    out = []
    for sample, vals in t.rows.items():
        w = well_of(sample)
        if not w:
            notes.append(f"{Path(t.path).name}: sample '{sample}' has no well ID; skipped")
            continue
        out.append(WellStat(sample, w, to_number(vals.get(h)), to_number(vals.get(count_h)) if count_h else None,
                            gate, Path(t.path).name))
    return out, notes


BEAD_LEVELS = (("pe_low", "low"), ("pe_med_low", "medlow"), ("pe_med_high", "medhigh"), ("pe_high", "high"))


def bead_gmfis(t: StatsTable, pe_parameter):
    """{'pe_low': gMFI, ...} from a bead export with gates named Low / Med Low / Med High / High."""
    found = {}
    for h, gate in t.columns("Geometric Mean"):
        if pe_parameter and pe_parameter.lower() not in h.lower():
            continue
        leaf = re.sub(r"[^a-z]", "", gate.split("/")[-1].lower())
        for key, name in BEAD_LEVELS:
            if leaf == name:
                vals = [to_number(v.get(h)) for v in t.rows.values()]
                vals = [v for v in vals if v is not None]
                if vals:
                    found[key] = sum(vals) / len(vals)
    missing = [n for k, n in BEAD_LEVELS if k not in found]
    if missing:
        raise ValueError(f"{Path(t.path).name}: bead gate(s) not found: {', '.join(missing)} "
                         "(expected gates named Low, Med Low, Med High, High)")
    return found
