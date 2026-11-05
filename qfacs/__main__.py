"""Command line: python -m qfacs <command> ...

  template OUT.xlsx              write a blank setup workbook
  validate SETUP.xlsx [--wells CSV]  check a setup workbook; optionally write the well map
  analyze SETUP.xlsx DATA... [-o OUT.xlsx]  FlowJo exports (files or folders) -> results workbook
      Files whose name contains "bead" are bead exports; others are cell exports named "<Plate ID>_...".
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .setup_io import read_setup
from .template import write_setup
from .validate import summarize, validate
from .wellmap import expand_wells


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qfacs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template", help="write a blank setup workbook")
    t.add_argument("out")
    v = sub.add_parser("validate", help="check a setup workbook")
    v.add_argument("setup")
    v.add_argument("--wells", help="also write one line per well to this CSV")
    z = sub.add_parser("analyze", help="FlowJo exports + setup -> results workbook")
    z.add_argument("setup")
    z.add_argument("data", nargs="+", help="export files or folders")
    z.add_argument("-o", "--out", help="results workbook (default: <Experiment ID>_qFACS_results.xlsx next to the setup)")
    z.add_argument("--beads", nargs="*", default=[], help="bead export files, when their names lack 'bead'")
    a = ap.parse_args(argv)

    if a.cmd == "analyze":
        return _analyze(a)

    if a.cmd == "template":
        write_setup(a.out)
        print("wrote", a.out)
        return 0

    setup, issues = read_setup(a.setup)
    issues = issues + validate(setup)
    for i in sorted(issues, key=lambda i: (i.level != "error", i.sheet, i.row or 0)):
        print(i)
    print(summarize(issues))
    if a.wells:
        wells, _ = expand_wells(setup)
        with open(a.wells, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["plate_id", "well", "cell_line", "reagent", "conc_ug_ml", "role", "point"])
            for x in sorted(wells, key=lambda x: (x.plate_id, x.row, x.col)):
                w.writerow([x.plate_id, x.well, x.cell_line, x.reagent or "", f"{x.conc_ug_ml:.6g}", x.role, x.point or ""])
        print("wrote", a.wells)
    return 1 if any(i.level == "error" for i in issues) else 0


EXTS = {".xls", ".xlsx", ".csv", ".txt", ".tsv"}


def _analyze(a) -> int:
    from .analysis import analyze
    from .report import write_results
    files = []
    for d in a.data:
        p = Path(d)
        files += sorted(x for x in p.iterdir() if x.suffix.lower() in EXTS and not x.name.startswith("~$")) if p.is_dir() else [p]
    beads = [str(Path(b)) for b in a.beads] + [str(f) for f in files if "bead" in f.name.lower()]
    cells = [str(f) for f in files if str(f) not in beads and f.resolve() != Path(a.setup).resolve()
             and "qfacs_results" not in f.name.lower()]
    setup, parse_issues = read_setup(a.setup)
    res = analyze(setup, cells, beads, parse_issues=parse_issues)
    out = a.out or str(Path(a.setup).with_name(f"{setup.experiment.get('experiment_id') or 'qFACS'}_qFACS_results.xlsx"))
    write_results(res, out)
    for i in sorted(res.issues, key=lambda i: i.level != "error"):
        print(i)
    for n in res.notes:
        print("NOTE   ", n)
    for f in res.fits:
        val = "ND" if f.status == "ND" else (f"{f.antigens:,.0f}" if f.antigens is not None else "not fitted")
        print(f"{f.cell_line:12s} {f.reagent:10s} {val:>12s}  {'; '.join(f.flags) or 'OK'}")
    print(summarize(res.issues), "->", out)
    return 1 if any(i.level == "error" for i in res.issues) else 0


if __name__ == "__main__":
    sys.exit(main())
