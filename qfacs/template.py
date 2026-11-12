"""Write the qFACS setup workbook (blank template or filled from a Setup)."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import schema as S
from .model import Setup

HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(bold=True, color="FFFFFF")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
TITLE_FONT = Font(bold=True, size=14, color="1F3864")
HELP_FONT = Font(italic=True, color="808080")
_thin = Side(style="thin", color="BFBFBF")
BOX = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

README_LINES = [
    ("qFACS experiment setup", TITLE_FONT),
    ("Fill in one workbook per experiment. Yellow cells are inputs; hover a column header's note for help.", None),
    ("", None),
    ("Sheets", Font(bold=True, size=12)),
    ("Experiment: IDs, PE parameter, live gate name, QC thresholds.", None),
    ("Beads: one row per Quantibrite PE tube acquired, with the lot's PE molecules per bead.", None),
    ("Reagents: every PE antibody and isotype with F/P, valency, host and isotype (all lot specific).", None),
    ("   Fit model per antibody: Isotype (default; subtract the matched isotype) or NS (fit non-specific binding, "
     "no isotype wells needed; run top doses well past saturation).", None),
    ("Cell_Lines: the lines tested, and any fluorescent reporter they carry.", None),
    ("Plates: plate IDs and which bead run calibrates each plate.", None),
    ("Layout: one line per plate row: cell line, reagent, top concentration, dilution, columns used.", None),
    ("Controls: unstained, PE-only, live/dead-only and reporter-only controls (wells or separate tubes).", None),
    ("", None),
    ("Check the workbook with:  python -m qfacs validate <this file>", Font(name="Consolas")),
]


def _dv_list_ref(token: str) -> str | None:
    """Excel list source for a '@name' choice token."""
    ranges = {
        "@reagents": ("Reagents", "A"),
        "@isotypes": ("Reagents", "A"),
        "@bead_runs": ("Beads", "A"),
        "@plates": ("Plates", "A"),
        "@cell_lines": ("Cell_Lines", "A"),
    }
    if token not in ranges:
        return None
    sheet, col = ranges[token]
    last = S.FIRST_DATA_ROW + S.TABLE_ROWS[sheet] - 1
    return f"={sheet}!${col}${S.FIRST_DATA_ROW}:${col}${last}"


def _validation_for(f: S.Field) -> DataValidation | None:
    if f.type == "yn":
        return DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
    if f.type == "row":
        return DataValidation(type="list", formula1='"' + ",".join(S.ROWS) + '"', allow_blank=True)
    if f.type == "choice" and f.choices:
        ref = _dv_list_ref(f.choices[0])
        if ref:
            return DataValidation(type="list", formula1=ref, allow_blank=True)
        return DataValidation(type="list", formula1='"' + ",".join(f.choices) + '"', allow_blank=True)
    if f.type in ("number", "int"):
        return DataValidation(type="decimal" if f.type == "number" else "whole", operator="greaterThan",
                              formula1="0", allow_blank=True)
    return None


def _xl(v):
    return "" if v is None else v


def write_setup(path, setup: Setup | None = None):
    """Write the setup workbook. With no setup this is the blank template."""
    setup = setup or Setup()
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    for i, (text, font) in enumerate(README_LINES, 1):
        c = ws.cell(i, 1, text)
        if font:
            c.font = font
    ws.column_dimensions["A"].width = 110

    for sh in S.SHEETS:
        ws = wb.create_sheet(sh.name)
        ws.cell(S.TITLE_ROW, 1, sh.title).font = TITLE_FONT
        if sh.help:
            ws.cell(S.HELP_ROW, 1, sh.help).font = HELP_FONT
        if sh.kind == "kv":
            _write_kv(ws, sh, setup.experiment)
        else:
            _write_table(ws, sh, getattr(setup, sh.name.lower()))

    meta = wb.create_sheet("_meta")
    meta["A1"], meta["B1"] = "template_version", S.TEMPLATE_VERSION
    meta.sheet_state = "hidden"
    wb.active = 1
    wb.save(path)
    return path


def _write_kv(ws, sh: S.Sheet, values: dict):
    ws.column_dimensions["A"].width = 52
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 80
    for i, f in enumerate(sh.fields):
        r = S.HEADER_ROW + i
        ws.cell(r, 1, f.header).font = Font(bold=True)
        v = values.get(f.key)
        c = ws.cell(r, 2, _xl(S.SUGGESTED.get(f.key) if v in (None, "") else v))
        c.fill, c.border = INPUT_FILL, BOX
        if f.help:
            ws.cell(r, 3, f.help).font = HELP_FONT
        dv = _validation_for(f)
        if dv:
            ws.add_data_validation(dv)
            dv.add(c.coordinate)


def _write_table(ws, sh: S.Sheet, records: list):
    nrows = S.TABLE_ROWS[sh.name]
    last = S.FIRST_DATA_ROW + nrows - 1
    for j, f in enumerate(sh.fields, 1):
        col = get_column_letter(j)
        h = ws.cell(S.HEADER_ROW, j, f.header + (" *" if f.required else ""))
        h.fill, h.font, h.border = HDR_FILL, HDR_FONT, BOX
        h.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        if f.help:
            from openpyxl.comments import Comment
            h.comment = Comment(f.help, "qfacs")
        ws.column_dimensions[col].width = f.width
        for r in range(S.FIRST_DATA_ROW, last + 1):
            c = ws.cell(r, j)
            c.fill, c.border = INPUT_FILL, BOX
        dv = _validation_for(f)
        if dv:
            ws.add_data_validation(dv)
            dv.add(f"{col}{S.FIRST_DATA_ROW}:{col}{last}")
    ws.row_dimensions[S.HEADER_ROW].height = 45
    ws.freeze_panes = ws.cell(S.FIRST_DATA_ROW, 1)
    if len(records) > nrows:
        raise ValueError(f"{sh.name}: {len(records)} records exceed the template's {nrows} rows")
    for i, rec in enumerate(records):
        for j, f in enumerate(sh.fields, 1):
            ws.cell(S.FIRST_DATA_ROW + i, j, _xl(rec.get(f.key)))
