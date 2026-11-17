"""qFACS as a page in the browser: pick the setup workbook and the FlowJo exports, press Run, download the results.

Started with `python -m qfacs app` or by double-clicking the packaged qFACS program. It is a small web server on
this computer only (127.0.0.1): files go from the browser to a temporary folder here, never to the internet.
Only the Python standard library is used for the server, so nothing extra has to be installed.
"""
from __future__ import annotations

import base64
import json
import socket
import sys
import tempfile
import threading
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__

MAX_BODY = 300 * 1024 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_results: dict = {}            # id -> (file name, bytes) of the last few results workbooks
_KEEP = 20


def _save_upload(folder: Path, item: dict) -> Path:
    """Write one uploaded file {name, data (base64)} into folder under its own file name."""
    name = Path(str(item.get("name") or "").replace("\\", "/")).name
    if not name:
        raise ValueError("a file arrived without a name")
    path = folder / name
    path.write_bytes(base64.b64decode(item.get("data") or ""))
    return path


def _save_setup(folder: Path, body: dict) -> Path:
    if not body.get("setup"):
        raise ValueError("Choose the setup workbook first.")
    path = _save_upload(folder, body["setup"])
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        raise ValueError(f"{path.name} is not a setup workbook. The setup is the filled-in qFACS setup template (.xlsx); "
                         "FlowJo exports go in step 2.")
    return path


def _issue(i) -> dict:
    return {"level": i.level, "where": i.sheet + (f" row {i.row}" if i.row else ""), "message": i.message}


def api_check(body: dict) -> dict:
    """Validate the setup workbook only."""
    from .runner import check_setup
    from .validate import summarize
    from .wellmap import expand_wells
    with tempfile.TemporaryDirectory() as tmp:
        setup, issues = check_setup(_save_setup(Path(tmp), body))
        errors = any(i.level == "error" for i in issues)
        wells = 0 if errors else len(expand_wells(setup)[0])
    return {"ok": not errors, "issues": [_issue(i) for i in issues], "totals": summarize(issues), "wells": wells,
            "experiment": setup.experiment.get("experiment_id") or ""}


def api_run(body: dict) -> dict:
    """Setup workbook + exports -> summary for the page and the results workbook kept for download."""
    from .report import _flagtext, sig3
    from .runner import report_lines, run_analysis
    from .validate import summarize
    if not body.get("setup"):
        raise ValueError("Choose the setup workbook first.")
    if not body.get("files"):
        raise ValueError("Add the FlowJo export files (cells and beads) first.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "setup").mkdir()
        (tmp / "data").mkdir()
        setup_path = _save_setup(tmp / "setup", body)
        for f in body["files"]:
            _save_upload(tmp / "data", f)
        res, out = run_analysis(setup_path, [tmp / "data"], source=setup_path.name)
        out = Path(out)
        log = report_lines(res, out.name)
        rid = uuid.uuid4().hex
        _results[rid] = (out.name, out.read_bytes())
        for old in list(_results)[:-_KEEP]:
            del _results[old]

    def value(f):
        if f is None:
            return "no isotype"
        return "ND" if f.status == "ND" else (f"{sig3(f.antigens):,.0f}" if f.antigens is not None else "not fitted")

    pairs = []
    for (line, ab), p in res.by_pair.items():
        iso, ns = p.get("Isotype"), p.get("NS")
        pairs.append({"cell_line": line, "antibody": ab, "iso": value(iso), "ns": value(ns) if ns else "",
                      "ratio": f"{ns.ns_vs_iso:.2f}" if ns and ns.ns_vs_iso is not None else "-",
                      "iso_flags": _flagtext(iso.flags) if iso else "no isotype data: see NS fit",
                      "ns_flags": _flagtext(ns.flags) if ns else ""})
    lots = {b.get("bead_run"): b.get("kit_lot") for b in res.setup.beads}
    beads = [{"text": f"Bead run {run} (lot {lots.get(run) or '?'}): {c.qc}, slope {c.slope:.4f}, R² {c.r2:.5f}",
              "ok": c.qc == "PASS"} for run, c in res.beads.items()]
    errors = any(i.level == "error" for i in res.issues)
    return {"ok": not errors, "experiment": res.setup.experiment.get("experiment_id") or "", "pairs": pairs, "beads": beads,
            "files": [{"file": d["file"], "plate": d["plate"], "cell_line": d["cell_line"],
                       "from": "file name" if d["named"] else "Layout", "wells": d["wells"], "antibodies": d["antibodies"]}
                      for d in res.data_files],
            "issues": [_issue(i) for i in sorted(res.issues, key=lambda i: i.level != "error")],
            "notes": list(res.notes), "calibrated": bool(res.beads), "totals": summarize(res.issues), "log": log, "result": {"id": rid, "name": out.name}}


def template_bytes() -> bytes:
    from .template import write_setup
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "qFACS_setup_template.xlsx"
        write_setup(str(p))
        return p.read_bytes()


class Handler(BaseHTTPRequestHandler):
    server_version = "qFACS"

    def log_message(self, fmt, *args):   # keep the console window quiet
        pass

    def _send(self, code, body: bytes, ctype, filename=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, PAGE.replace("{{version}}", __version__).encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/template":
            self._send(200, template_bytes(), XLSX, "qFACS_setup_template.xlsx")
        elif path.startswith("/api/result/"):
            hit = _results.get(path.rsplit("/", 1)[1])
            if hit:
                self._send(200, hit[1], XLSX, hit[0].replace('"', ""))
            else:
                self._send(404, b"That result is no longer kept. Run the analysis again.", "text/plain; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        handlers = {"/api/check": api_check, "/api/run": api_run}
        fn = handlers.get(self.path.split("?")[0])
        if fn is None:
            return self._send(404, b"not found", "text/plain")
        # JSON only: a web page on another site cannot send this without the browser asking first, which is refused
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._json({"error": "expected JSON"}, 415)
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self._json({"error": "These files are too large. Add only the FlowJo table exports (.xls), not .fcs or .wsp files."}, 413)
        try:
            self._json(fn(json.loads(self.rfile.read(n) or b"{}")))
        except ValueError as e:
            self._json({"error": str(e)})
        except Exception as e:  # show the reason on the page instead of a dead button
            traceback.print_exc()
            self._json({"error": f"{type(e).__name__}: {e}"})


def make_server(host="127.0.0.1", port=8765) -> ThreadingHTTPServer:
    """Server on the wanted port, or on any free one when that port is taken."""
    try:
        return ThreadingHTTPServer((host, port), Handler)
    except OSError:
        return ThreadingHTTPServer((host, 0), Handler)


def serve(host="127.0.0.1", port=8765, open_browser=True) -> int:
    httpd = make_server(host, port)
    shown = "localhost" if host in ("127.0.0.1", "localhost") else (socket.gethostname() if host == "0.0.0.0" else host)
    url = f"http://{shown}:{httpd.server_address[1]}/"
    out = sys.stdout or open(Path(tempfile.gettempdir()) / "qfacs_app.log", "w")
    print(f"qFACS {__version__} is running.\n\n  Open {url} in your browser (it should open by itself).\n\n"
          "  Leave this window open while you use qFACS. Close it to quit.", file=out, flush=True)
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>qFACS</title>
<style>
  :root { --ink:#1c2430; --soft:#5b6675; --line:#d8dee6; --bg:#f4f6f9; --card:#fff; --accent:#1f6feb; --accent-ink:#fff;
          --good:#1a7f37; --good-bg:#e6f4ea; --bad:#b42318; --bad-bg:#fdecea; --warn:#8a5a00; --warn-bg:#fff4d6; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  main { max-width:980px; margin:0 auto; padding:28px 16px 60px; }
  h1 { font-size:26px; margin:0; } h2 { font-size:17px; margin:0 0 4px; } h3 { font-size:15px; margin:22px 0 8px; }
  .sub { color:var(--soft); margin:2px 0 22px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:18px 20px; margin-bottom:16px; }
  .step { display:inline-flex; width:24px; height:24px; border-radius:50%; background:var(--accent); color:var(--accent-ink);
          align-items:center; justify-content:center; font-size:13px; font-weight:700; margin-right:8px; }
  .hint { color:var(--soft); font-size:13.5px; margin:2px 0 12px; }
  .drop { border:2px dashed var(--line); border-radius:8px; padding:18px; text-align:center; color:var(--soft); cursor:pointer;
          transition:border-color .15s, background .15s; }
  .drop:hover, .drop.over, .drop:focus-visible { border-color:var(--accent); background:#f0f6ff; outline:none; }
  .drop b { color:var(--accent); }
  input[type=file] { display:none; }
  ul.files { list-style:none; margin:10px 0 0; padding:0; }
  ul.files li { display:flex; align-items:center; gap:10px; padding:6px 10px; border:1px solid var(--line); border-radius:6px;
                margin-top:6px; overflow-wrap:anywhere; }
  ul.files .name { flex:1; }
  .tag { font-size:12px; padding:1px 8px; border-radius:20px; background:#eef1f5; color:var(--soft); white-space:nowrap; }
  .tag.bead { background:var(--warn-bg); color:var(--warn); }
  .x { border:0; background:none; color:var(--soft); font-size:18px; cursor:pointer; line-height:1; padding:2px 6px; }
  .x:hover { color:var(--bad); }
  button.btn, a.btn { font:inherit; font-weight:600; border-radius:8px; padding:9px 18px; cursor:pointer; text-decoration:none;
                      display:inline-block; border:1px solid var(--line); background:#fff; color:var(--ink); }
  button.btn:hover, a.btn:hover { border-color:var(--accent); }
  .btn.primary { background:var(--accent); border-color:var(--accent); color:var(--accent-ink); }
  .btn.primary:hover { filter:brightness(1.08); }
  .btn:disabled { opacity:.5; cursor:default; }
  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  .banner { border-radius:8px; padding:10px 14px; margin:12px 0 0; }
  .banner.good { background:var(--good-bg); color:var(--good); } .banner.bad { background:var(--bad-bg); color:var(--bad); }
  .banner.warn { background:var(--warn-bg); color:var(--warn); }
  .scroll { overflow-x:auto; }
  table { border-collapse:collapse; width:100%; font-size:14px; }
  th, td { border:1px solid var(--line); padding:6px 10px; text-align:left; vertical-align:top; }
  th { background:#eef1f5; font-weight:600; white-space:nowrap; }
  td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
  td.flag { font-size:13px; } td.flag.ok { color:var(--good); } td.flag.no { color:var(--warn); }
  .lvl { font-size:12px; font-weight:700; padding:1px 7px; border-radius:4px; }
  .lvl.error { background:var(--bad-bg); color:var(--bad); } .lvl.warning { background:var(--warn-bg); color:var(--warn); }
  details { margin-top:14px; } summary { cursor:pointer; color:var(--soft); }
  pre { background:#f6f8fa; border:1px solid var(--line); border-radius:6px; padding:10px; overflow-x:auto; font-size:12.5px; }
  footer { color:var(--soft); font-size:13px; margin-top:20px; }
  [hidden] { display:none !important; }
</style>
</head>
<body>
<main>
  <h1>qFACS</h1>
  <p class="sub">Setup workbook + FlowJo exports &rarr; antigens per cell. Files stay on this computer.</p>

  <section class="card">
    <h2><span class="step">1</span>Setup workbook</h2>
    <p class="hint">The filled-in experiment setup (.xlsx). Starting a new experiment?
      <a href="/api/template">Download a blank setup template</a>.</p>
    <div class="drop" id="setupDrop" tabindex="0" role="button"><b>Choose the setup workbook</b> or drop it here</div>
    <input type="file" id="setupInput" accept=".xlsx,.xlsm">
    <ul class="files" id="setupList"></ul>
    <div class="row" style="margin-top:12px"><button class="btn" id="checkBtn" disabled>Check setup</button>
      <span class="hint" style="margin:0">Optional: checks the workbook before any data is added.</span></div>
    <div id="checkOut"></div>
  </section>

  <section class="card">
    <h2><span class="step">2</span>FlowJo exports</h2>
    <p class="hint">The Table Editor exports for this experiment: one per plate and cell line, named
      <code>&lt;Plate ID&gt; &lt;cell line&gt;.xls</code> (for example <code>Plate1 A431.xls</code>), plus the bead export
      with &ldquo;bead&rdquo; in its name. Select them all at once.</p>
    <div class="drop" id="dataDrop" tabindex="0" role="button"><b>Choose the export files</b> or drop them here</div>
    <input type="file" id="dataInput" multiple accept=".xls,.xlsx,.csv,.txt,.tsv">
    <ul class="files" id="dataList"></ul>
  </section>

  <section class="card">
    <h2><span class="step">3</span>Run</h2>
    <div class="row" style="margin-top:10px"><button class="btn primary" id="runBtn" disabled>Run analysis</button>
      <span class="hint" id="runHint" style="margin:0">Add the setup workbook and the exports first.</span></div>
    <div id="runOut"></div>
  </section>

  <footer>qfacs {{version}}. Gating and unmixing are done in FlowJo; this page reads only the exported tables.</footer>
</main>
<script>
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let setupFile = null, dataFiles = [];

function wire(drop, input, onFiles) {
  drop.addEventListener("click", () => input.click());
  drop.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  input.addEventListener("change", () => { onFiles([...input.files]); input.value = ""; });
  ["dragenter", "dragover"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => onFiles([...e.dataTransfer.files]));
}
// a stray drop outside the boxes should not make the browser open the file
["dragover", "drop"].forEach(t => window.addEventListener(t, e => e.preventDefault()));

wire($("setupDrop"), $("setupInput"), files => {
  const f = files.find(f => /\.xls[xm]$/i.test(f.name));
  if (!f) return;
  setupFile = f; $("checkOut").innerHTML = ""; render();
});
wire($("dataDrop"), $("dataInput"), files => {
  for (const f of files) {
    if (!/\.(xlsx?|csv|txt|tsv)$/i.test(f.name) || f.name.startsWith("~$")) continue;
    dataFiles = dataFiles.filter(d => d.name !== f.name);
    dataFiles.push(f);
  }
  dataFiles.sort((a, b) => a.name.localeCompare(b.name));
  render();
});

function render() {
  $("setupList").innerHTML = setupFile
    ? `<li><span class="name">${esc(setupFile.name)}</span><button class="x" data-k="setup" title="Remove">&times;</button></li>` : "";
  $("dataList").innerHTML = dataFiles.map((f, i) => {
    const bead = /bead/i.test(f.name);
    return `<li><span class="name">${esc(f.name)}</span><span class="tag ${bead ? "bead" : ""}">${bead ? "bead export" : "cell export"}</span>` +
           `<button class="x" data-k="${i}" title="Remove">&times;</button></li>`;
  }).join("");
  $("checkBtn").disabled = !setupFile;
  const ready = setupFile && dataFiles.length;
  $("runBtn").disabled = !ready;
  $("runHint").textContent = ready ? `${dataFiles.length} export file${dataFiles.length > 1 ? "s" : ""} ready.`
    : "Add the setup workbook and the exports first.";
}
document.addEventListener("click", e => {
  const k = e.target.closest(".x")?.dataset.k;
  if (k === undefined) return;
  if (k === "setup") { setupFile = null; $("checkOut").innerHTML = ""; } else dataFiles.splice(+k, 1);
  render();
});

const pack = file => new Promise((ok, bad) => {
  const r = new FileReader();
  r.onload = () => ok({name: file.name, data: r.result.slice(r.result.indexOf(",") + 1)});
  r.onerror = () => bad(new Error("Could not read " + file.name + ". If it is open in Excel, close it and try again."));
  r.readAsDataURL(file);
});
async function post(url, body) {
  let resp;
  try {
    resp = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  } catch (e) {
    throw new Error("qFACS is not running any more. Start it again (the qFACS window must stay open), then reload this page.");
  }
  const out = await resp.json();
  if (out.error) throw new Error(out.error);
  return out;
}
const issuesTable = issues => !issues.length ? "" :
  `<div class="scroll"><table><tr><th></th><th>Where</th><th>What</th></tr>` + issues.map(i =>
    `<tr><td><span class="lvl ${esc(i.level)}">${esc(i.level)}</span></td><td>${esc(i.where)}</td><td>${esc(i.message)}</td></tr>`).join("") +
  `</table></div>`;
const banner = (kind, text) => `<div class="banner ${kind}">${text}</div>`;

$("checkBtn").addEventListener("click", async () => {
  const btn = $("checkBtn"); btn.disabled = true; btn.textContent = "Checking...";
  try {
    const r = await post("/api/check", {setup: await pack(setupFile)});
    $("checkOut").innerHTML = (r.ok
      ? banner(r.issues.length ? "warn" : "good", `Setup is usable: ${esc(r.totals)}, ${r.wells} wells in the Layout.` +
               (r.issues.length ? " Warnings are QC flags that travel with the results." : ""))
      : banner("bad", `Setup has errors to fix before it can run: ${esc(r.totals)}.`)) +
      (r.issues.length ? "<h3>Setup issues</h3>" + issuesTable(r.issues) : "");
  } catch (e) { $("checkOut").innerHTML = banner("bad", esc(e.message)); }
  btn.textContent = "Check setup"; btn.disabled = !setupFile;
});

$("runBtn").addEventListener("click", async () => {
  const btn = $("runBtn"); btn.disabled = true; btn.textContent = "Running...";
  $("runOut").innerHTML = "";
  try {
    const r = await post("/api/run", {setup: await pack(setupFile), files: await Promise.all(dataFiles.map(pack))});
    const link = `/api/result/${r.result.id}`;
    let h = r.ok && !r.calibrated
      ? banner("bad", "No bead export was read, so nothing could be calibrated to antigens per cell. Add the bead export " +
               "(its file name must contain &ldquo;bead&rdquo;, or be named on the Beads sheet) and run again.")
      : r.ok ? banner("good", `Done: ${esc(r.experiment)} &middot; ${esc(r.totals)}.`)
      : banner("bad", `No results were calculated: ${esc(r.totals)}. Fix the errors listed below and run again.`);
    h += `<div class="row" style="margin-top:14px"><a class="btn primary" id="download" href="${link}" download="${esc(r.result.name)}">` +
         `Download results workbook</a><span class="hint" style="margin:0">${esc(r.result.name)} (Summary, Plots, Fits, Wells, Beads, Method, Issues)</span></div>`;
    if (r.beads.length) h += r.beads.map(b => banner(b.ok ? "good" : "warn", esc(b.text))).join("");
    if (r.pairs.length) {
      h += `<h3>Antigens per cell</h3><div class="scroll"><table id="summary"><tr><th>Cell line</th><th>Antibody</th>` +
           `<th>Isotype subtracted</th><th>NS fit</th><th>NS &divide; isotype</th><th>Flags: isotype subtracted</th><th>Flags: NS fit</th></tr>` +
        r.pairs.map(p => {
          const cls = f => f === "OK" ? "ok" : "no";
          return `<tr><td><b>${esc(p.cell_line)}</b></td><td>${esc(p.antibody)}</td><td class="num">${esc(p.iso)}</td>` +
                 `<td class="num">${esc(p.ns)}</td><td class="num">${esc(p.ratio)}</td>` +
                 `<td class="flag ${cls(p.iso_flags)}">${esc(p.iso_flags)}</td><td class="flag ${cls(p.ns_flags)}">${esc(p.ns_flags)}</td></tr>`;
        }).join("") + `</table></div>`;
    }
    if (r.files.length) {
      h += `<h3>Data files</h3><div class="scroll"><table><tr><th>File</th><th>Plate</th><th>Cell line</th><th>Cell line from</th><th>Wells</th><th>Antibodies</th></tr>` +
        r.files.map(f => `<tr><td>${esc(f.file)}</td><td>${esc(f.plate)}</td><td>${esc(f.cell_line)}</td><td>${esc(f.from)}</td>` +
                         `<td class="num">${esc(f.wells)}</td><td>${esc(f.antibodies)}</td></tr>`).join("") + `</table></div>`;
    }
    if (r.issues.length) h += `<h3>Issues</h3>` + issuesTable(r.issues);
    if (r.notes.length) h += `<h3>Notes</h3><ul>` + r.notes.map(n => `<li>${esc(n)}</li>`).join("") + `</ul>`;
    h += `<details><summary>Full run log</summary><pre>${esc(r.log.join("\n"))}</pre></details>`;
    $("runOut").innerHTML = h;
  } catch (e) { $("runOut").innerHTML = banner("bad", esc(e.message)); }
  btn.textContent = "Run analysis"; render();
});
render();
</script>
</body>
</html>
"""
