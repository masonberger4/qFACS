"""Build the Excel-only qFACS workbook (Power Query import + formula-only analysis).
python build_qfacs_xl.py <out.xlsx> [--example inputs.xlsx export1.xls ... ]  (example = pre-filled Plate 1 copy)
"""
import os, re, sys, datetime as dt
import xlrd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.chart import ScatterChart, BarChart, Reference, Series
from openpyxl.chart.marker import Marker
from openpyxl.utils import get_column_letter as COL

ROWS = 'ABCDEFGH'
IMAX = 20000                                 # last Import row referenced by formulas
NAB = 8
BEADS = [('Low', 'Low', 474), ('Med-Low', 'Med Low', 5359), ('Med-High', 'Med High', 23843), ('High', 'High', 62336)]
NG1, NG2 = 241, 101                          # Kd grid sizes (stage 1 / stage 2)
G1R0 = 6; G2R0 = G1R0 + NG1 + 4              # first grid rows on Fit_Grid
GSR = G2R0 + NG2 + 2                         # grid summary rows start
NCURVE = 60

HDR = PatternFill('solid', fgColor='1F3864'); HF = Font(bold=True, color='FFFFFF')
INP = PatternFill('solid', fgColor='FFF2CC'); CAL = PatternFill('solid', fgColor='EDEDED')
OVR = PatternFill('solid', fgColor='FCE4D6')
RED = PatternFill('solid', fgColor='FFC7CE'); GRN = PatternFill('solid', fgColor='C6EFCE')
TITLE = Font(bold=True, size=14, color='1F3864'); _t = Side(style='thin', color='BFBFBF')
BOX = Border(left=_t, right=_t, top=_t, bottom=_t); WARN = Font(bold=True, color='C00000')
IMPORT_COLS = ['File', 'Kind', 'PlateID', 'CellLine', 'RowKey', 'Well', 'Gate', 'Stat', 'Header', 'Num', 'Text', 'Key', 'Loaded']
STAT_ROWS = {'mean', 'sd', 'median', 'cv', 'min', 'max', 'rsd', 'robust sd', 'robust cv'}


def hdr(ws, row, col, labels, height=None):
    for i, l in enumerate(labels):
        c = ws.cell(row, col + i, l); c.fill = HDR; c.font = HF; c.border = BOX
        c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
    if height: ws.row_dimensions[row].height = height


def name(wb, n, ref): wb.defined_names[n] = DefinedName(n, attr_text=ref)


def inp(c, v=None, fill=INP):
    if v is not None: c.value = v
    c.fill = fill; c.border = BOX; return c


def cal(c, v, fmt=None):
    c.value = v; c.fill = CAL; c.border = BOX
    if fmt: c.number_format = fmt
    return c


def sig3(ref):
    return f'IF({ref}=0,0,ROUND({ref},2-INT(LOG10(ABS({ref})))))'


# ------------------------------------------------------------------ Power Query (M) -------------------------------
M_CODE = r'''// qFACS_Import  -  reads every FlowJo table export (.xls / .csv / .txt) in THIS workbook's folder
// into one long table (one row per file x sample row x statistic column). Paste into Power Query > Advanced Editor.
let
    FolderRaw   = Text.Trim(Text.From(Excel.CurrentWorkbook(){[Name="PQ_Folder"]}[Content]{0}[Column1])),
    Unesc       = (t as text) as text => List.Accumulate({{"%20"," "},{"%2C",","},{"%28","("},{"%29",")"},{"%26","&"},{"%27","'"}},
                     t, (s, p) => Text.Replace(s, p{0}, p{1})),
    Folder      = Unesc(FolderRaw),
    IsWeb       = Text.StartsWith(Text.Lower(Folder), "http"),

    // ---- SharePoint / OneDrive (workbook opened from a synced library reports an https:// path) -------------
    Segs        = List.Select(Text.Split(Text.Replace(Folder, "\", "/"), "/"), each _ <> ""),   // {"https:", host, "sites", site, library, sub...}
    SiteUrl     = Segs{0} & "//" & Text.Combine(List.Range(Segs, 1, 3), "/"),
    SubPath     = List.Skip(Segs, 4),
    WebFolder   = () => List.Accumulate(SubPath, SharePoint.Contents(SiteUrl, [ApiVersion = 15]),
                     (tbl, seg) => tbl{[Name = seg]}[Content]),

    // ---- local / mapped drive / UNC ---------------------------------------------------------------------
    LocalFolder = () => let
                        F = Folder.Files(Folder),
                        Norm = (p as text) => Text.Lower(Text.TrimEnd(p, "\")),
                        Here = Table.SelectRows(F, each Norm([Folder Path]) = Norm(Folder))   // no sub-folders
                      in Here,

    Listing     = if IsWeb then WebFolder() else LocalFolder(),
    Files0      = Table.SelectRows(Listing, each List.Contains({".xls", ".csv", ".txt"}, Text.Lower([Extension]))
                                         and not Text.StartsWith([Name], "~$")),
    Files       = Table.SelectColumns(Files0, {"Name", "Extension", "Content"}),

    ReadRaw     = (bin as binary, ext as text) as table =>
                    let
                        AsXls = try Table.SelectRows(Excel.Workbook(bin, false), each [Kind] = "Sheet"){0}[Data] otherwise null,
                        AsTab = Table.FromColumns(Table.ToColumns(Csv.Document(bin, [Delimiter = "#(tab)", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]))),
                        AsCsv = Csv.Document(bin, [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
                        T = if ext = ".xls" then (if AsXls <> null then AsXls else AsTab)
                            else if ext = ".csv" then AsCsv else AsTab
                    in T,

    ToNum       = (v) => if v = null then null
                         else if Value.Is(v, type number) then v
                         else try Number.FromText(Text.Trim(Text.Replace(Text.Replace(Text.From(v), "%", ""), ",", "")), "en-US") otherwise null,

    WellOf      = (k as text) =>
                    let s = Text.Upper(Text.Trim(k)),
                        L = Text.Start(s, 1),
                        dig = Text.Combine(List.FirstN(Text.ToList(Text.Middle(s, 1)), each Text.Contains("0123456789", _))),
                        n = if dig = "" or Text.Length(dig) > 2 then null else Number.FromText(dig)
                    in if L <> "" and Text.Contains("ABCDEFGH", L) and n <> null and n >= 1 and n <= 12
                       then L & Text.PadStart(Text.From(n), 2, "0") else null,

    ParseFile   = (fname as text, ext as text, bin as binary) as table =>
                    let
                        T     = ReadRaw(bin, ext),
                        Cols  = Table.ColumnNames(T),
                        Hdr   = List.Transform(Record.FieldValues(T{0}), each if _ = null then "" else Text.Trim(Text.From(_))),
                        Body0 = Table.Skip(T, 1),
                        Body1 = Table.TransformColumns(Body0, {{Cols{0}, each if _ = null then "" else Text.Trim(Text.From(_)), type text}}),
                        Body  = Table.SelectRows(Body1, each Record.Field(_, Cols{0}) <> ""
                                    and not List.Contains({"mean","sd","median","cv","min","max","rsd","robust sd","robust cv"},
                                                          Text.Lower(Record.Field(_, Cols{0})))),
                        Unp   = Table.UnpivotOtherColumns(Body, {Cols{0}}, "Col", "Value"),
                        Ren   = Table.RenameColumns(Unp, {{Cols{0}, "RowKey"}}),
                        AddH  = Table.AddColumn(Ren, "Header", each Hdr{List.PositionOf(Cols, [Col])}, type text),
                        Stem  = Text.BeforeDelimiter(fname, ".", {0, RelativePosition.FromEnd}),
                        Kind  = if Text.Contains(Text.Lower(fname), "bead") then "bead" else "cells",
                        Pid   = Text.BeforeDelimiter(Stem, " "),
                        Cell  = Text.Trim(Text.AfterDelimiter(Stem, " ")),
                        Out   = Table.FromRecords(Table.TransformRows(AddH, (r) =>
                                  let h  = r[Header],
                                      wl = WellOf(r[RowKey]),
                                      g  = if Text.Contains(h, "|") then Text.Trim(Text.BeforeDelimiter(h, "|")) else "",
                                      st = if Text.Contains(h, "|") then Text.Trim(Text.AfterDelimiter(h, "|")) else h
                                  in [File = fname, Kind = Kind, PlateID = Pid, CellLine = Cell, RowKey = r[RowKey], Well = wl,
                                      Gate = g, Stat = st, Header = h, Num = ToNum(r[Value]), Text = Text.From(r[Value]),
                                      Key = Kind & "|" & Pid & "|" & (if wl = null then "" else wl) & "|" & st]))
                    in Out,

    Safe        = (fname, ext, bin) => try ParseFile(fname, ext, bin) otherwise
                    #table({"File","Kind","PlateID","CellLine","RowKey","Well","Gate","Stat","Header","Num","Text","Key"},
                           {{fname, "error", "", "", "", null, "", "", "PARSE ERROR", null, "file could not be read", ""}}),
    Parsed      = Table.AddColumn(Files, "T", each Safe([Name], Text.Lower([Extension]), [Content])),
    Combined    = if Table.RowCount(Parsed) = 0
                    then #table({"File","Kind","PlateID","CellLine","RowKey","Well","Gate","Stat","Header","Num","Text","Key"}, {})
                    else Table.Combine(Parsed[T]),
    Stamped     = Table.AddColumn(Combined, "Loaded", each DateTime.LocalNow(), type datetime),
    Typed       = Table.TransformColumnTypes(Stamped, {{"File", type text}, {"Kind", type text}, {"PlateID", type text},
                    {"CellLine", type text}, {"RowKey", type text}, {"Well", type text}, {"Gate", type text}, {"Stat", type text},
                    {"Header", type text}, {"Num", type number}, {"Text", type text}, {"Key", type text}})
in
    Typed'''


# ------------------------------------------------------------------ Python replica of the M import (example data) ----
def _num(v):
    if v is None or v == '': return None
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).replace('%', '').replace(',', '').strip())
    except ValueError: return None


def _well(k):
    s = k.strip().upper(); L = s[:1]; m = re.match(r'(\d+)', s[1:])
    if L and L in 'ABCDEFGH' and m and len(m.group(1)) <= 2 and 1 <= int(m.group(1)) <= 12: return f'{L}{int(m.group(1)):02d}'
    return None


def pq_emulate(path, fname=None):
    fname = fname or os.path.basename(path)
    sh = xlrd.open_workbook(path).sheet_by_index(0)
    hdrs = [str(sh.cell_value(0, c)).strip() for c in range(sh.ncols)]
    stem = os.path.splitext(fname)[0]; pid, _, cell = stem.partition(' ')
    kind = 'bead' if 'bead' in fname.lower() else 'cells'
    out = []
    for r in range(1, sh.nrows):
        key = str(sh.cell_value(r, 0)).strip()
        if not key or key.lower() in STAT_ROWS: continue
        for c in range(1, sh.ncols):
            v = sh.cell_value(r, c)
            if v in ('', None): continue
            h = hdrs[c]
            gate, stat = (h.split('|', 1)[0].strip(), h.split('|', 1)[1].strip()) if '|' in h else ('', h)
            wl = _well(key)
            out.append([fname, kind, pid, cell.strip(), key, wl, gate, stat, h, _num(v),
                        (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)), f'{kind}|{pid}|{wl or ""}|{stat}'])
    return out


# ------------------------------------------------------------------ workbook ----------------------------------------
def build(out, example=None):
    ex = example or {}
    wb = Workbook()

    # ============ README ============
    ws = wb.active; ws.title = 'README'
    txt = [
        ('qFACS antigen quantitation - BD QuantiBRITE PE (Cat. 340495) - Excel-only workbook, one 96-well plate per workbook', TITLE),
        ('Yellow = input · orange = manual override (leave blank to use imported value) · grey = calculated (do not edit).', None), ('', None),
        ('How it works', Font(bold=True, size=12)),
        ('1. Save this workbook INTO the experiment Analysis folder that holds the FlowJo table exports for the plate (plus the bead export).', None),
        ('2. On open, Power Query (query "qFACS_Import", refresh-on-open) reads every .xls/.csv/.txt export in that folder into the hidden Import sheet.', None),
        ('   Files whose name contains "bead" are bead exports; all others are cell exports named "<PlateID> <CellLine>.xls" (e.g. "Plate1 H1975.xls").', None),
        ('3. All maths is in formulas: bead curve (Bead_Std) -> per-well PE/cell, ABC, isotype subtraction (Wells) -> one-site fit per plate row (Fit) -> Summary.', None),
        ('4. Check Setup (Plate ID, PE detector, folder status), Antibody_Panel (F/P, isotype, MW, valency) and Plate_Map. Then read Summary.', None),
        ('   If Power Query is blocked or a value is wrong, type the value in the orange override columns (Wells gMFI, Bead_Std gMFI, Plate_Map cell line).', None),
        ('   To drop a well from the fit, put Y in Wells column "Exclude?".', None), ('', None),
        ('Equations', Font(bold=True, size=12)),
        ('Bead curve: log10(bead gMFI) = m·log10(PE/bead) + c (4 QuantiBRITE peaks);  PE/cell = 10^((log10 gMFI − c)/m)', None),
        ('ABC = (PE/cell − PE/cell of the same plate row\'s column-12 no-antibody well) / F:P   (column-12 wells show their PE/cell)', None),
        ('Isotype ABC = ABC of the matched isotype row (same cell line), linearly interpolated at the same concentration on the log-dilution index', None),
        ('Specific ABC = ABC − isotype ABC;  Antigens/cell = Bmax × valency factor (default 1 = ABC reported)', None),
        ('One-site fit: Specific ABC = Bmax·C/(Kd + C).  For any Kd the least-squares Bmax is exact: Bmax(Kd) = Σw·y·f / Σw·f², f = C/(Kd+C) (Bmax ≥ 0).', None),
        ('   Kd is found on a log grid: stage 1 = 241 points from top×1e-4 to top×1e2; stage 2 = 101 points ±0.025 decade around the stage-1 minimum;', None),
        ('   final = parabolic vertex of the 3 lowest stage-2 points (sheet Fit_Grid, hidden).', None),
        ('   SE from (JᵀJ)⁻¹·s², s² = SSE/(n−2), J = [f, −Bmax·C/(Kd+C)²];  95% CI = estimate ± TINV(0.05, n−2)·SE.  Reproduces scipy curve_fit.', None),
        ('   Kd(nM) = Kd(µg/mL)·1000 / MW(kDa).  ND when Bmax − t·SE ≤ 0, max specific ABC ≤ 0 or R² < 0.', None), ('', None),
        ('Flags', Font(bold=True, size=12)),
        ('Plateau: top conc ≥ k×Kd (Setup, default 5) else "NOT saturated - Bmax extrapolated".  Fit: poor fit (R² < 0.9), Bmax SE > 25 %, Kd at grid bound,', None),
        ('no matched isotype.  Bead range: top-concentration gMFI outside Low..High bead peaks (extrapolated).  Wells: bead range, low live events, import issues.', None), ('', None),
        ('Caveats', Font(bold=True, size=12)),
        (' - Bead lot 42618 EXPIRED 2022-10-31: absolute values are provisional; relative comparisons within a run remain valid.', None),
        (' - ABC counts antibodies, not antigens (bivalent IgG binding can give up to 2× more antigens; enter valency only when supported).', None),
        (' - Absolute ABC assumes the entered F:P (PE:mAb). BioLegend F/P unknown here (assumed 1). DLL3 reagent is a rabbit-Fc chimera vs mouse IgG1 isotype.', None),
        (' - Kd is an apparent, cell-based value (avidity, ligand depletion and wash dissociation not modelled).', None),
        (' - Excel limit: full path + file name ≤ 218 characters (Setup shows the current length).', None), ('', None),
        ('One-time Power Query setup (master template only; copies inherit it) - see sheet PQ_Setup.', Font(bold=True, size=12)),
    ]
    for i, (l, f) in enumerate(txt, 1):
        c = ws.cell(i, 1, l)
        if f: c.font = f
    ws.column_dimensions['A'].width = 160

    # ============ Setup ============
    s = wb.create_sheet('Setup'); s['A1'] = 'Experiment setup'; s['A1'].font = TITLE
    exs = ex.get('setup', {})
    setup = [  # row, label, default, defined name, note
        (3, 'Experiment ID', exs.get('exp', ''), None, ''),
        (4, 'Date (yyyy-mm-dd)', exs.get('date', ''), 'ExpDate', ''),
        (5, 'Operator', '', None, ''),
        (6, 'Instrument', 'BD FACSDiscover A8', None, ''),
        (7, 'Plate ID (file-name prefix; blank = all cell exports in folder)', exs.get('plate', ''), 'PlateID',
         'Exports "<PlateID> <CellLine>.xls" are used; other plates in the same folder are ignored.'),
        (8, 'PE detector / parameter (as in FlowJo header)', 'B5 (575)-A', 'PEdet', 'Matched to "Geometric Mean (<detector>)".'),
        (9, 'PE gate path (optional; blank = auto per plate row)', '', 'PEgate',
         'e.g. Cells/Single Cells/Live. Needed only if an export holds several PE Geometric Mean columns.'),
        (10, 'Bead file name contains', 'bead', 'BeadKey', 'Selects the bead export among files whose name contains "bead".'),
        (11, 'PE detector voltage / gain', '', None, ''),
        (12, 'Cell gating', 'Cells > Single Cells > Live', None, ''),
        (13, 'Staining buffer / temp / time', '', None, ''),
        (14, 'Bead kit', 'BD QuantiBRITE PE, Cat. 340495', None, ''),
        (15, 'Bead lot #', '42618', 'BeadLot', ''),
        (16, 'Bead lot expiry (yyyy-mm-dd)', '2022-10-31', 'BeadExpiry', ''),
        (17, 'Cells fixed before acquisition? (Y/N)', 'N', None, ''),
        (18, 'Min live events per well (QC)', 1000, 'MinEvents', 'Needs a live-gate Count column in the FlowJo export.'),
        (19, 'Bead fit R² minimum (QC)', 0.98, 'MinR2', ''),
        (20, 'Default antibody MW (kDa) for Kd in nM', 150, 'DefMW', ''),
        (21, 'Plateau criterion: top conc ≥ k × Kd (k)', 5, 'SatK', ''),
        (23, 'Folder override (optional: full local path or https:// folder URL)', '', 'FolderOverride', 'Leave blank normally.'),
    ]
    for r, lab, dflt, nm, note in setup:
        s.cell(r, 1, lab).font = Font(bold=True); inp(s.cell(r, 2), dflt)
        if note: s.cell(r, 3, note).font = Font(italic=True, color='808080')
        if nm: name(wb, nm, f'Setup!$B${r}')
    s['A22'] = 'Data source'; s['A22'].font = Font(bold=True, size=12)
    calc_rows = [
        (24, 'This workbook (from CELL("filename"))', 'IFERROR(SUBSTITUTE(LEFT(CELL("filename",$A$1),FIND("]",CELL("filename",$A$1))-1),"[",""),"(save the workbook first)")', None),
        (25, 'Folder detected', 'IFERROR(LEFT(CELL("filename",$A$1),FIND("[",CELL("filename",$A$1))-1),"")', None),
        (26, 'Folder used by Power Query', 'IF(TRIM(FolderOverride)<>"",TRIM(FolderOverride),B25)', 'PQ_Folder'),
        (27, 'Source type', 'IF(B26="","-",IF(LEFT(LOWER(B26),4)="http","SharePoint/OneDrive (org sign-in once)","Local / network folder"))', None),
        (28, 'Path + file name length (Excel max 218)', 'IF(LEFT(B24,1)="(","",LEN(B24))', None),
        (29, 'Import rows loaded', 'COUNTA(IM_File)', 'ImportRows'),
        (30, 'Last refresh', 'IF(COUNT(IM_Loaded)=0,"never (static data or not refreshed)",MAX(IM_Loaded))', None),
        (31, 'Cell-export rows for this Plate ID', 'IF(PlateID="",COUNTIF(IM_Kind,"cells"),COUNTIFS(IM_Kind,"cells",IM_Plate,PlateID))', None),
        (32, 'Bead-export rows', 'COUNTIFS(IM_Kind,"bead",IM_File,"*"&BeadKey&"*")', None),
        (33, 'Files that could not be parsed', 'COUNTIF(IM_Header,"PARSE ERROR")', None),
    ]
    for r, lab, f, nm in calc_rows:
        s.cell(r, 1, lab).font = Font(bold=True); cal(s.cell(r, 2), '=' + f)
        if nm: name(wb, nm, f'Setup!$B${r}')
    s['B30'].number_format = 'yyyy-mm-dd hh:mm'
    s['C16'] = '=IFERROR(IF(OR(ExpDate="",DATEVALUE(ExpDate)>DATEVALUE(BeadExpiry)),"WARNING: bead lot expired before/at use - absolute ABC provisional",""),"WARNING: bead lot expiry - check dates")'
    s['C17'] = '=IF(UPPER(B17)="Y","Fixation can reduce PE signal / quantitation (BD Limitations)","")'
    s['C28'] = '=IF(N(B28)>218,"TOO LONG: Excel cannot save/open reliably - shorten folder names",IF(N(B28)>200,"close to limit",""))'
    s['C29'] = f'=IF(B29>={IMAX - 1},"Import exceeds {IMAX} rows - extend IM_ ranges","")'
    s['C31'] = '=IF(B31=0,"No cell exports found for this Plate ID - check file names / folder / refresh","")'
    s['C32'] = '=IF(B32=0,"No bead export found (file name must contain the bead key)","")'
    s['C33'] = '=IF(B33>0,"Check Import sheet: rows with Header = PARSE ERROR","")'
    for c in ('C16', 'C17', 'C28', 'C29', 'C31', 'C32', 'C33'): s[c].font = WARN
    s.column_dimensions['A'].width = 58; s.column_dimensions['B'].width = 48; s.column_dimensions['C'].width = 80
    dv = DataValidation(type='list', formula1='"Y,N"', allow_blank=True); s.add_data_validation(dv); dv.add('B17')

    # ============ Antibody_Panel ============
    p = wb.create_sheet('Antibody_Panel'); p['A1'] = 'Reagent panel (PE conjugates incl. isotype controls)'; p['A1'].font = TITLE
    p['A2'] = 'Name = ID used in Plate_Map. Isotype? = Y for isotype controls. Matched isotype = Name of the isotype row subtracted from this antibody.'
    pcols = ['Name (plate-map ID)', 'Target antigen', 'Isotype? (Y/N)', 'Clone', 'Vendor', 'Catalog #', 'Lot #', 'Host / isotype',
             'F/P ratio (PE:mAb)', 'F/P source', 'MW (kDa)', 'Valency factor', 'Valency source', 'Matched isotype (Name)', 'Notes']
    hdr(p, 4, 1, pcols, 32)
    pan = ex.get('panel', [])
    for i in range(NAB):
        r = 5 + i; vals = pan[i] if i < len(pan) else {}
        dfl = {3: 'N', 9: 1, 10: 'assumed 1:1', 11: '=DefMW', 12: 1, 13: 'assumed (ABC reported)'} if (vals or i == 0) else {}
        for cc in range(1, 16):
            v = vals.get(cc) if vals.get(cc) not in (None, '') else dfl.get(cc)
            inp(p.cell(r, cc), v)
    for i, w in enumerate([16, 15, 9, 11, 16, 16, 12, 16, 10, 22, 9, 9, 20, 15, 40], 1): p.column_dimensions[COL(i)].width = w
    for nm, c in [('P_Name', 'A'), ('P_Target', 'B'), ('P_Iso', 'C'), ('P_Clone', 'D'), ('P_Cat', 'F'), ('P_Lot', 'G'),
                  ('P_FP', 'I'), ('P_MW', 'K'), ('P_Val', 'L'), ('P_MatchIso', 'N')]:
        name(wb, nm, f'Antibody_Panel!${c}$5:${c}${4 + NAB}')
    dvy = DataValidation(type='list', formula1='"Y,N"', allow_blank=True); p.add_data_validation(dvy); dvy.add(f'C5:C{4 + NAB}')
    dvi = DataValidation(type='list', formula1='=P_Name', allow_blank=True); p.add_data_validation(dvi); dvi.add(f'N5:N{4 + NAB}')

    # ============ Plate_Map ============
    m = wb.create_sheet('Plate_Map'); m['A1'] = 'Plate map - one row per plate row (columns 1-11 serial dilution, column 12 no antibody)'; m['A1'].font = TITLE
    m['A2'] = 'Cell line is taken from the export file name "<PlateID> <CellLine>" holding that plate row; type in the orange column to override.'
    hdr(m, 4, 1, ['Plate row', 'Cell line (from file name)', 'Cell line override', 'Cell line used', 'Antibody (Name)',
                  'Top conc, col 1 (µg/mL final)', 'Transfer vol (µL)', 'Diluent vol in wells (µL)', 'Dilution factor', 'Isotype?',
                  'Matched isotype plate row #', 'key', 'PE gate used', 'Source export'], 45)
    pm = ex.get('platemap', {})
    pk = '"cells|"&IF(PlateID="","*",PlateID)&"|"'
    for i, L in enumerate(ROWS):
        r = 5 + i; v = pm.get(L, {})
        m.cell(r, 1, L).font = Font(bold=True)
        cal(m.cell(r, 2), f'=IFERROR(INDEX(IM_Cell,MATCH({pk}&$A{r}&"??|*",IM_Key,0)),"")')
        inp(m.cell(r, 3), v.get('cell_override'), OVR)
        cal(m.cell(r, 4), f'=IF(TRIM(C{r})<>"",TRIM(C{r}),B{r})')
        inp(m.cell(r, 5), v.get('ab')); inp(m.cell(r, 6), v.get('top')); inp(m.cell(r, 7), v.get('xfer', 125)); inp(m.cell(r, 8), v.get('dil', 100))
        cal(m.cell(r, 9), f'=IF(N(G{r})>0,(G{r}+H{r})/G{r},"")', '0.000')
        cal(m.cell(r, 10), f'=IF(E{r}="","",IFERROR(IF(UPPER(INDEX(P_Iso,MATCH(E{r},P_Name,0)))="Y","Y","N"),"not in panel"))')
        cal(m.cell(r, 11), f'=IF(OR(D{r}="",E{r}="",J{r}<>"N"),"",IFERROR(MATCH(D{r}&"|"&INDEX(P_MatchIso,MATCH(E{r},P_Name,0)),$L$5:$L$12,0),"none"))')
        m.cell(r, 12, f'=D{r}&"|"&E{r}').font = Font(color='A0A0A0')
        cal(m.cell(r, 13), f'=IF(PEgate<>"",PEgate,IFERROR(INDEX(IM_Gate,MATCH({pk}&$A{r}&"??|Geometric Mean*"&PEdet&"*",IM_Key,0)),""))')
        cal(m.cell(r, 14), f'=IFERROR(INDEX(IM_File,MATCH({pk}&$A{r}&"??|*",IM_Key,0)),"")')
    m['A14'] = 'Dilution factor = (transfer + diluent) / transfer, e.g. 125 µL into 100 µL → 225/125 = 1.8.'; m['A14'].font = Font(italic=True)
    dva = DataValidation(type='list', formula1='=P_Name', allow_blank=True); m.add_data_validation(dva); dva.add('E5:E12')
    for nm, c in [('PM_Cell', 'D'), ('PM_Ab', 'E'), ('PM_Top', 'F'), ('PM_DF', 'I'), ('PM_IsoFlag', 'J'), ('PM_IsoRow', 'K'), ('PM_Gate', 'M')]:
        name(wb, nm, f'Plate_Map!${c}$5:${c}$12')
    m['A16'] = 'Final concentration grid (µg/mL)'; m['A16'].font = Font(bold=True, size=12)
    hdr(m, 17, 1, ['Row'] + [str(k) for k in range(1, 13)] + ['Label'])
    for i, L in enumerate(ROWS):
        r = 18 + i; pr = 5 + i
        m.cell(r, 1, L).font = Font(bold=True)
        for k in range(1, 12):
            cal(m.cell(r, 1 + k), f'=IF(OR(N($F{pr})=0,N($I{pr})=0),"",$F{pr}/$I{pr}^{k - 1})', '0.000')
        cal(m.cell(r, 13), f'=IF(N($F{pr})=0,"","bkg")'); cal(m.cell(r, 14), f'=IF(E{pr}="","",D{pr}&" "&E{pr})')
    for c, w in zip('ABCDEFGHIJKLMN', (9, 16, 14, 14, 14, 13, 10, 11, 10, 10, 11, 4, 24, 22)): m.column_dimensions[c].width = w
    m.column_dimensions['L'].hidden = True

    # ============ Bead_Std ============
    b = wb.create_sheet('Bead_Std'); b['A1'] = 'QuantiBRITE PE standard curve'; b['A1'].font = TITLE
    b['A2'] = 'Bead peak gMFI is pulled from the bead export by gate name (FlowJo gate ".../<gate name>"). PE/bead pre-filled for lot 42618.'
    hdr(b, 4, 1, ['Bead level', 'FlowJo gate name', 'PE molecules / bead (lot)', 'gMFI (imported)', 'Import matches', 'gMFI override',
                  'gMFI used', 'log10 PE/bead', 'log10 gMFI', 'Back-calc. PE/bead', '% recovery'], 32)
    bstat = '"Geometric Mean*"&PEdet&"*"'; bfile = '"*"&BeadKey&"*"'
    for i, (lv, gate, pe) in enumerate(BEADS):
        r = 5 + i; b.cell(r, 1, lv).font = Font(bold=True)
        inp(b.cell(r, 2), gate); inp(b.cell(r, 3), pe)
        cal(b.cell(r, 4), f'=IFERROR(AVERAGEIFS(IM_Num,IM_Kind,"bead",IM_File,{bfile},IM_Gate,"*/"&B{r},IM_Stat,{bstat}),'
                          f'IFERROR(AVERAGEIFS(IM_Num,IM_Kind,"bead",IM_File,{bfile},IM_Gate,B{r},IM_Stat,{bstat}),""))', '#,##0')
        cal(b.cell(r, 5), f'=COUNTIFS(IM_Kind,"bead",IM_File,{bfile},IM_Gate,"*/"&B{r},IM_Stat,{bstat})+COUNTIFS(IM_Kind,"bead",IM_File,{bfile},IM_Gate,B{r},IM_Stat,{bstat})')
        inp(b.cell(r, 6), None, OVR)
        cal(b.cell(r, 7), f'=IF(N(F{r})>0,F{r},IF(N(D{r})>0,D{r},""))', '#,##0')
        cal(b.cell(r, 8), f'=IF(N(C{r})>0,LOG10(C{r}),NA())', '0.0000'); cal(b.cell(r, 9), f'=IF(N(G{r})>0,LOG10(G{r}),NA())', '0.0000')
        cal(b.cell(r, 10), f'=IFERROR(10^((I{r}-Intercept)/Slope),"")', '#,##0'); cal(b.cell(r, 11), f'=IFERROR(J{r}/C{r},"")', '0.0%')
    fitrows = [('Slope (m)', '=IFERROR(SLOPE(I5:I8,H5:H8),"")', '0.0000', 'Slope'),
               ('Intercept (c)', '=IFERROR(INTERCEPT(I5:I8,H5:H8),"")', '0.0000', 'Intercept'),
               ('R²', '=IFERROR(RSQ(I5:I8,H5:H8),"")', '0.00000', 'BeadR2'),
               ('Lowest bead gMFI', '=IF(COUNT(G5:G8)=4,MIN(G5:G8),"")', '#,##0', 'BeadMin'),
               ('Highest bead gMFI', '=IF(COUNT(G5:G8)=4,MAX(G5:G8),"")', '#,##0', 'BeadMax'),
               ('Curve QC', '=IF(COUNT(G5:G8)<4,"Enter / import all 4 bead gMFIs",IF(AND(B13>=MinR2,MIN(K5:K8)>=0.8,MAX(K5:K8)<=1.2),"PASS","CHECK: R² < min or a bead recovery outside 80-120%"))', None, 'BeadQC'),
               ('Import check', '=IF(MAX(E5:E8)>1,"several bead tubes/files matched - values averaged; set Setup bead key",IF(MIN(E5:E8)=0,"a bead gate was not found - check gate names / override","OK"))', None, None)]
    for i, (k, f, fmt, nm) in enumerate(fitrows, 11):
        b.cell(i, 1, k).font = Font(bold=True); cal(b.cell(i, 2), f, fmt)
        if nm: name(wb, nm, f'Bead_Std!$B${i}')
    b['A19'] = 'Self-check vs BD data-sheet example (gMFI 500, y = 0.99707x − 1.7247 → 27,332):'; cal(b['B19'], '=10^((LOG10(500)+1.7247)/0.99707)', '#,##0')
    b['A20'] = 'Bead gating: FSC-H vs SSC-H singlets → PE histogram → geometric mean of each peak. Same PE voltage & compensation as cells.'
    for i, w in enumerate([18, 16, 14, 14, 10, 13, 13, 12, 12, 14, 11], 1): b.column_dimensions[COL(i)].width = w
    b.column_dimensions['A'].width = 22
    b.conditional_formatting.add('B16', FormulaRule(formula=['$B$16="PASS"'], fill=GRN))
    b.conditional_formatting.add('B16', FormulaRule(formula=['LEFT($B$16,5)="CHECK"'], fill=RED))
    b.conditional_formatting.add('B17', FormulaRule(formula=['$B$17<>"OK"'], fill=RED))

    # ============ Wells ============
    w = wb.create_sheet('Wells'); w['A1'] = 'Per-well data and calculations'; w['A1'].font = TITLE
    w['A2'] = 'gMFI imported from Import (live gate Geometric Mean of the PE detector). Orange = manual override / exclusion.'
    wcols = ['Well', 'Row', 'Col', 'Row #', 'Cell line', 'Antibody', 'Conc (µg/mL)', 'Isotype?', 'gMFI (imported)', 'Import matches',
             'gMFI override', 'gMFI used', 'Live events', 'Exclude from fit? (Y)', 'PE/cell', 'ABC = (PE − col-12 PE)/F:P [col 12: PE]',
             'Isotype ABC @ conc', 'Specific ABC', 'Antigens/cell (× valency)', 'Bead-range flag', 'Events flag', 'Isotype flag', 'Import flag',
             'h:iso row', 'h:k*', 'h:k1', 'plot log10 PE', 'plot log10 gMFI']
    hdr(w, 4, 1, wcols, 45)
    W0, W1 = 5, 100
    stat = '"Geometric Mean*"&PEdet&"*"'; pcrit = 'IF(PlateID="","*",PlateID)'
    ovr = ex.get('well_override', {})
    for i in range(96):
        r = W0 + i; well = f'{ROWS[i // 12]}{i % 12 + 1:02d}'
        g = f'INDEX(PM_Gate,D{r})'
        crit = f'IM_Kind,"cells",IM_Well,A{r},IM_Gate,{g},IM_Plate,{pcrit}'
        F = {1: well,
             2: f'=LEFT(A{r},1)', 3: f'=VALUE(MID(A{r},2,2))', 4: f'=CODE(B{r})-64',
             5: f'=INDEX(PM_Cell,D{r})&""',
             6: f'=IF(INDEX(PM_Ab,D{r})&""="","",IF(C{r}=12,"bkg",INDEX(PM_Ab,D{r})&""))',
             7: f'=IF(OR(F{r}="",N(INDEX(PM_Top,D{r}))=0,N(INDEX(PM_DF,D{r}))=0),"",IF(C{r}=12,0,INDEX(PM_Top,D{r})/INDEX(PM_DF,D{r})^(C{r}-1)))',
             8: f'=IF(F{r}="","",IF(C{r}=12,"bkg",IFERROR(IF(UPPER(INDEX(P_Iso,MATCH(F{r},P_Name,0)))="Y","Y","N"),"N")))',
             9: f'=IFERROR(AVERAGEIFS(IM_Num,{crit},IM_Stat,{stat}),"")',
             10: f'=COUNTIFS({crit},IM_Stat,{stat})',
             12: f'=IF(N(K{r})>0,K{r},IF(N(I{r})>0,I{r},""))',
             13: f'=IFERROR(AVERAGEIFS(IM_Num,{crit},IM_Stat,"Count"),"")',
             15: f'=IF(L{r}="","",IFERROR(10^((LOG10(L{r})-Intercept)/Slope),""))',
             16: f'=IF(O{r}="","",IF(C{r}=12,O{r},(O{r}-N(INDEX($O${W0}:$O${W1},(D{r}-1)*12+12)))/IFERROR(INDEX(P_FP,MATCH(F{r},P_Name,0)),1)))',
             24: f'=IF(OR(H{r}<>"N",G{r}=""),"",IF(ISNUMBER(INDEX(PM_IsoRow,D{r})),INDEX(PM_IsoRow,D{r}),""))',
             25: f'=IF(X{r}="","",IFERROR(MIN(MAX(1+LN(INDEX(PM_Top,X{r})/G{r})/LN(INDEX(PM_DF,X{r})),1),11),""))',
             26: f'=IF(Y{r}="","",MIN(INT(Y{r}+1E-9),10))',
             17: f'=IF(Z{r}="","",IFERROR(INDEX($P${W0}:$P${W1},(X{r}-1)*12+Z{r})+(Y{r}-Z{r})*(INDEX($P${W0}:$P${W1},(X{r}-1)*12+Z{r}+1)-INDEX($P${W0}:$P${W1},(X{r}-1)*12+Z{r})),""))',
             18: f'=IF(OR(P{r}="",H{r}<>"N"),"",IF(Q{r}="",P{r},P{r}-Q{r}))',
             19: f'=IF(R{r}="","",R{r}*IFERROR(INDEX(P_Val,MATCH(F{r},P_Name,0)),1))',
             20: f'=IF(L{r}="","",IF(BeadMin="","no bead curve",IF(L{r}<BeadMin,"Below Low bead",IF(L{r}>BeadMax,"Above High bead","OK"))))',
             21: f'=IF(L{r}="","",IF(M{r}="","no count",IF(M{r}<MinEvents,"Low events","OK")))',
             22: f'=IF(R{r}="","",IF(X{r}="","No matched isotype - not subtracted",IF(G{r}>INDEX(PM_Top,X{r})*1.0001,"Conc above isotype range",IF(Q{r}="","Isotype data missing","OK"))))',
             23: f'=IF(F{r}="","",IF(N(K{r})>0,"manual override",IF(J{r}=0,"no data imported",IF(J{r}>1,"several matches ("&J{r}&") averaged - check duplicates / PE gate","OK"))))',
             27: f'=IF(O{r}="",NA(),LOG10(O{r}))', 28: f'=IF(O{r}="",NA(),LOG10(L{r}))'}
        for cc, f in F.items():
            c = w.cell(r, cc, f)
            if cc == 1: c.font = Font(bold=True)
            else: c.fill = CAL
        inp(w.cell(r, 11), ovr.get(well), OVR); inp(w.cell(r, 14), None, OVR)
        for cc in (9, 12, 15, 16, 17, 18, 19): w.cell(r, cc).number_format = '#,##0'
        w.cell(r, 7).number_format = '0.000'; w.cell(r, 13).number_format = '#,##0'
    for c in ('X', 'Y', 'Z', 'AA', 'AB'): w.column_dimensions[c].hidden = True
    for i, wd in enumerate([6, 5, 5, 6, 11, 10, 10, 8, 11, 8, 11, 11, 9, 9, 11, 13, 11, 11, 12, 15, 10, 18, 22], 1): w.column_dimensions[COL(i)].width = wd
    w.freeze_panes = 'B5'
    w.conditional_formatting.add(f'T{W0}:W{W1}', FormulaRule(formula=[f'AND(T{W0}<>"",T{W0}<>"OK")'], fill=RED))
    dvx = DataValidation(type='list', formula1='"Y"', allow_blank=True); w.add_data_validation(dvx); dvx.add(f'N{W0}:N{W1}')
    # bead chart with wells overlay
    ch = ScatterChart(); ch.title = 'QuantiBRITE PE standard curve (beads + wells)'; ch.style = 13
    ch.x_axis.title = 'log10 PE molecules'; ch.y_axis.title = 'log10 PE gMFI'
    s1 = Series(Reference(b, min_col=9, min_row=5, max_row=8), Reference(b, min_col=8, min_row=5, max_row=8), title='Beads')
    s1.marker = Marker('circle', size=8); s1.graphicalProperties.line.noFill = True
    s2 = Series(Reference(w, min_col=28, min_row=W0, max_row=W1), Reference(w, min_col=27, min_row=W0, max_row=W1), title='Wells')
    s2.marker = Marker('triangle', size=5); s2.graphicalProperties.line.noFill = True
    ch.series += [s1, s2]; ch.x_axis.delete = False; ch.y_axis.delete = False; ch.height = 9; ch.width = 16
    b.add_chart(ch, 'M3')

    # ============ Fit_Data (hidden) ============
    fd = wb.create_sheet('Fit_Data'); fd['A1'] = 'Fit input arrays per plate row (x = conc, y = specific ABC, w = include 1/0)'; fd['A1'].font = TITLE
    hdr(fd, 4, 1, ['Row'] + [f'x{k}' for k in range(1, 12)] + [''] + [f'y{k}' for k in range(1, 12)] + [''] + [f'w{k}' for k in range(1, 12)]
        + ['', '', 'fit?', 'n', 'x max', 'Σw·y²'])
    for d, L in enumerate(ROWS):
        r = 5 + d; fd.cell(r, 1, L)
        for k in range(11):
            wr = W0 + d * 12 + k
            fd.cell(r, 2 + k, f'=IF(ISNUMBER(Wells!G{wr}),Wells!G{wr},1)')
            fd.cell(r, 26 + k, f'=IF(AND(INDEX(PM_IsoFlag,{d + 1})="N",ISNUMBER(Wells!R{wr}),ISNUMBER(Wells!G{wr}),UPPER(Wells!N{wr})<>"Y"),1,0)')
            fd.cell(r, 14 + k, f'=IF({COL(26 + k)}{r}=1,Wells!R{wr},0)')
        fd.cell(r, 39, f'=AND(INDEX(PM_IsoFlag,{d + 1})="N",AN{r}>=2)')
        fd.cell(r, 40, f'=SUM(Z{r}:AJ{r})')
        fd.cell(r, 41, f'=IF(AN{r}=0,1,SUMPRODUCT(MAX(B{r}:L{r}*Z{r}:AJ{r})))')
        fd.cell(r, 42, f'=SUMPRODUCT(Z{r}:AJ{r},N{r}:X{r},N{r}:X{r})')
    X = lambda r: f'Fit_Data!$B${r}:$L${r}'; Y = lambda r: f'Fit_Data!$N${r}:$X${r}'; Wt = lambda r: f'Fit_Data!$Z${r}:$AJ${r}'

    # ============ Fit_Grid (hidden) ============
    fg = wb.create_sheet('Fit_Grid'); fg['A1'] = 'Kd grid search per plate row: SSE(Kd) with exact least-squares Bmax(Kd) = MAX(0, Σwyf/Σwf²)'; fg['A1'].font = TITLE
    fg['A2'] = f'Stage 1: {NG1} log-spaced Kd from xmax·1e-4 to xmax·1e2 (rows {G1R0}-{G1R0 + NG1 - 1}); stage 2: {NG2} points ±0.025 decade (rows {G2R0}-{G2R0 + NG2 - 1}); then parabolic vertex.'
    for d, L in enumerate(ROWS):
        c0 = 1 + 5 * d; r = 5 + d
        A, B_, C_, D_ = (COL(c0 + j) for j in range(4))
        fg.cell(4, c0, f'Row {L}: log10 Kd'); fg.cell(4, c0 + 1, 'Σwyf'); fg.cell(4, c0 + 2, 'Σwf²'); fg.cell(4, c0 + 3, 'SSE')
        for blk, (r0, n, start) in enumerate([(G1R0, NG1, None), (G2R0, NG2, None)]):
            for j in range(n):
                gr = r0 + j
                if blk == 0:
                    lk = f'=IF(Fit_Data!$AM${r},LOG10(Fit_Data!$AO${r})-4+{6 * j / (NG1 - 1)!r},"")'
                else:
                    lk = f'=IF(Fit_Data!$AM${r},${A}${GSR + 1}-0.025+{0.05 * j / (NG2 - 1)!r},"")'
                fg[f'{A}{gr}'] = lk
                fx = f'{X(r)}/(10^{A}{gr}+{X(r)})'
                fg[f'{B_}{gr}'] = f'=IF({A}{gr}="","",SUMPRODUCT({Wt(r)}*{Y(r)}*{fx}))'
                fg[f'{C_}{gr}'] = f'=IF({A}{gr}="","",SUMPRODUCT({Wt(r)}*({fx})^2))'
                bb = f'MAX(0,{B_}{gr}/{C_}{gr})'
                fg[f'{D_}{gr}'] = f'=IF({A}{gr}="","",IFERROR(Fit_Data!$AP${r}-2*{bb}*{B_}{gr}+{bb}^2*{C_}{gr},""))'
        s1r = f'${D_}${G1R0}:${D_}${G1R0 + NG1 - 1}'; s2r = f'${D_}${G2R0}:${D_}${G2R0 + NG2 - 1}'
        a2r = f'${A}${G2R0}:${A}${G2R0 + NG2 - 1}'
        fg.cell(GSR, c0, 'stage-1 argmin'); fg[f'{B_}{GSR}'] = f'=IFERROR(MATCH(MIN({s1r}),{s1r},0),"")'
        fg[f'{A}{GSR + 1}'] = f'=IFERROR(INDEX(${A}${G1R0}:${A}${G1R0 + NG1 - 1},{B_}{GSR}),"")'; fg.cell(GSR + 1, c0 + 1, '← stage-1 log Kd')
        fg.cell(GSR + 2, c0, 'stage-2 argmin'); fg[f'{B_}{GSR + 2}'] = f'=IFERROR(MATCH(MIN({s2r}),{s2r},0),"")'
        m_ = f'{B_}{GSR + 2}'
        fg.cell(GSR + 3, c0, 'parabola δ'); fg[f'{B_}{GSR + 3}'] = (
            f'=IFERROR(IF(OR({m_}<=1,{m_}>={NG2}),0,0.5*{0.05 / (NG2 - 1)!r}*(INDEX({s2r},{m_}-1)-INDEX({s2r},{m_}+1))'
            f'/(INDEX({s2r},{m_}-1)-2*INDEX({s2r},{m_})+INDEX({s2r},{m_}+1))),0)')
        fg.cell(GSR + 4, c0, 'final log10 Kd'); fg[f'{B_}{GSR + 4}'] = f'=IFERROR(INDEX({a2r},{m_})+MAX(-{0.05 / (NG2 - 1)!r},MIN({0.05 / (NG2 - 1)!r},{B_}{GSR + 3})),"")'
        fg.cell(GSR + 5, c0, 'at grid bound?'); fg[f'{B_}{GSR + 5}'] = f'=IF({B_}{GSR}="","",OR({B_}{GSR}=1,{B_}{GSR}={NG1}))'

    # ============ Fit ============
    ft = wb.create_sheet('Fit'); ft['A1'] = 'One-site binding fit per plate row: Specific ABC = Bmax·C/(Kd + C)  (live formulas)'; ft['A1'].font = TITLE
    ft['A2'] = 'Grid search on Kd with exact least-squares Bmax; SE from Jacobian; 95% CI = ± TINV(0.05, n−2)·SE. Isotype rows are not fitted.'
    fcols = ['Plate row', 'Cell line', 'Antibody', 'Target', 'Clone', 'Catalog #', 'Lot #', 'Fitted?', 'n points', 'Bmax (ABC)', 'Bmax SE',
             'Bmax 95% CI low', 'Bmax 95% CI high', 'Kd (µg/mL)', 'Kd SE (µg/mL)', 'Kd 95% CI low', 'Kd 95% CI high', 'Kd (nM)', 'R²',
             'Top conc / Kd', 'Max observed specific ABC', 'Valency factor', 'Antigens/cell (Bmax × valency)', 'Plateau flag', 'Fit flag',
             'Top-conc bead-range flag', 'Status',
             'h:Kd', 'h:Syf', 'h:Sff', 'h:Bmax', 'h:SSE', 'h:SST', 'h:a', 'h:b', 'h:c', 'h:det', 'h:s²', 'h:t', 'h:ND', 'h:bound',
             'h:cell#', 'h:ab#', 'h:key', 'h:rank', 'h:MW']
    hdr(ft, 5, 1, fcols, 45)
    F0 = 6
    for d, L in enumerate(ROWS):
        r = F0 + d; fr_ = 5 + d; c0 = 1 + 5 * d; gB = COL(c0 + 1)
        x, y, wt = X(fr_), Y(fr_), Wt(fr_)
        ab = f'Plate_Map!$E${5 + d}'
        pl = lambda col: f'IFERROR(INDEX({col},MATCH($C{r},P_Name,0))&"","")'
        K = f'$AB{r}'; Bm = f'$AE{r}'
        fx = f'{x}/({K}+{x})'; j2 = f'{Bm}*{x}/({K}+{x})^2'
        F = {1: L, 2: f'=Plate_Map!$D${5 + d}', 3: f'={ab}&""', 4: '=' + pl('P_Target'), 5: '=' + pl('P_Clone'), 6: '=' + pl('P_Cat'),
             7: '=' + pl('P_Lot'),
             8: f'=Fit_Data!$AM${fr_}', 9: f'=Fit_Data!$AN${fr_}',
             28: f'=IF(AND(H{r},I{r}>=4),10^Fit_Grid!${gB}${GSR + 4},"")',
             29: f'=IF(AB{r}="","",SUMPRODUCT({wt}*{y}*{fx}))',
             30: f'=IF(AB{r}="","",SUMPRODUCT({wt}*({fx})^2))',
             31: f'=IF(AB{r}="","",MAX(0,AC{r}/AD{r}))',
             32: f'=IF(AB{r}="","",Fit_Data!$AP${fr_}-2*AE{r}*AC{r}+AE{r}^2*AD{r})',
             33: f'=IF(AB{r}="","",SUMPRODUCT({wt}*({y}-SUMPRODUCT({wt},{y})/I{r})^2))',
             34: f'=IF(AB{r}="","",AD{r})',
             35: f'=IF(AB{r}="","",-SUMPRODUCT({wt}*({fx})*({j2})))',
             36: f'=IF(AB{r}="","",SUMPRODUCT({wt}*({j2})^2))',
             37: f'=IF(AB{r}="","",AH{r}*AJ{r}-AI{r}^2)',
             38: f'=IF(AB{r}="","",AF{r}/(I{r}-2))',
             39: f'=IF(AB{r}="","",TINV(0.05,I{r}-2))',
             11: f'=IF(AB{r}="","",IFERROR(SQRT(AL{r}*AJ{r}/AK{r}),""))',
             15: f'=IF(AB{r}="","",IFERROR(SQRT(AL{r}*AH{r}/AK{r}),""))',
             19: f'=IF(AB{r}="","",IF(AG{r}>0,1-AF{r}/AG{r},""))',
             21: f'=IF(I{r}=0,"",SUMPRODUCT(MAX({y}-(1-{wt})*1E+300)))',
             40: f'=IF(AB{r}="","",IFERROR(OR(AE{r}-AM{r}*K{r}<=0,U{r}<=0,S{r}<0),TRUE))',
             41: f'=IF(AB{r}="","",Fit_Grid!${gB}${GSR + 5})',
             10: f'=IF(OR(AB{r}="",AN{r}=TRUE),"",AE{r})',
             12: f'=IF(J{r}="","",J{r}-AM{r}*K{r})', 13: f'=IF(J{r}="","",J{r}+AM{r}*K{r})',
             14: f'=IF(J{r}="","",AB{r})',
             16: f'=IF(J{r}="","",MAX(N{r}-AM{r}*O{r},0))', 17: f'=IF(J{r}="","",N{r}+AM{r}*O{r})',
             46: f'=IFERROR(INDEX(P_MW,MATCH($C{r},P_Name,0)),DefMW)',
             18: f'=IF(J{r}="","",N{r}*1000/IF(N(AT{r})>0,AT{r},DefMW))',
             20: f'=IF(J{r}="","",Fit_Data!$AO${fr_}/N{r})',
             22: f'=IF(H{r},IFERROR(INDEX(P_Val,MATCH($C{r},P_Name,0)),1),"")',
             23: f'=IF(J{r}="","",J{r}*V{r})',
             24: f'=IF(J{r}="","",IF(T{r}>=SatK,"Plateau reached","NOT saturated (top conc < "&SatK&" x Kd) - Bmax extrapolated"))',
             25: (f'=IF(NOT(H{r}),"",IF(I{r}<4,"too few points",IF(AN{r}=TRUE,"ND - no specific binding above isotype"'
                  f'&IF(Plate_Map!$K${5 + d}="none","; no matched isotype - not subtracted",""),'
                  f'IF(MID(IF(Plate_Map!$K${5 + d}="none","; no matched isotype - not subtracted","")'
                  f'&IF(S{r}<0.9,"; poor fit (R² "&TEXT(S{r},"0.00")&")","")'
                  f'&IF(IFERROR(K{r}/J{r}>0.25,TRUE),"; Bmax imprecise (SE > 25%)","")'
                  f'&IF(AO{r}=TRUE,"; Kd at grid bound - check curve",""),3,999)="","OK",'
                  f'MID(IF(Plate_Map!$K${5 + d}="none","; no matched isotype - not subtracted","")'
                  f'&IF(S{r}<0.9,"; poor fit (R² "&TEXT(S{r},"0.00")&")","")'
                  f'&IF(IFERROR(K{r}/J{r}>0.25,TRUE),"; Bmax imprecise (SE > 25%)","")'
                  f'&IF(AO{r}=TRUE,"; Kd at grid bound - check curve",""),3,999)))))'),
             26: (f'=IF(NOT(H{r}),"",IF(NOT(ISNUMBER(Wells!L{W0 + d * 12})),"no data",IF(BeadMin="","no bead curve",'
                  f'IF(Wells!L{W0 + d * 12}<BeadMin,"Below Low bead",IF(Wells!L{W0 + d * 12}>BeadMax,"Above High bead (extrapolated)","OK")))))'),
             27: f'=IF(NOT(H{r}),IF(Plate_Map!$J${5 + d}="Y","isotype control",IF(C{r}="","empty","no data")),IF(J{r}<>"","fitted",IF(AN{r}=TRUE,"ND","not fitted")))',
             42: f'=IF(AND(H{r},COUNTIFS($B${F0}:B{r},B{r},$H${F0}:H{r},TRUE)=1),MAX($AP${F0 - 1}:AP{r - 1})+1,"")',
             43: f'=IF(AND(H{r},COUNTIFS($C${F0}:C{r},C{r},$H${F0}:H{r},TRUE)=1),MAX($AQ${F0 - 1}:AQ{r - 1})+1,"")',
             44: f'=B{r}&"|"&C{r}',
             45: f'=IF(H{r},COUNTIF($H${F0}:H{r},TRUE),"")'}
        for cc, f in F.items():
            c = ft.cell(r, cc, f)
            if cc > 1: c.fill = CAL; c.border = BOX
        for cc in (10, 11, 12, 13, 21, 23): ft.cell(r, cc).number_format = '#,##0'
        for cc in (14, 15, 16, 17, 18, 20): ft.cell(r, cc).number_format = '0.000'
        ft.cell(r, 19).number_format = '0.0000'
    ft.cell(F0 - 1, 42).value = 'h:cell#'  # header cell doubles as MAX() anchor (text ignored)
    for cc in range(28, 47): ft.column_dimensions[COL(cc)].hidden = True
    for i, wd in enumerate([7, 10, 10, 13, 10, 12, 10, 8, 7, 11, 9, 11, 11, 10, 10, 10, 10, 9, 8, 9, 12, 8, 13, 30, 34, 22, 12], 1):
        ft.column_dimensions[COL(i)].width = wd
    ft.conditional_formatting.add(f'X{F0}:Z{F0 + 7}', FormulaRule(formula=[f'AND(X{F0}<>"",X{F0}<>"Plateau reached",X{F0}<>"OK")'], fill=RED))
    ft.freeze_panes = 'D6'

    # ============ Plot_Data (hidden) + Plots ============
    pdt = wb.create_sheet('Plot_Data'); pdt['A1'] = 'Chart series (live)'; pdt['A1'].font = TITLE
    pl_ = wb.create_sheet('Plots'); pl_['A1'] = 'Titration curves: total, isotype and specific ABC with one-site fit (log concentration axis)'; pl_['A1'].font = TITLE
    for d, L in enumerate(ROWS):
        c0 = 1 + 6 * d; fr = F0 + d
        pdt.cell(3, c0, f'=Fit!A{fr}&": "&Fit!B{fr}&" "&Fit!C{fr}')
        for j, lab in enumerate(['Conc', 'total ABC', 'isotype ABC', 'specific ABC', 'fit conc', 'one-site fit']): pdt.cell(4, c0 + j, lab)
        for k in range(11):
            r = 5 + k; wr = W0 + d * 12 + k
            pdt.cell(r, c0, f'=IF(ISNUMBER(Wells!G{wr}),Wells!G{wr},NA())')
            pdt.cell(r, c0 + 1, f'=IF(ISNUMBER(Wells!P{wr}),Wells!P{wr},NA())')
            pdt.cell(r, c0 + 2, f'=IF(ISNUMBER(Wells!Q{wr}),Wells!Q{wr},NA())')
            pdt.cell(r, c0 + 3, f'=IF(ISNUMBER(Wells!R{wr}),Wells!R{wr},NA())')
        for k in range(NCURVE):
            r = 5 + k
            pdt.cell(r, c0 + 4, f'=IF(ISNUMBER(Fit!J{fr}),10^(LOG10(Fit_Data!$AO${5 + d}/1.5/{1.8 ** 10!r})+{k / (NCURVE - 1)!r}*LOG10(2.25*{1.8 ** 10!r})),NA())')
            pdt.cell(r, c0 + 5, f'=IF(ISNUMBER(Fit!J{fr}),Fit!J{fr}*{COL(c0 + 4)}{r}/(Fit!N{fr}+{COL(c0 + 4)}{r}),NA())')
        sc = ScatterChart(); sc.title = f'Plate row {L}'; sc.style = 13
        sc.x_axis.title = 'Antibody (µg/mL)'; sc.y_axis.title = 'ABC'; sc.x_axis.scaling.logBase = 10
        sc.x_axis.delete = False; sc.y_axis.delete = False
        xs = Reference(pdt, min_col=c0, min_row=5, max_row=15)
        for j, (mk, sz) in zip((1, 2, 3), (('circle', 5), ('square', 4), ('circle', 7))):
            se = Series(Reference(pdt, min_col=c0 + j, min_row=4, max_row=15), xs, title_from_data=True)
            se.marker = Marker(mk, size=sz); se.graphicalProperties.line.noFill = True; sc.series.append(se)
        se = Series(Reference(pdt, min_col=c0 + 5, min_row=4, max_row=4 + NCURVE), Reference(pdt, min_col=c0 + 4, min_row=5, max_row=4 + NCURVE), title_from_data=True)
        se.marker = Marker('none'); se.smooth = True; sc.series.append(se)
        sc.height = 7.5; sc.width = 12
        pl_.cell(3 + 16 * (d // 2), 1 + 9 * (d % 2), f'=Plot_Data!{COL(c0)}3').font = Font(bold=True)
        pl_.add_chart(sc, f'{COL(1 + 9 * (d % 2))}{4 + 16 * (d // 2)}')

    # ============ Summary ============
    su = wb.create_sheet('Summary', 1); su['A1'] = 'Antigens per cell (one-site fit Bmax × valency; 3 significant figures)'; su['A1'].font = TITLE
    su['A2'] = '=IF(BeadQC<>"PASS","Bead curve QC: "&BeadQC,"Bead curve QC: PASS (slope "&TEXT(Slope,"0.0000")&", R² = "&TEXT(BeadR2,"0.00000")&")")'
    su['A3'] = '=Setup!C16'; su['A3'].font = WARN
    su['A4'] = '=IF(Setup!C31<>"",Setup!C31,IF(Setup!C32<>"",Setup!C32,"Data: "&Setup!B29&" import rows; last refresh "&IF(ISNUMBER(Setup!B30),TEXT(Setup!B30,"yyyy-mm-dd hh:mm"),Setup!B30)))'
    su['A5'] = '=Setup!C17'; su['A5'].font = WARN
    r0 = 7; NC = 8; NA_ = 8
    su.cell(r0, 1, 'Antigens/cell').font = Font(bold=True, size=12)
    su.cell(r0, 2 + NA_ + 1, 'Flags').font = Font(bold=True, size=12)
    hdr(su, r0 + 1, 1, ['Cell line'] + [''] * NA_); hdr(su, r0 + 1, 2 + NA_ + 1, ['Cell line'] + [''] * NA_)
    FR = f'Fit!$A${F0}:$A${F0 + 7}'
    fcol = lambda c: f'Fit!${c}${F0}:${c}${F0 + 7}'
    for j in range(NA_):
        cc = 2 + j
        su.cell(r0 + 1, cc).value = f'=IFERROR(INDEX({fcol("C")},MATCH({j + 1},{fcol("AQ")},0)),"")'
        su.cell(r0 + 1, cc + NA_ + 1).value = f'=IF({COL(cc)}{r0 + 1}="","",{COL(cc)}{r0 + 1}&" flag")'
    for i in range(NC):
        rr = r0 + 2 + i
        cA = su.cell(rr, 1, f'=IFERROR(INDEX({fcol("B")},MATCH({i + 1},{fcol("AP")},0)),"")'); cA.font = Font(bold=True)
        su.cell(rr, 2 + NA_ + 1, f'=A{rr}').font = Font(bold=True)
        for j in range(NA_):
            cc = 2 + j; hc = f'{COL(cc)}${r0 + 1}'
            mt = f'MATCH($A{rr}&"|"&{hc},{fcol("AR")},0)'
            v = f'INDEX({fcol("W")},{mt})'
            c = su.cell(rr, cc, f'=IF(OR($A{rr}="",{hc}=""),"",IFERROR(IF(ISNUMBER({v}),{sig3(v)},IF(INDEX({fcol("AA")},{mt})="ND","ND",INDEX({fcol("Y")},{mt}))),""))')
            c.number_format = '#,##0'; c.border = BOX; c.alignment = Alignment(horizontal='right')
            flg = (f'IF(OR(INDEX({fcol("X")},{mt})="Plateau reached",INDEX({fcol("X")},{mt})=""),"","; "&INDEX({fcol("X")},{mt}))'
                   f'&IF(OR(INDEX({fcol("Y")},{mt})="OK",INDEX({fcol("Y")},{mt})=""),"","; "&INDEX({fcol("Y")},{mt}))'
                   f'&IF(OR(INDEX({fcol("Z")},{mt})="OK",INDEX({fcol("Z")},{mt})=""),"","; "&INDEX({fcol("Z")},{mt}))')
            c2 = su.cell(rr, cc + NA_ + 1, f'=IF(OR($A{rr}="",{hc}=""),"",IFERROR(IF(MID({flg},3,999)="","OK",MID({flg},3,999)),""))')
            c2.border = BOX; c2.alignment = Alignment(wrap_text=True, vertical='top')
            # numeric copy for the chart
            su.cell(rr, 40 + j, f'=IF(ISNUMBER({COL(cc)}{rr}),{COL(cc)}{rr},NA())')
        su.cell(rr, 39, f'=IF(A{rr}="","",A{rr})')
    for j in range(NA_): su.cell(r0 + 1, 40 + j, f'={COL(2 + j)}{r0 + 1}')
    su.conditional_formatting.add(f'{COL(3 + NA_)}{r0 + 2}:{COL(2 + 2 * NA_)}{r0 + 1 + NC}',
                                  FormulaRule(formula=[f'{COL(3 + NA_)}{r0 + 2}="OK"'], fill=GRN))
    su.conditional_formatting.add(f'{COL(3 + NA_)}{r0 + 2}:{COL(2 + 2 * NA_)}{r0 + 1 + NC}',
                                  FormulaRule(formula=[f'AND({COL(3 + NA_)}{r0 + 2}<>"OK",{COL(3 + NA_)}{r0 + 2}<>"")'], fill=RED))
    for c in range(39, 48): su.column_dimensions[COL(c)].hidden = True
    bc = BarChart(); bc.type = 'col'; bc.grouping = 'clustered'; bc.title = 'Antigens per cell'
    bc.y_axis.title = 'Antigens/cell (ABC)'; bc.x_axis.delete = False; bc.y_axis.delete = False
    bc.add_data(Reference(su, min_col=40, max_col=39 + NA_, min_row=r0 + 1, max_row=r0 + 1 + NC), titles_from_data=True)
    bc.set_categories(Reference(su, min_col=39, min_row=r0 + 2, max_row=r0 + 1 + NC))
    bc.height = 8; bc.width = 16; su.add_chart(bc, f'A{r0 + 3 + NC}')
    L0 = r0 + 3 + NC + 17
    su.cell(L0 - 1, 1, 'Long-format results (pipeline / LIMS export)').font = Font(bold=True, size=12)
    lcols = [('Plate ID', None), ('Plate row', 'A'), ('Cell line', 'B'), ('Antibody', 'C'), ('Target', 'D'), ('Clone', 'E'), ('Catalog #', 'F'),
             ('Lot #', 'G'), ('Antigens/cell (3 s.f.)', 'W'), ('Bmax 95% CI low', 'L'), ('Bmax 95% CI high', 'M'), ('Kd (µg/mL)', 'N'),
             ('Kd (nM)', 'R'), ('R²', 'S'), ('n points', 'I'), ('Plateau flag', 'X'), ('Fit flag', 'Y'), ('Top-conc bead-range flag', 'Z'),
             ('Bead lot', None), ('Bead QC', None), ('Bead slope', None), ('Bead R²', None)]
    hdr(su, L0, 1, [c for c, _ in lcols], 32)
    for i in range(8):
        rr = L0 + 1 + i; mt = f'MATCH({i + 1},{fcol("AS")},0)'
        for j, (lab, col) in enumerate(lcols):
            if col is None:
                f = {'Plate ID': 'PlateID&""', 'Bead lot': 'BeadLot&""', 'Bead QC': 'BeadQC', 'Bead slope': 'Slope', 'Bead R²': 'BeadR2'}[lab]
                f = f'=IF($B{rr}="","",{f})'
            elif col == 'A':
                f = f'=IFERROR(INDEX({fcol("A")},{mt}),"")'
            else:
                v = f'INDEX({fcol(col)},{mt})'
                if col in ('W', 'L', 'M', 'N', 'R'):
                    f = f'=IF($B{rr}="","",IFERROR(IF(ISNUMBER({v}),{sig3(v)},IF(INDEX({fcol("AA")},{mt})="ND","ND","")),""))' if col == 'W' else \
                        f'=IF($B{rr}="","",IFERROR(IF(ISNUMBER({v}),{sig3(v)},""),""))'
                else:
                    f = f'=IF($B{rr}="","",IFERROR({v}&"",""))' if col not in ('S', 'I') else f'=IF($B{rr}="","",IFERROR({v},""))'
            c = su.cell(rr, 1 + j, f); c.border = BOX
            if col in ('W', 'L', 'M'): c.number_format = '#,##0'
            if col == 'S': c.number_format = '0.000'
            if lab == 'Bead slope': c.number_format = '0.0000'
            if lab == 'Bead R²': c.number_format = '0.00000'
    su.column_dimensions['A'].width = 14
    for i in range(2, 2 + NA_): su.column_dimensions[COL(i)].width = 12
    su.column_dimensions[COL(2 + NA_)].width = 3
    for i in range(3 + NA_, 3 + 2 * NA_): su.column_dimensions[COL(i)].width = 28
    for i in range(2 + 2 * NA_ + 1, 23): su.column_dimensions[COL(i)].width = 14

    # ============ PQ_Setup ============
    q = wb.create_sheet('PQ_Setup'); q['A1'] = 'One-time Power Query setup (do this once in the MASTER template; every copy inherits it)'; q['A1'].font = TITLE
    steps = [
        '1. Save the master template to a local folder that contains test exports (e.g. a copy of the Plate 1 files). Save it as .xlsx.',
        '2. Data > Get Data > From Other Sources > Blank Query.  In the Power Query editor: Home > Advanced Editor. Select ALL text, delete it.',
        '3. Copy cells A20 down to the last line of the code below (click A20, Ctrl+Shift+End, Ctrl+C) and paste into the Advanced Editor. Click Done.',
        '4. Rename the query (right pane, Name) to: qFACS_Import',
        '5. File > Options and settings > Query Options > CURRENT WORKBOOK > Privacy: tick "Ignore the Privacy Levels and potentially improve performance".',
        '   (Required: the query reads the folder path from this workbook (named cell PQ_Folder) and then opens that folder; otherwise Formula.Firewall error.)',
        '6. Home > Close & Load To... > Table > Existing worksheet. BEFORE pressing OK: unhide sheet Import (right-click a tab > Unhide), select Import!A1:M20000,',
        '   press Delete (clear contents only - do NOT delete rows/columns or the sheet), then enter =Import!$A$1 as the destination. OK.',
        '7. Data > Queries & Connections > right-click qFACS_Import > Properties: tick "Refresh data when opening the file"; untick "Enable background refresh";',
        '   untick "Adjust column width". OK. Hide sheet Import again. Save.',
        '8. Test: copy the master into another folder with exports, open it -> Setup B29 (Import rows) > 0, Bead_Std shows 4 gMFIs, Summary filled.',
        '9. SharePoint test: open the copy from the synced library. Setup B26 starts with https:// ; Excel asks once for credentials -> choose Organizational account > Sign in > Connect.',
        '   If navigation fails, check the library segment in B26 (e.g. "Shared Documents") or paste the local OneDrive path into Setup B23 (Folder override).',
        'Notes: Import columns are fixed (File, Kind, PlateID, CellLine, RowKey, Well, Gate, Stat, Header, Num, Text, Key, Loaded); formulas read Import!A2:M20000.',
        '       Kind = "bead" if the file name contains "bead", else "cells".  Summary rows (Mean, SD, Median, CV, ...) are dropped.  Unreadable files appear as PARSE ERROR.',
        '       This code was written for Excel 365 Power Query and could not be executed in the build environment - verify on first run.',
    ]
    for i, l in enumerate(steps, 3): q.cell(i, 1, l)
    q['A19'] = 'M code (copy from A20 down):'; q['A19'].font = Font(bold=True, color='C00000')
    for i, line in enumerate(M_CODE.split('\n'), 20):
        c = q.cell(i, 1, line); c.font = Font(name='Consolas', size=9)
        c.number_format = '@'
        if line.startswith('='): c.value = "'" + line
    q.column_dimensions['A'].width = 170

    # ============ Import (hidden) ============
    im = wb.create_sheet('Import')
    for j, h in enumerate(IMPORT_COLS, 1): im.cell(1, j, h).font = Font(bold=True)
    for i, row in enumerate(ex.get('import', []), 2):
        for j, v in enumerate(row, 1):
            if v is not None: im.cell(i, j, v)
    for nm, c in zip(['IM_File', 'IM_Kind', 'IM_Plate', 'IM_Cell', 'IM_RowKey', 'IM_Well', 'IM_Gate', 'IM_Stat', 'IM_Header', 'IM_Num', 'IM_Text', 'IM_Key', 'IM_Loaded'],
                     'ABCDEFGHIJKLM'):
        name(wb, nm, f'Import!${c}$2:${c}${IMAX}')
    for c, wd in zip('ABCDEFGHIJKLM', (22, 7, 9, 10, 18, 6, 28, 26, 44, 10, 10, 48, 16)): im.column_dimensions[c].width = wd

    for sh in ('Fit_Data', 'Fit_Grid', 'Plot_Data', 'Import'): wb[sh].sheet_state = 'hidden'
    order = ['README', 'Setup', 'Summary', 'Antibody_Panel', 'Plate_Map', 'Bead_Std', 'Wells', 'Fit', 'Plots', 'PQ_Setup', 'Fit_Data', 'Fit_Grid', 'Plot_Data', 'Import']
    wb._sheets = [wb[n] for n in order]
    wb.active = 1
    wb.calculation.fullCalcOnLoad = True
    wb.save(out)
    return out


def example_from_v4(inputs_xlsx, exports):
    """Pre-fill panel / plate map from the v4 inputs workbook and static Import rows from the exports."""
    wbv = load_workbook(inputs_xlsx)
    p = wbv['Antibody_Panel']; m = wbv['Plate_Map']; s = wbv['Setup']
    panel = []
    for i in range(NAB):
        row = {cc: p.cell(5 + i, cc).value for cc in range(1, 16)}
        if row.get(1): panel.append(row)
    pm = {}
    for i, L in enumerate(ROWS):
        r = 5 + i
        pm[L] = dict(ab=m.cell(r, 3).value, top=m.cell(r, 4).value, xfer=m.cell(r, 5).value, dil=m.cell(r, 6).value)
    imp = []
    for e in exports: imp += [row + [None] for row in pq_emulate(e[0], e[1])]
    return dict(setup={'plate': 'Plate1', 'date': s['B4'].value or '', 'exp': 'Exp2290'}, panel=panel, platemap=pm, import_=imp, **{'import': imp})


if __name__ == '__main__':
    out = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == '--example':
        inputs = sys.argv[3]; ex_files = [(a.split('::')[0], a.split('::')[1]) for a in sys.argv[4:]]
        build(out, example_from_v4(inputs, ex_files))
    else:
        build(out)
    print('wrote', out)
