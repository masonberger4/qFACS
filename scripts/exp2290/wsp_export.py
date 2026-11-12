"""FlowJo table export straight from a workspace (.wsp), with no .fcs files and no re-gating.

FlowJo saves, for every sample in the workspace, the event count of each gate and the value of each statistic
added to a population (here Count and Geometric Mean of B5 (575)-A on Live). This reads those saved numbers and
writes the table FlowJo's Table Editor exports, one .xls per workspace group (cell line):

    sample | Cells | Freq. of Parent | Cells/Single Cells | Freq. of Parent | .../Live | Freq. of Parent
           | .../Live | Count | .../Live | Geometric Mean (B5 (575)-A)        then Mean and SD

The numbers are FlowJo's own, as of the last time the workspace was saved.

Usage: python wsp_export.py WSP OUT_DIR PLATE_LABEL [--name "wsp group=file name" ...] [--no-count]
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_export import PE, SKIP_GROUPS, write_xls  # noqa: E402

from qfacs.stats_io import well_of  # noqa: E402


def wsp_tables(wsp_path, pe=PE):
    """Returns ({group: [row]}, gate paths). Row: sample, freq (% of parent per gate), count, gmfi: FlowJo's saved values."""
    root = ElementTree.parse(str(wsp_path)).getroot()
    samples = {}
    for sn in root.iterfind(".//SampleList/Sample/SampleNode"):
        counts, names, node = [int(sn.get("count"))], [], sn
        while (nxt := node.find("Subpopulations/Population")) is not None:      # Cells > Single Cells > Live
            if len(node.findall("Subpopulations/Population")) != 1:
                raise ValueError(f"{sn.get('name')}: the gate tree branches under {node.get('name')}; expected one chain")
            node = nxt
            names.append(node.get("name"))
            counts.append(int(node.get("count")))
        if not names:
            continue                                                             # ungated sample (beads, controls)
        if min(counts) < 0:
            raise ValueError(f"{sn.get('name')}: FlowJo saved no event counts; open the workspace, let it recalculate, save")
        gm = [float(st.get("value")) for st in node.iterfind("Subpopulations/Statistic")
              if st.get("name") == "Geometric Mean" and st.get("id") == pe]
        if not gm or math.isnan(gm[0]):
            raise ValueError(f"{sn.get('name')}: no saved Geometric Mean of {pe} on {'/'.join(names)}; add it to the population in FlowJo and save")
        freq = [100.0 * c / p if p else None for p, c in zip(counts, counts[1:])]
        samples[sn.get("sampleID")] = (dict(sample=Path(sn.get("name")).stem, freq=freq, count=counts[-1], gmfi=gm[0]),
                                       ["/".join(names[:i + 1]) for i in range(len(names))])
    out, paths = {}, None
    for g in root.iterfind(".//Groups/GroupNode"):
        if g.get("name").lower() in SKIP_GROUPS:
            continue
        rows = [samples[r.get("sampleID")] for r in g.iterfind(".//SampleRefs/SampleRef") if r.get("sampleID") in samples]
        if rows:
            out[g.get("name")] = sorted((r for r, _ in rows), key=lambda r: well_of(r["sample"]) or r["sample"])
            paths = rows[0][1]
    return out, paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wsp")
    ap.add_argument("out_dir")
    ap.add_argument("plate")
    ap.add_argument("--name", action="append", default=[], help='"workspace group=cell line name for the file"')
    ap.add_argument("--no-count", action="store_true", help="leave the Count column out (layout of 'Plate1 A549.xls')")
    a = ap.parse_args()
    rename = dict(x.split("=", 1) for x in a.name)
    groups, paths = wsp_tables(a.wsp)
    for g, rows in groups.items():
        f = write_xls(rows, paths, Path(a.out_dir) / f"{a.plate} {rename.get(g, g)}.xls", with_count=not a.no_count, count_first=True)
        gm = [r["gmfi"] for r in rows]
        print(f"{f}: {len(rows)} wells, live events {min(r['count'] for r in rows)}-{max(r['count'] for r in rows)}, gMFI {min(gm):.0f}-{max(gm):.0f}")


if __name__ == "__main__":
    main()
