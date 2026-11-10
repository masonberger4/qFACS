"""Single source of truth for the qFACS setup workbook layout.

The template writer, the reader and the validator all use these definitions, so a column
added here appears in the template and is read back without other changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

TEMPLATE_VERSION = "1"

ROWS = "ABCDEFGH"
NCOLS = 12

CONTROL_TYPES = ["Unstained", "PE only", "Live/dead only", "Reporter only", "Other"]
YN = ["Y", "N"]


@dataclass(frozen=True)
class Field:
    key: str            # attribute name in the model
    header: str         # text shown in the workbook
    type: str = "text"  # text | number | int | yn | row | choice
    required: bool = False
    help: str = ""
    width: int = 14
    choices: tuple = ()  # for type "choice"; "@reagents" etc. = list built from another sheet


@dataclass(frozen=True)
class Sheet:
    name: str
    kind: str                 # "kv" (label / value pairs) or "table" (one record per row)
    title: str
    fields: tuple = field(default_factory=tuple)
    help: str = ""


# Suggested values pre-filled in a new setup workbook (the analysis uses the same values when a cell is blank).
SUGGESTED = {"min_live_events": 1000, "bead_r2_min": 0.98, "saturation_k": 5,
             # automatic gating channels (BD FACSDiscover A8 raw detectors)
             "gate_fsc": "FSC-A", "gate_ssc": "SSC (Violet)-A", "gate_width": "SSC (Violet)-W",
             "gate_viability": "V6 (515)-A"}

EXPERIMENT = Sheet("Experiment", "kv", "Experiment", (
    Field("experiment_id", "Experiment ID", required=True),
    Field("date", "Date (yyyy-mm-dd)"),
    Field("operator", "Operator"),
    Field("instrument", "Instrument"),
    Field("pe_parameter", "PE parameter (as in the data, e.g. PE-A or B5 (575)-A)",
          help="The channel the analysis reads. After unmixing this is usually the PE fluorochrome name."),
    Field("live_gate", "Live gate name (last gate of the path)",
          help="Name of the final gate, e.g. Live. Used to find gMFI and counts in exports."),
    Field("fixed_after_staining", "Cells fixed after staining? (Y/N)", "yn",
          help="Recorded so fixed and unfixed runs can be compared."),
    Field("min_live_events", "Min live events per well (QC)", "int",
          help="Suggested 1000 (pre-filled; blank = 1000). Wells with fewer live events are flagged (still used). "
               "Lower it for scarce cells, raise it for more precise gMFI."),
    Field("bead_r2_min", "Bead curve R² minimum (QC)", "number",
          help="Suggested 0.98 (pre-filled; blank = 0.98). R² of the log-log line through the 4 bead peaks (shown on the Beads sheet "
               "of the results); good runs are > 0.99. Below this, results on that plate are flagged 'check beads'."),
    Field("saturation_k", "Saturated when top conc ≥ k × Kd (k)", "number",
          help="Suggested 5 (pre-filled; blank = 5); use 10 for a stricter check. Kd comes from the fit. At 5×Kd ~83% of antigen is bound, at 10×Kd ~91%. "
               "If the top conc is below k×Kd, Bmax is extrapolated and flagged 'not saturated'. Lower k if stock conc limits you."),
    Field("gate_fsc", "Auto gating: forward scatter (area)",
          help="Suggested FSC-A (pre-filled; blank = FSC-A). Only used when a plate has .fcs files but no FlowJo .wsp: "
               "the program then draws Cells > Single Cells > Live itself, one set of gates per plate and cell line. "
               "Use the parameter name exactly as in the .fcs file."),
    Field("gate_ssc", "Auto gating: side scatter (area)",
          help="Suggested SSC (Violet)-A (pre-filled; blank = SSC (Violet)-A). Y axis of the Cells gate."),
    Field("gate_width", "Auto gating: singlet width parameter",
          help="Suggested SSC (Violet)-W (pre-filled; blank = SSC (Violet)-W). Doublets are removed on side scatter area vs width, "
               "as in the hand-drawn Single Cells gate."),
    Field("gate_viability", "Auto gating: viability dye parameter (none = no Live gate)",
          help="Suggested V6 (515)-A (pre-filled; blank = V6 (515)-A), the live/dead dye detector. Live = the dim main peak. "
               "Type none if no viability dye was used."),
    Field("notes", "Notes", width=60),
), help="One value per line. Yellow cells are inputs.")

BEADS = Sheet("Beads", "table", "Quantibrite PE bead runs (one row per bead tube acquired)", (
    Field("bead_run", "Bead run ID", required=True, help="e.g. Set1. Plates point to this ID."),
    Field("kit_lot", "Kit lot #", required=True),
    Field("lot_expiry", "Lot expiry (yyyy-mm-dd)"),
    Field("pe_low", "PE/bead Low", "number", required=True, help="From the lot flyer."),
    Field("pe_med_low", "PE/bead Med-Low", "number", required=True),
    Field("pe_med_high", "PE/bead Med-High", "number", required=True),
    Field("pe_high", "PE/bead High", "number", required=True),
    Field("data_file", "Bead data file (.fcs or export)", width=30),
    Field("notes", "Notes", width=40),
), help="PE molecules per bead are lot specific: copy them from the flyer in the kit.")

REAGENTS = Sheet("Reagents", "table", "PE reagents, including isotype controls", (
    Field("name", "Name (used in Layout)", required=True, width=16),
    Field("target", "Target antigen", width=16),
    Field("is_isotype", "Isotype control? (Y/N)", "yn", required=True),
    Field("host", "Host species", help="e.g. Mouse, Rat, Rabbit, Human."),
    Field("isotype", "Isotype / Fc", help="e.g. IgG1 κ, IgG2a, rabbit Fc chimera."),
    Field("clone", "Clone"),
    Field("vendor", "Vendor"),
    Field("catalog", "Catalog #"),
    Field("lot", "Lot #"),
    Field("stock_ug_ml", "Stock (µg/mL)", "number"),
    Field("fp_ratio", "F/P (PE per antibody)", "number",
          help="Optional. PE molecules per antibody, lot specific (vial label or CoA); ABC = PE per cell / F/P. "
               "Blank on an antibody = 1 (a 1:1 PE conjugate, e.g. BD Quantibrite-format antibodies), flagged "
               "'F/P assumed 1' in the results. Blank on an isotype = isotype subtracted in PE units "
               "(assumes the same F/P as the antibody)."),
    Field("valency", "Valency (antigens per antibody bound)", "number",
          help="Blank = 1 (antigens/cell reported as ABC)."),
    Field("mw_kda", "MW (kDa)", "number", help="For Kd in nM. Blank = 150."),
    Field("matched_isotype", "Matched isotype (Name)", "choice", choices=("@isotypes",), width=16,
          help="Isotype row subtracted from this antibody."),
    Field("notes", "Notes", width=40),
), help="Every value here is lot specific and entered by the user; nothing is pre-filled.")

CELL_LINES = Sheet("Cell_Lines", "table", "Cell lines", (
    Field("cell_line", "Cell line", required=True, width=16),
    Field("source_id", "Source / internal ID"),
    Field("reporter", "Fluorescent reporter (blank = none)", width=20,
          help="e.g. GFP. A reporter line needs a reporter-only control for unmixing."),
    Field("notes", "Notes", width=40),
))

PLATES = Sheet("Plates", "table", "Plates", (
    Field("plate_id", "Plate ID", required=True, help="Matches the plate name in the data files."),
    Field("bead_run", "Bead run ID", "choice", required=True, choices=("@bead_runs",)),
    Field("acquired", "Acquired (yyyy-mm-dd)"),
    Field("data_folder", "Data folder or file prefix", width=30),
    Field("notes", "Notes", width=40),
))

LAYOUT = Sheet("Layout", "table", "Plate layout: one line per plate row", (
    Field("plate_id", "Plate ID", "choice", required=True, choices=("@plates",)),
    Field("row", "Row (A-H)", "row", required=True, width=8),
    Field("cell_line", "Cell line", "choice", required=True, choices=("@cell_lines",), width=16),
    Field("reagent", "Reagent (Name)", "choice", required=True, choices=("@reagents",), width=16),
    Field("top_conc_ug_ml", "Top conc, final (µg/mL)", "number", required=True),
    Field("dilution_factor", "Dilution factor", "number", required=True, help="e.g. 1.8"),
    Field("first_col", "First column", "int", required=True, width=9),
    Field("n_points", "Number of points", "int", required=True, width=9),
    Field("blank_cols", "No-antibody column(s)", width=12,
          help="Cells + buffer only, e.g. 12. Several: 11,12."),
    Field("notes", "Notes", width=40),
), help="Points run left to right from the top concentration, each one dilution factor lower.")

CONTROLS = Sheet("Controls", "table", "Controls for gating and unmixing (wells or separate .fcs files)", (
    Field("control_id", "Control ID", required=True),
    Field("type", "Type", "choice", required=True, choices=tuple(CONTROL_TYPES)),
    Field("cell_line", "Cell line (blank = any)", "choice", choices=("@cell_lines",), width=16),
    Field("plate_id", "Plate ID (if a well)", "choice", choices=("@plates",)),
    Field("well", "Well (e.g. A12)", width=9),
    Field("data_file", "Data file (if a tube)", width=30),
    Field("fluorochrome", "Fluorochrome / reporter", width=16),
    Field("notes", "Notes", width=40),
))

SHEETS = (EXPERIMENT, BEADS, REAGENTS, CELL_LINES, PLATES, LAYOUT, CONTROLS)
SHEET_BY_NAME = {s.name: s for s in SHEETS}

# Table layout inside the workbook
TITLE_ROW = 1
HELP_ROW = 2
HEADER_ROW = 4
FIRST_DATA_ROW = 5
TABLE_ROWS = {"Beads": 10, "Reagents": 30, "Cell_Lines": 60, "Plates": 40, "Layout": 320, "Controls": 120}
