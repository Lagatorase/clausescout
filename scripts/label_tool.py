"""A small local tool for labelling the Singapore contracts by hand, one clause type at a time.

It starts with no labels and never shows model output, so the labels can't be nudged by what
ClauseScout predicts. Each contract gets 11 decisions (clausescout/data/singapore.py): the 8
high-stakes types plus arbitration, SIAC arbitration and data protection. For each one you mark
it absent, or select the exact clause text and add it. Every click is saved straight away, so you
can stop at any point and carry on later. Labels are saved as character offsets into the text
from scripts/fetch_singapore.py, in datasets/singapore/labels/<id>.json.

Usage: python scripts/label_tool.py   then open http://127.0.0.1:8765
"""

import json
import re
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from clausescout.data import singapore
from clausescout.data.singapore import GUIDANCE, LABEL_TYPES

TEXT_DIR = singapore.TEXT_DIR
LABEL_DIR = singapore.LABEL_DIR
SAFE_ID = re.compile(r"^[a-z0-9-]+$")


def contract_ids() -> list[str]:
    return singapore.contract_ids()


def load_labels(cid: str) -> dict:
    return singapore.load_labels(cid, LABEL_DIR)


def validate(cid: str, data: dict, text: str) -> dict:
    """Keeps only well-formed labels, and checks every span's text against the contract."""
    labels = {}
    for cat, entry in data.get("labels", {}).items():
        if cat not in LABEL_TYPES or entry.get("status") not in ("present", "absent"):
            continue
        spans = []
        for s in entry.get("spans", []):
            start, end = int(s["start"]), int(s["end"])
            if 0 <= start < end <= len(text):
                spans.append({"start": start, "end": end, "text": text[start:end]})
        if entry["status"] == "present" and not spans:
            continue
        # An absent type never keeps quotes, so the two states can't get mixed up.
        labels[cat] = {"status": entry["status"], "spans": spans if entry["status"] == "present"
                       else []}
    return {"contract": cid, "labeller": str(data.get("labeller", ""))[:100],
            "saved": datetime.now(UTC).isoformat(timespec="seconds"), "labels": labels}


def save_labels(cid: str, saved: dict) -> None:
    # I write to a temporary file and rename it, so a crash mid-save can't leave half a file.
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = LABEL_DIR / f"{cid}.json.tmp"
    tmp.write_text(json.dumps(saved, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(LABEL_DIR / f"{cid}.json")


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
                labels = load_labels(cid)["labels"]
                out.append({"id": cid, "fetched": (TEXT_DIR / f"{cid}.txt").exists(),
                            "decided": sum(t in labels for t in LABEL_TYPES)})
            return self._send({"contracts": out, "types": LABEL_TYPES, "guidance": GUIDANCE})
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
        save_labels(cid, saved)
        self._send({"ok": True, "decided": len(saved["labels"]), "saved": saved["saved"]})

    def log_message(self, *args):
        pass


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ClauseScout labelling</title><style>
:root { --bg:#fff; --fg:#1d1f23; --muted:#5c6370; --line:#d8dbe0; --mark:#fde68a; --sel:#dbeafe;
  --ok:#16a34a; }
@media (prefers-color-scheme: dark) { :root { --bg:#16181c; --fg:#e6e7ea; --muted:#9aa0aa;
  --line:#2e3238; --mark:#6b5310; --sel:#1e3a5f; --ok:#4ade80; } }
body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.5 system-ui,sans-serif;
  display:grid; grid-template-columns:230px 1fr 360px; height:100vh; }
aside, main, section { overflow:auto; padding:12px; border-right:1px solid var(--line); }
pre { white-space:pre-wrap; font:13px/1.55 ui-monospace,monospace; margin:0; }
mark { background:var(--mark); color:inherit; } .muted { color:var(--muted); }
button { font:inherit; margin:2px 2px 0 0; cursor:pointer; }
#progress { font-size:15px; margin-bottom:4px; } #saved { min-height:1.5em; }
.cat { border-bottom:1px solid var(--line); padding:6px 4px; }
.cat.current { background:var(--sel); }
.cat .guide { display:none; font-size:13px; } .cat.current .guide { display:block; }
.present b { color:var(--ok); } .absent b { color:var(--muted); text-decoration:line-through; }
li { cursor:pointer; } li.on { font-weight:600; } li.done { color:var(--ok); }
</style></head><body>
<aside><h3>Contracts</h3><ol id="list"></ol>
<p class="muted">For the highlighted clause type, select its exact text in the contract and press
Present, or press Absent. Nothing is pre-filled, and every click is saved.</p>
<label>Your name <input id="who" size="14"></label></aside>
<main><pre id="doc" class="muted">Choose a contract.</pre></main>
<section><div id="progress"></div><div id="saved" class="muted"></div>
<button id="next" hidden>Next contract</button><div id="cats"></div></section>
<script>
let types = [], guidance = {}, contracts = [], cur = null, data = null, focus = null;
const $ = id => document.getElementById(id);
async function loadList() {
  const r = await (await fetch('/api/contracts')).json();
  types = r.types; guidance = r.guidance; contracts = r.contracts;
  $('list').innerHTML = '';
  for (const c of contracts) {
    const li = document.createElement('li');
    li.textContent = `${c.id} (${c.fetched ? c.decided + '/' + types.length : 'not fetched'})`;
    li.className = (c.id === cur ? 'on ' : '') + (c.decided === types.length ? 'done' : '');
    if (c.fetched) li.onclick = () => openContract(c.id);
    $('list').appendChild(li);
  }
}
async function openContract(id) {
  cur = id; focus = null;
  data = await (await fetch('/api/contracts/' + id)).json();
  $('who').value = data.labeller || $('who').value;
  $('saved').textContent = data.saved ? 'Last saved ' + data.saved : '';
  await loadList(); render();
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
function current() {
  // The type being labelled: the one clicked, or else the first without a decision.
  if (focus) return focus;
  return types.find(t => !data.labels[t]) || null;
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
  const decided = types.filter(t => data.labels[t]).length;
  const x = contracts.findIndex(c => c.id === cur) + 1, cat = current();
  const step = cat ? `type ${types.indexOf(cat) + 1} of ${types.length}`
                   : `all ${types.length} types done`;
  $('progress').innerHTML = `<b>Contract ${x} of ${contracts.length}</b> &middot; ${step}`
    + `<br><span class="muted">${decided} of ${types.length} decided</span>`;
  $('next').hidden = decided < types.length;
  $('cats').innerHTML = '';
  for (const t of types) {
    const e = data.labels[t], div = document.createElement('div');
    div.className = 'cat ' + (e ? e.status : '') + (t === cat ? ' current' : '');
    div.innerHTML = `<b></b> <span class="muted"></span><div class="guide muted"></div>`;
    div.querySelector('b').textContent = t;
    div.querySelector('b').onclick = () => { focus = t; render(); };
    div.querySelector('.guide').textContent = guidance[t];
    const note = !e ? '' : e.status === 'present' ? e.spans.length + ' quote(s)' : 'absent';
    div.querySelector('span').textContent = note;
    const add = document.createElement('button'); add.textContent = 'Present: add selection';
    add.onclick = () => {
      const o = selectionOffsets();
      if (!o) return alert('Select the clause text in the contract first.');
      const old = data.labels[t];
      const entry = old && old.status === 'present' ? old : {status: 'present', spans: []};
      // Then on to the next undecided type; a second quote goes in with the same button.
      entry.spans.push(o); data.labels[t] = entry; focus = null; save();
    };
    const absent = document.createElement('button'); absent.textContent = 'Absent';
    absent.onclick = () => {
      data.labels[t] = {status: 'absent', spans: []}; focus = null; save();
    };
    const clear = document.createElement('button'); clear.textContent = 'Clear';
    clear.onclick = () => { delete data.labels[t]; focus = t; save(); };
    div.append(document.createElement('br'), add, absent, clear);
    $('cats').appendChild(div);
  }
}
async function save() {
  // Every decision is sent straight away, so stopping the tool never loses more than one click.
  const r = await fetch('/api/contracts/' + cur, {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({labeller: $('who').value, labels: data.labels})});
  if (!r.ok) return alert('Not saved: ' + r.status);
  const keep = focus;
  await openContract(cur);
  focus = keep; render();
}
$('next').onclick = () => {
  const i = contracts.findIndex(c => c.id === cur);
  const nxt = contracts.slice(i + 1).concat(contracts.slice(0, i))
    .find(c => c.fetched && c.decided < types.length);
  if (nxt) openContract(nxt.id); else alert('Every fetched contract is fully labelled.');
};
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
