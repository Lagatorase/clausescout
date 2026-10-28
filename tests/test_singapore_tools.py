"""The Singapore download and labelling helpers, without touching the network."""

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_has_unique_edgar_urls():
    contracts = yaml.safe_load((ROOT / "datasets/singapore/manifest.yaml").read_text())["contracts"]
    assert len(contracts) >= 15
    assert len({c["id"] for c in contracts}) == len(contracts)
    assert all(c["url"].startswith("https://www.sec.gov/Archives/edgar/data/") for c in contracts)


def test_html_to_text_keeps_blocks_and_drops_scripts():
    fetch = _load("fetch_singapore")
    text = fetch.html_to_text("<p>One&nbsp; two</p><script>x()</script><div>Three</div>")
    assert text == "One two\n\nThree\n"


def test_label_validation_keeps_only_real_spans():
    tool = _load("label_tool")
    text = "This Agreement is governed by the laws of Singapore."
    saved = tool.validate("c", {"labeller": "me", "labels": {
        "Governing Law": {"status": "present", "spans": [{"start": 0, "end": len(text)}]},
        "Non-Compete": {"status": "absent"},
        "Not A Type": {"status": "absent"},
        "Exclusivity": {"status": "present", "spans": [{"start": 5, "end": 999}]},
    }}, text)
    assert saved["labels"]["Governing Law"]["spans"][0]["text"] == text
    assert saved["labels"]["Non-Compete"] == {"status": "absent", "spans": []}
    # Unknown types and present labels with no valid span are dropped.
    assert set(saved["labels"]) == {"Governing Law", "Non-Compete"}


def test_label_server_round_trip(tmp_path):
    import json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    tool = _load("label_tool")
    cid = tool.contract_ids()[0]
    tool.TEXT_DIR, tool.LABEL_DIR = tmp_path / "text", tmp_path / "labels"
    tool.TEXT_DIR.mkdir()
    (tool.TEXT_DIR / f"{cid}.txt").write_text("Governed by the laws of Singapore.", "utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), tool.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "Nothing is pre-filled" in page
        start = json.loads(urllib.request.urlopen(f"{base}/api/contracts/{cid}").read())
        assert start["labels"] == {}
        body = json.dumps({"labels": {"Governing Law": {"status": "present",
                                                        "spans": [{"start": 0, "end": 33}]}}})
        req = urllib.request.Request(f"{base}/api/contracts/{cid}", body.encode(), method="POST")
        assert json.loads(urllib.request.urlopen(req).read())["decided"] == 1
        saved = json.loads((tool.LABEL_DIR / f"{cid}.json").read_text("utf-8"))
        span = saved["labels"]["Governing Law"]["spans"][0]
        assert span["text"] == "Governed by the laws of Singapore"
    finally:
        server.shutdown()
