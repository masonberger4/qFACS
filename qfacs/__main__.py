"""Command line: python -m qfacs <command> ...

  template OUT.xlsx              write a blank setup workbook
  validate SETUP.xlsx [--wells CSV]  check a setup workbook; optionally write the well map
  analyze SETUP.xlsx DATA... [-o OUT.xlsx]  FlowJo exports (files or folders) -> results workbook
      Files whose name contains "bead" are bead exports; others are cell exports named "<Plate ID>_...".
      Gating, compensation and unmixing are done by hand in FlowJo; .fcs and .wsp files are not read.
  app [--port N] [--no-browser]  the same steps as a page in your browser (no command line needed after this)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .runner import check_setup
from .template import write_setup
from .validate import summarize
from .wellmap import expand_wells


def main(argv=None) -> int:
    # Windows consoles and redirected output often use cp1252, which has no κ, µ etc.: never crash on printing
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
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
    g = sub.add_parser("app", help="open qFACS as a page in your browser")
    g.add_argument("--port", type=int, default=8765)
    g.add_argument("--host", default="127.0.0.1", help="0.0.0.0 serves the page to other computers on the network")
    g.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "app":
        from .app import serve
        return serve(a.host, a.port, not a.no_browser)

    if a.cmd == "analyze":
        return _analyze(a)

    if a.cmd == "template":
        write_setup(a.out)
        print("wrote", a.out)
        return 0

    setup, issues = check_setup(a.setup)
    for i in issues:
        print(i)
    print(summarize(issues))
    if a.wells:
        wells, _ = expand_wells(setup)
        with open(a.wells, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["plate_id", "well", "cell_line", "reagent", "conc_ug_ml", "role", "point"])
            for x in sorted(wells, key=lambda x: (x.plate_id, x.row, x.col)):
                w.writerow([x.plate_id, x.well, x.cell_line, x.reagent or "", f"{x.conc_ug_ml:.6g}", x.role, x.point or ""])
        print("wrote", a.wells)
    return 1 if any(i.level == "error" for i in issues) else 0


def _analyze(a) -> int:
    from .runner import report_lines, run_analysis
    res, out = run_analysis(a.setup, a.data, a.out, a.beads)
    for line in report_lines(res, out):
        print(line)
    return 1 if any(i.level == "error" for i in res.issues) else 0


if __name__ == "__main__":
    sys.exit(main())
