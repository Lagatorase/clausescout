"""A small local tool for labelling the Singapore contracts by hand, one clause type at a time.

It starts with no labels and never shows model output, so the labels can't be nudged by what
ClauseScout predicts. For each of the 41 CUAD clause types you either mark it absent or select
the clause text and add it. Labels are saved as character offsets into the text from
scripts/fetch_singapore.py, in datasets/singapore/labels/<id>.json.

Usage: python scripts/label_tool.py   then open http://127.0.0.1:8765
"""

import json
import re
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

from clausescout.data.cuad import CATEGORIES

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets" / "singapore" / "manifest.yaml"
TEXT_DIR = ROOT / "data" / "singapore" / "text"
LABEL_DIR = ROOT / "datasets" / "singapore" / "labels"
SAFE_ID = re.compile(r"^[a-z0-9-]+$")


def contract_ids() -> list[str]:
    return [c["id"] for c in yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["contracts"]]


def load_labels(cid: str) -> dict:
    path = LABEL_DIR / f"{cid}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"contract": cid, "labels": {}}


def validate(cid: str, data: dict, text: str) -> dict:
    """Keeps only well-formed labels, and checks every span's text against the contract."""
    labels = {}
    for cat, entry in data.get("labels", {}).items():
        if cat not in CATEGORIES or entry.get("status") not in ("present", "absent"):
            continue
        spans = []
        for s in entry.get("spans", []):
            start, end = int(s["start"]), int(s["end"])
            if 0 <= start < end <= len(text):
                spans.append({"start": start, "end": end, "text": text[start:end]})
        if entry["status"] == "present" and not spans:
            continue
        labels[cat] = {"status": entry["status"], "spans": spans}
    return {"contract": cid, "labeller": str(data.get("labeller", ""))[:100],
            "saved": datetime.now(UTC).isoformat(timespec="seconds"), "labels": labels}


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, status=200, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _contract(self):
        # Paths look like /api/contracts/<id>; the id must be in the manifest.
        cid = self.path.rstrip("/").split("/")[-1]
        if not SAFE_ID.match(cid) or cid not in contract_ids():
            return None, None
        path = TEXT_DIR / f"{cid}.txt"
        return cid, path.read_text(encoding="utf-8") if path.exists() else None

    def do_GET(self):
        if self.path == "/":
            return self._send(PAGE.encode("utf-8"), kind="text/html; charset=utf-8")
        if self.path == "/api/contracts":
            out = []
            for cid in contract_ids():
                done = len(load_labels(cid)["labels"])
                out.append({"id": cid, "fetched": (TEXT_DIR / f"{cid}.txt").exists(),
                            "decided": done})
            return self._send({"contracts": out, "categories": CATEGORIES})
        if self.path.startswith("/api/contracts/"):
            cid, text = self._contract()
            if cid is None or text is None:
                return self._send({"error": "unknown or not fetched"}, 404)
            return self._send({"id": cid, "text": text, **load_labels(cid)})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/api/contracts/"):
            return self._send({"error": "not found"}, 404)
        cid, text = self._contract()
        if cid is None or text is None:
            return self._send({"error": "unknown or not fetched"}, 404)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        saved = validate(cid, body, text)
        LABEL_DIR.mkdir(parents=True, exist_ok=True)
        tmp = LABEL_DIR / f"{cid}.json.tmp"
        tmp.write_text(json.dumps(saved, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(LABEL_DIR / f"{cid}.json")
        self._send({"ok": True, "decided": len(saved["labels"])})

    def log_message(self, *args):
        pass


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ClauseScout labelling</title><style>
:root { --bg:#fff; --fg:#1d1f23; --muted:#5c6370; --line:#d8dbe0; --mark:#fde68a; --sel:#dbeafe; }
@media (prefers-color-scheme: dark) { :root { --bg:#16181c; --fg:#e6e7ea; --muted:#9aa0aa;
  --line:#2e3238; --mark:#6b5310; --sel:#1e3a5f; } }
body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.5 system-ui,sans-serif;
  display:grid; grid-template-columns:220px 1fr 340px; height:100vh; }
aside, main, section { overflow:auto; padding:12px; border-right:1px solid var(--line); }
pre { white-space:pre-wrap; font:13px/1.55 ui-monospace,monospace; margin:0; }
mark { background:var(--mark); color:inherit; } .muted { color:var(--muted); }
button { font:inherit; margin:2px 2px 0 0; cursor:pointer; }
.cat { border-bottom:1px solid var(--line); padding:6px 0; } .cat.current { background:var(--sel); }
.present b { color:#16a34a; } .absent b { color:var(--muted); text-decoration:line-through; }
li { cursor:pointer; } li.on { font-weight:600; }
</style></head><body>
<aside><h3>Contracts</h3><ul id="list"></ul>
<p class="muted">Select clause text, then press Add on a clause type. Mark types that are not in
the contract as Absent. Nothing is pre-filled.</p>
<label>Your name <input id="who" size="14"></label></aside>
<main><pre id="doc" class="muted">Choose a contract.</pre></main>
<section><div id="progress"></div><div id="cats"></div></section>
<script>
let cats = [], cur = null, data = null;
const $ = id => document.getElementById(id);
async function loadList() {
  const r = await (await fetch('/api/contracts')).json();
  cats = r.categories;
  $('list').innerHTML = '';
  for (const c of r.contracts) {
    const li = document.createElement('li');
    li.textContent = `${c.id} (${c.fetched ? c.decided + '/' + cats.length : 'not fetched'})`;
    if (c.id === cur) li.className = 'on';
    if (c.fetched) li.onclick = () => openContract(c.id);
    $('list').appendChild(li);
  }
}
async function openContract(id) {
  cur = id;
  data = await (await fetch('/api/contracts/' + id)).json();
  $('who').value = data.labeller || $('who').value;
  render(); loadList();
}
function selectionOffsets() {
  const sel = window.getSelection();
  if (!sel.rangeCount || sel.isCollapsed) return null;
  const range = sel.getRangeAt(0);
  if (!$('doc').contains(range.commonAncestorContainer)) return null;
  // The offset is the length of all text before the selection inside the document.
  const before = document.createRange();
  before.setStart($('doc'), 0); before.setEnd(range.startContainer, range.startOffset);
  const start = before.toString().length;
  return {start, end: start + range.toString().length};
}
function render() {
  const text = data.text, spans = [];
  for (const [cat, e] of Object.entries(data.labels))
    for (const s of e.spans || []) spans.push({...s, cat});
  spans.sort((a, b) => a.start - b.start);
  const doc = $('doc'); doc.className = ''; doc.textContent = '';
  let pos = 0;
  for (const s of spans) {
    if (s.start < pos) continue;
    doc.append(text.slice(pos, s.start));
    const m = document.createElement('mark'); m.title = s.cat;
    m.textContent = text.slice(s.start, s.end); doc.append(m); pos = s.end;
  }
  doc.append(text.slice(pos));
  const decided = Object.keys(data.labels).length;
  $('progress').innerHTML = `<b>${decided} of ${cats.length}</b> clause types decided`;
  $('cats').innerHTML = '';
  for (const cat of cats) {
    const e = data.labels[cat], div = document.createElement('div');
    div.className = 'cat ' + (e ? e.status : '');
    div.innerHTML = `<b></b> <span class="muted"></span><br>`;
    div.querySelector('b').textContent = cat;
    const note = !e ? '' : e.status === 'present' ? e.spans.length + ' span(s)' : 'absent';
    div.querySelector('span').textContent = note;
    const add = document.createElement('button'); add.textContent = 'Add selection';
    add.onclick = () => {
      const o = selectionOffsets();
      if (!o) return alert('Select text in the contract first.');
      const old = data.labels[cat];
      const entry = old && old.status === 'present' ? old : {status: 'present', spans: []};
      entry.spans.push(o); data.labels[cat] = entry; save();
    };
    const absent = document.createElement('button'); absent.textContent = 'Absent';
    absent.onclick = () => { data.labels[cat] = {status: 'absent', spans: []}; save(); };
    const clear = document.createElement('button'); clear.textContent = 'Clear';
    clear.onclick = () => { delete data.labels[cat]; save(); };
    div.append(add, absent, clear);
    $('cats').appendChild(div);
  }
}
async function save() {
  await fetch('/api/contracts/' + cur, {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({labeller: $('who').value, labels: data.labels})});
  await openContract(cur);
}
loadList();
</script></body></html>
"""


def main() -> None:
    # I bind to localhost only, so the tool is never reachable from the network.
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Labelling tool on http://127.0.0.1:8765 (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
