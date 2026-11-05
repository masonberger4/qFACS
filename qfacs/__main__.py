"""Command line: python -m qfacs <command> ...

  template OUT.xlsx              write a blank setup workbook
  validate SETUP.xlsx [--wells CSV]  check a setup workbook; optionally write the well map
"""
from __future__ import annotations

import argparse
import csv
import sys

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
    a = ap.parse_args(argv)

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


if __name__ == "__main__":
    sys.exit(main())
