// qFACS_Import  -  reads every FlowJo table export (.xls / .csv / .txt) in THIS workbook's folder
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
    Typed
