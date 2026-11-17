"""One analysis run from files on disk, shared by the command line and the app."""
from __future__ import annotations

from pathlib import Path

from .setup_io import read_setup
from .validate import summarize, validate

EXTS = {".xls", ".xlsx", ".csv", ".txt", ".tsv"}


def is_results_workbook(f: Path) -> bool:
    """True for a qFACS results workbook (Summary + Fits sheets), so a re-run does not read old results as data."""
    if f.suffix.lower() != ".xlsx":
        return False
    try:
        from openpyxl import load_workbook
        wb = load_workbook(f, read_only=True)
        names = set(wb.sheetnames)
        wb.close()
        return {"Summary", "Fits"} <= names
    except Exception:
        return False


def collect(setup_path, data, out=None, beads=()):
    """Export files or folders -> (cell exports, bead exports). Bead exports have "bead" in the name or are listed
    in `beads`; the setup workbook, the output and earlier results workbooks are left out."""
    files = []
    for d in data:
        p = Path(d)
        files += sorted(x for x in p.iterdir() if x.suffix.lower() in EXTS and not x.name.startswith("~$")) if p.is_dir() else [p]
    bead_files = [str(Path(b)) for b in beads] + [str(f) for f in files if "bead" in f.name.lower()]
    skip = {Path(setup_path).resolve()} | ({Path(out).resolve()} if out else set())
    cells = [str(f) for f in files if str(f) not in bead_files and f.resolve() not in skip
             and "qfacs_results" not in f.name.lower() and not is_results_workbook(f)]
    return cells, bead_files


def default_out(setup_path, setup) -> str:
    return str(Path(setup_path).with_name(f"{setup.experiment.get('experiment_id') or 'qFACS'}_qFACS_results.xlsx"))


def check_setup(setup_path):
    """Read and validate a setup workbook -> (setup, issues sorted errors first)."""
    setup, issues = read_setup(setup_path)
    issues = issues + validate(setup)
    return setup, sorted(issues, key=lambda i: (i.level != "error", i.sheet, i.row or 0))


def run_analysis(setup_path, data, out=None, beads=(), source=None):
    """Setup workbook + FlowJo exports (files or folders) -> (Results, path of the results workbook written).
    `source` replaces the setup path shown in the results (the app works on temporary copies)."""
    from .analysis import analyze
    from .report import write_results
    cells, bead_files = collect(setup_path, data, out, beads)
    setup, parse_issues = read_setup(setup_path)
    if source:
        setup.source = source
    res = analyze(setup, cells, bead_files, parse_issues=parse_issues)
    out = out or default_out(setup_path, setup)
    write_results(res, out)
    return res, out


def report_lines(res, out) -> list[str]:
    """The run log: one line per export, issue, note and fit, then the totals."""
    from .analysis import MODEL_LABEL
    lines = [f"FILE    {d['file']}: {d['plate']}, {d['cell_line']} ({'from file name' if d['named'] else 'from Layout'}), "
             f"{d['wells']} wells; {d['antibodies']}" for d in res.data_files]
    lines += [str(i) for i in sorted(res.issues, key=lambda i: i.level != "error")]
    lines += [f"NOTE    {n}" for n in res.notes]
    for f in res.fits:
        val = "ND" if f.status == "ND" else (f"{f.antigens:,.0f}" if f.antigens is not None else "not fitted")
        lines.append(f"{f.cell_line:12s} {f.reagent:10s} {MODEL_LABEL[f.model]:19s} {val:>12s}  {'; '.join(f.flags) or 'OK'}")
    lines.append(f"{summarize(res.issues)} -> {out}")
    return lines
