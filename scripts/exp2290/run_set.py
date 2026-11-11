"""Analyse one Exp2290 set both ways and write its outputs.

    python run_set.py SET_ID LAB_SETUP.xlsx OUT_DIR BEAD_EXPORT

OUT_DIR/cell_line_exports/ must already hold the per cell line FlowJo-style exports ('Plate1 A549.xls', ...),
written by gate_export.py (Sets 2, 3) or set1_exports.py (Set 1).

Writes into OUT_DIR:
  Exp2290_<set>_setup.xlsx           qFACS setup workbook built from the lab setup sheet
  Exp2290_<set>_qFACS_results.xlsx   the engine's own results workbook (method 1)
  Exp2290_<set>_Analysis.xlsx        analysis workbook in the layout of Exp2290_Analysis.xlsx, both methods
"""
from __future__ import annotations

import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import abc_calc  # noqa: E402
from sets import SETS, build_setup  # noqa: E402

from qfacs.analysis import analyze, antibody_fp  # noqa: E402
from qfacs.calc import BEAD_KEYS  # noqa: E402
from qfacs.report import write_results  # noqa: E402
from qfacs.setup_io import read_setup  # noqa: E402
from qfacs.template import write_setup  # noqa: E402


def run(set_id, lab_xlsx, out_dir, bead_export):
    out_dir = Path(out_dir)
    with_counts = out_dir / "cell_line_exports_with_counts"      # same exports plus the Live Count column (low-events QC)
    exports = sorted((with_counts if with_counts.is_dir() else out_dir / "cell_line_exports").glob("Plate*.xls"))
    bead_file = out_dir / Path(bead_export).name
    if Path(bead_export).resolve() != bead_file.resolve():
        shutil.copy(bead_export, bead_file)
    setup, layout = build_setup(set_id, lab_xlsx, bead_file)
    setup_path = out_dir / f"Exp2290_{set_id}_setup.xlsx"
    write_setup(setup_path, setup)
    setup, parse_issues = read_setup(setup_path)

    # ---- method 1: the qFACS engine (log-log bead curve, isotype subtraction, one-site fit)
    res = analyze(setup, [str(f) for f in exports], [str(bead_file)], parse_issues=parse_issues)
    write_results(res, out_dir / f"Exp2290_{set_id}_qFACS_results.xlsx")

    # ---- method 2: the ABC calculator (linear bead slope, unstained-subtracted gMFI, total-binding fit)
    curve = next(iter(res.beads.values()))
    slope, intercept, r2 = abc_calc.bead_line([curve.pe[k] for k in BEAD_KEYS], [curve.gmfi[k] for k in BEAD_KEYS])
    blank = {(r.well.plate_id, r.well.row): r.gmfi for r in res.wells if r.well.role == "blank"}
    groups = defaultdict(list)
    for r in res.wells:
        if r.well.role == "titration" and r.gmfi is not None:
            groups[(r.well.cell_line, r.well.reagent)].append(r)
    calc = {}
    for (line, reagent), rs in groups.items():
        rec = setup.reagent(reagent)
        rs = sorted(rs, key=lambda r: -r.well.conc_ug_ml)
        b = blank.get((rs[0].well.plate_id, rs[0].well.row))
        if b is None:
            continue
        conc = [r.well.conc_ug_ml for r in rs] + [0.0]
        y = [r.gmfi - b for r in rs] + [0.0]
        fit = abc_calc.fit_total_binding(conc, y)
        fp, assumed = (1.0, False) if rec.get("is_isotype") == "Y" else antibody_fp(rec)
        abc_calc.abc(fit, slope, fp)
        if assumed:
            fit.flags.append("F/P assumed 1 (blank in setup)")
        calc[(line, reagent)] = dict(fit=fit, conc=conc, y=y, blank=b, fp=fp, rows=rs, isotype=rec.get("is_isotype") == "Y")
    return dict(set_id=set_id, info=SETS[set_id], setup=setup, layout=layout, res=res, calc=calc, exports=exports,
                bead=dict(curve=curve, slope=slope, intercept=intercept, r2=r2, file=bead_file.name), out_dir=out_dir,
                lab_xlsx=lab_xlsx)


def show(d):
    res, calc = d["res"], d["calc"]
    b = d["bead"]
    print(f"== {d['set_id']}: beads {b['curve'].gmfi} | engine log-log slope {b['curve'].slope:.4f} R2 {b['curve'].r2:.4f} {b['curve'].qc}"
          f" | calculator linear slope {b['slope']:.4f} R2 {b['r2']:.4f}")
    for i in res.issues:
        print("  ", i)
    for n in res.notes:
        print("   NOTE", n)
    print(f"  {'cell line':10s} {'Ab':6s} {'engine':>10s} {'eng Kd':>8s} {'eng NS':>10s} {'calc ABC':>10s} {'calc Kd':>8s} {'NS':>8s} {'R2':>6s}  flags")
    for f in res.fits:
        c = calc.get((f.cell_line, f.reagent))
        eng = "ND" if f.status == "ND" else (f"{f.antigens:,.0f}" if f.antigens is not None else "-")
        cross = f"{f.cross_antigens:,.0f}" if f.cross_antigens is not None else ("ND" if f.cross is not None and f.cross.nd else "-")
        kd = f"{f.fit.kd:.3g}" if f.fit.kd and not f.fit.nd else "-"
        if c:
            cf = c["fit"]
            print(f"  {f.cell_line:10s} {f.reagent:6s} {eng:>10s} {kd:>8s} {cross:>10s} {cf.abc:>10,.0f} {cf.kd:>8.3g} {cf.ns:>8.3g} {cf.r2 or 0:>6.3f}  "
                  f"E[{'; '.join(f.flags)}] C[{'; '.join(cf.flags)}]")
        else:
            print(f"  {f.cell_line:10s} {f.reagent:6s} {eng:>10s}  (no data)  E[{'; '.join(f.flags)}]")


if __name__ == "__main__":
    d = run(*sys.argv[1:5])
    show(d)
    if "--no-book" not in sys.argv:
        from analysis_book import write_analysis
        print("wrote", write_analysis(d))
