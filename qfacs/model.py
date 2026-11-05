"""In-memory setup: plain records keyed by the field keys in schema.py."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Setup:
    experiment: dict = field(default_factory=dict)
    beads: list = field(default_factory=list)
    reagents: list = field(default_factory=list)
    cell_lines: list = field(default_factory=list)
    plates: list = field(default_factory=list)
    layout: list = field(default_factory=list)
    controls: list = field(default_factory=list)
    source: str = ""

    def reagent(self, name):
        return next((r for r in self.reagents if r.get("name") == name), None)


@dataclass(frozen=True)
class Issue:
    level: str      # "error" (blocks analysis) | "warning" (flag, analysis continues)
    sheet: str
    row: int | None  # workbook row number, None for sheet-wide issues
    message: str

    def __str__(self):
        where = self.sheet + (f" row {self.row}" if self.row else "")
        return f"{self.level.upper():7s} {where}: {self.message}"


@dataclass(frozen=True)
class Well:
    plate_id: str
    well: str           # e.g. A01
    row: str
    col: int
    cell_line: str
    reagent: str | None  # None for no-antibody wells
    conc_ug_ml: float    # 0 for no-antibody wells
    role: str            # "titration" | "blank"
    point: int | None    # 1 = top concentration
    layout_row: int      # workbook row of the Layout line
