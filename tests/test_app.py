"""The browser app's server: same numbers as the command line, from uploaded files."""
import base64
import io
import json
import threading
import urllib.request
from pathlib import Path

import pytest
from openpyxl import load_workbook

from qfacs.app import make_server
from qfacs.runner import run_analysis

EX = Path(__file__).parent.parent / "examples" / "Exp2290_Set2_Plate1"
EXPORTS = ["Plate1_A431.xls", "Plate1_U87.xls", "Quantbrite PE Beads.xls"]


@pytest.fixture(scope="module")
def url():
    httpd = make_server("127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def up(name):
    return {"name": name, "data": base64.b64encode((EX / name).read_bytes()).decode()}


def post(url, path, body, ctype="application/json"):
    req = urllib.request.Request(url + path, json.dumps(body).encode(), {"Content-Type": ctype})
    return json.load(urllib.request.urlopen(req))


def test_page_and_template(url):
    assert b"Run analysis" in urllib.request.urlopen(url + "/").read()
    wb = load_workbook(io.BytesIO(urllib.request.urlopen(url + "/api/template").read()))
    assert {"Experiment", "Beads", "Reagents", "Layout"} <= set(wb.sheetnames)


def test_check(url):
    r = post(url, "/api/check", {"setup": up("Exp2290_Set2_setup.xlsx")})
    assert r["ok"] and r["wells"] == 96 and r["experiment"] == "Exp2290_Set2"


def test_run_matches_command_line(url, tmp_path):
    r = post(url, "/api/run", {"setup": up("Exp2290_Set2_setup.xlsx"), "files": [up(f) for f in EXPORTS]})
    assert r["ok"] and r["calibrated"] and len(r["pairs"]) == 6 and len(r["files"]) == 2
    res, _ = run_analysis(EX / "Exp2290_Set2_setup.xlsx", [EX / f for f in EXPORTS], out=tmp_path / "cli.xlsx")
    cli = {(f.cell_line, f.reagent, f.model): f.antigens for f in res.fits}
    page = {(p["cell_line"], p["antibody"]): p for p in r["pairs"]}
    for (line, ab, model), v in cli.items():
        shown = page[(line, ab)]["iso" if model == "Isotype" else "ns"]
        if v is not None and shown != "ND":
            assert abs(float(shown.replace(",", "")) - v) <= 0.006 * v      # the page shows 3 significant figures
    wb = load_workbook(io.BytesIO(urllib.request.urlopen(f"{url}/api/result/{r['result']['id']}").read()))
    assert {"Summary", "Fits", "Wells", "Beads"} <= set(wb.sheetnames)
    assert r["result"]["name"] == "Exp2290_Set2_qFACS_results.xlsx"


def test_no_bead_export_is_reported(url):
    r = post(url, "/api/run", {"setup": up("Exp2290_Set2_setup.xlsx"), "files": [up(f) for f in EXPORTS[:2]]})
    assert not r["calibrated"]


def test_errors_come_back_as_messages(url):
    assert "setup workbook" in post(url, "/api/run", {"files": [up(EXPORTS[0])]})["error"]
    assert post(url, "/api/run", {"setup": up(EXPORTS[0]), "files": [up(EXPORTS[0])]}).get("error")   # .xls is not a setup
    with pytest.raises(urllib.error.HTTPError):   # only JSON is accepted (blocks posts from other web pages)
        post(url, "/api/run", {}, ctype="text/plain")
