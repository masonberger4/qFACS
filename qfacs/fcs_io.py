"""Gate .fcs files and compute FlowJo-style statistics (needs the optional `flowkit` package).

Cells: a FlowJo workspace (.wsp) holds the gates (e.g. Cells > Single Cells > Live). FlowKit applies them to the
.fcs files; for each sample we report the live count and the PE geometric mean.

Beads: a bead tube workspace holds hand-drawn Low / Med Low / Med High / High gates. Nothing is gated
automatically.

Geometric mean, FlowJo style: FlowJo v10 averages the events on the parameter's display transform (the
biexponential set in the workspace) and transforms the average back. On Exp2290 Plate 1 this reproduces
FlowJo's exported gMFI to a median of +0.2% (90% of wells within 0.5%), against about -3.4% for a plain
log-space geometric mean of the positive events.

The results are written as FlowJo-like table exports (one row per sample, '<gate path> | <statistic>' columns),
so they can be opened and checked, and the rest of qFACS reads them exactly like a FlowJo export.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .stats_io import StatsTable

# Default display transform for PE when no workspace is given (the A8 workspace's B5 (575)-A biex).
DEFAULT_BIEX = dict(negative=0.0, width=-1000.0, positive=6.45, max_value=1e8)
BEAD_GATES = ("Low", "Med Low", "Med High", "High")


def _fk():
    try:
        import flowkit
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("reading .fcs/.wsp files needs FlowKit: pip install flowkit") from e
    return flowkit


def _quiet():
    import warnings
    warnings.filterwarnings("ignore")


def biex(**kw):
    fk = _fk()
    p = {**DEFAULT_BIEX, **kw}
    return fk.transforms.WSPBiexTransform(negative=p["negative"], width=p["width"], positive=p["positive"],
                                          max_value=p["max_value"])


def flowjo_gmean(values, transform=None):
    """FlowJo-style geometric mean: mean on the display transform, transformed back."""
    v = np.asarray(values, float)
    if v.size == 0:
        return None
    if transform is None:
        pos = v[v > 0]
        return float(np.exp(np.mean(np.log(pos)))) if pos.size else None
    y = transform.apply(v.reshape(-1, 1)).ravel()
    return float(transform.inverse(np.array([[y.mean()]]))[0, 0])


def norm_plate(s):
    """'Plate_001' and 'Plate1' -> 'plate1'."""
    s = re.sub(r"[^a-z0-9]", "", str(s or "").lower())
    return re.sub(r"(?<=[a-z])0+(?=\d)", "", s)


def gate_workspace(wsp_path, fcs_dir, pe_param, live_gate=None):
    """Apply a workspace's gates to the .fcs files in fcs_dir.

    Returns {plate keyword or '': StatsTable}, notes. Columns: '<path> | Count' and
    '<path> | Geometric Mean (<pe_param>)' for the live gate (default: the deepest gate).
    """
    _quiet()
    fk = _fk()
    notes = []
    wsp = fk.Workspace(str(wsp_path), fcs_samples=str(fcs_dir))
    sids = wsp.get_sample_ids()
    if not sids:
        raise ValueError(f"{Path(wsp_path).name}: none of its samples were found in {fcs_dir}")
    tables = {}
    for sid in sorted(sids):
        try:
            wsp.analyze_samples(sample_id=sid, use_mp=False)
        except Exception as e:
            notes.append(f"{sid}: gating failed ({e}); skipped")
            continue
        sample = wsp.get_sample(sid)
        gates = wsp.get_gate_ids(sid)
        if live_gate:
            hit = [(g, p) for g, p in gates if g.lower() == str(live_gate).lower()]
        else:
            hit = sorted(gates, key=lambda gp: len(gp[1]))[-1:]
        if not hit:
            notes.append(f"{sid}: no gate named '{live_gate}' in the workspace; skipped")
            continue
        gname, gpath = hit[0]
        path = "/".join(list(gpath[1:]) + [gname])
        labels = sample.pnn_labels
        if pe_param not in labels:
            raise ValueError(f"{sample.original_filename}: no parameter '{pe_param}'")
        mem = wsp.get_gate_membership(sid, gname, gate_path=gpath)
        x = sample.get_events(source="raw")[mem, labels.index(pe_param)]
        try:
            tr = wsp.get_transform(sid, pe_param)
        except Exception:
            tr = None
        if tr is None:
            notes.append(f"{sid}: no display transform for {pe_param} in the workspace; used the default biex")
            tr = biex()
        plate = str(sample.metadata.get("plateid") or "")
        well = sample.metadata.get("wellid")
        name = sid if (not well or sid.upper().startswith(str(well).upper())) else f"{well}-{sid}"
        t = tables.setdefault(plate, StatsTable(str(wsp_path), [f"{path} | Count",
                                                                  f"{path} | Geometric Mean ({pe_param})"]))
        t.rows[name] = {t.headers[0]: int(mem.sum()), t.headers[1]: flowjo_gmean(x, tr)}
    return tables, notes


def wsp_gate_names(wsp_path):
    """Names of every gate (Population) in a FlowJo workspace, read from its XML."""
    text = Path(wsp_path).read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r'<Population\b[^>]*\bname="([^"]*)"', text))


def is_bead_workspace(wsp_path):
    """True when the workspace holds the four Quantibrite bead gates (Low, Med Low, Med High, High)."""
    names = {n.strip().lower() for n in wsp_gate_names(wsp_path)}
    return all(g.lower() in names for g in BEAD_GATES)


def gate_bead_workspace(wsp_path, fcs_dir, pe_param):
    """Apply hand-drawn bead gates (Low, Med Low, Med High, High) from a workspace.

    Returns ({sample stem: StatsTable}, notes), one table per bead .fcs, in FlowJo bead export layout.
    """
    _quiet()
    fk = _fk()
    notes = []
    wsp = fk.Workspace(str(wsp_path), fcs_samples=str(fcs_dir))
    sids = wsp.get_sample_ids()
    if not sids:
        raise ValueError(f"{Path(wsp_path).name}: none of its samples were found in {fcs_dir}")
    tables = {}
    for sid in sorted(sids):
        try:
            wsp.analyze_samples(sample_id=sid, use_mp=False)
        except Exception as e:
            notes.append(f"{sid}: bead gating failed ({e}); skipped")
            continue
        sample = wsp.get_sample(sid)
        if pe_param not in sample.pnn_labels:
            raise ValueError(f"{sample.original_filename}: no parameter '{pe_param}'")
        gates = {g.lower(): (g, p) for g, p in wsp.get_gate_ids(sid)}
        if not all(g.lower() in gates for g in BEAD_GATES):
            notes.append(f"{sid}: not all bead gates ({', '.join(BEAD_GATES)}) are drawn; skipped")
            continue
        try:
            tr = wsp.get_transform(sid, pe_param)
        except Exception:
            tr = None
        tr = tr or biex()
        pe = sample.get_events(source="raw")[:, sample.pnn_labels.index(pe_param)]
        headers, row = [], {}
        for g in BEAD_GATES:
            gname, gpath = gates[g.lower()]
            path = "/".join(list(gpath[1:]) + [gname])
            mem = wsp.get_gate_membership(sid, gname, gate_path=gpath)
            headers += [f"{path} | Count", f"{path} | Geometric Mean ({pe_param})"]
            row[headers[-2]] = int(mem.sum())
            row[headers[-1]] = flowjo_gmean(pe[mem], tr)
        stem = Path(str(sample.original_filename or sid)).stem
        t = StatsTable(str(wsp_path), headers)
        t.rows[stem] = row
        tables[stem] = t
        notes.append(f"{Path(wsp_path).name}: bead gates from the workspace applied to {stem}")
    return tables, notes


def write_table(t: StatsTable, path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Export"
    ws.append([""] + t.headers)
    for name, vals in t.rows.items():
        ws.append([name] + [vals.get(h) for h in t.headers])
    ws.column_dimensions["A"].width = 24
    for col in "BCDEFGHI":
        ws.column_dimensions[col].width = 30
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return str(path)


def gate_folder(folder, setup, out_dir=None):
    """Gate every .wsp + .fcs in folder. Returns (cell export paths, bead export paths, notes).

    Cell exports are named '<Plate ID>_<wsp name>_gated.xlsx' (plate from the .fcs 'plateid' keyword, or the only
    plate in the setup). Beads are gated only from a bead tube workspace (gates Low, Med Low, Med High, High).
    Nothing is gated automatically: .fcs files no workspace covers are listed in the notes and left out.
    """
    folder = Path(folder)
    out_dir = Path(out_dir or folder / "qfacs_gated")
    exp = setup.experiment
    pe, live = exp.get("pe_parameter"), exp.get("live_gate")
    notes, cells, beads = [], [], []
    plates = {norm_plate(p["plate_id"]): p["plate_id"] for p in setup.plates if p.get("plate_id")}
    fcs = sorted(p for p in folder.rglob("*.fcs"))
    bead_names = {Path(str(b.get("data_file"))).stem.lower() for b in setup.beads if b.get("data_file")}
    used = set()
    for wsp in sorted(folder.rglob("*.wsp")):
        dirs = sorted({p.parent for p in fcs})
        if is_bead_workspace(wsp):
            # a bead tube workspace: use its hand-drawn Low / Med Low / Med High / High gates
            for d in dirs:
                try:
                    tables, n = gate_bead_workspace(wsp, d, pe)
                except ValueError:
                    continue
                notes += n
                for stem, t in tables.items():
                    beads.append(write_table(t, out_dir / f"{stem}.xlsx"))
                    used |= {p for p in d.glob("*.fcs") if p.stem == stem}
            continue
        for d in dirs:
            try:
                tables, n = gate_workspace(wsp, d, pe, live)
            except ValueError:
                continue  # this workspace's samples are not in this folder
            notes += n
            for plate_kw, t in tables.items():
                pid = plates.get(norm_plate(plate_kw)) or (setup.plates[0]["plate_id"] if len(setup.plates) == 1 else None)
                if not pid:
                    notes.append(f"{wsp.name}: plate '{plate_kw}' not on the Plates sheet; skipped")
                    continue
                cells.append(write_table(t, out_dir / f"{pid}_{wsp.stem}_gated.xlsx"))
                notes.append(f"{wsp.name}: gated {len(t.rows)} samples from {d.name} for {pid}")
            # a bead .fcs named on the Beads sheet may sit next to the plate's .fcs files
            used |= {p for p in d.glob("*.fcs") if p.stem.lower() not in bead_names and "bead" not in p.name.lower()}
    rest = [p for p in fcs if p not in used]
    if rest:
        notes.append(f"{len(rest)} .fcs file(s) not covered by a FlowJo workspace were not used (no automatic gating); "
                     "gate them in FlowJo and export the table")
    return cells, beads, notes
