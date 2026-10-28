"""The ClauseScout API: upload a pack of contracts, review them in the background, read results.

Everything runs on this machine. The server binds to 127.0.0.1 by default and only reaches the
network if the config picks a hosted LLM, which also needs ALLOW_HOSTED_LLM=true.

Run: uvicorn api.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import os
import queue
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from clausescout.data.cuad import CATEGORIES, HIGH_STAKES
from clausescout.data.documents import SUPPORTED, load_document
from clausescout.extraction import build_method
from clausescout.pipeline import ReviewResult, review_document
from clausescout.playbook.engine import load_playbook
from clausescout.report.export import DISCLAIMER, render_html, write_excel

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.environ.get("CLAUSESCOUT_CONFIG", ROOT / "config" / "app.yaml"))
EXPORT_DIR = Path(os.environ.get("CLAUSESCOUT_EXPORTS", ROOT / "runs" / "app_exports"))
WEB_DIST = ROOT / "web" / "dist"


@dataclass
class DocumentJob:
    id: str
    name: str
    data: bytes
    status: str = "queued"  # queued, running, done, failed
    error: str | None = None
    result: ReviewResult | None = None
    seconds: float | None = None
    scanned: bool = False


@dataclass
class Pack:
    id: str
    created: float
    documents: list[DocumentJob] = field(default_factory=list)

    @property
    def status(self) -> str:
        states = {d.status for d in self.documents}
        if states <= {"done", "failed"}:
            return "done"
        return "running" if states & {"running", "done", "failed"} else "queued"


class Reviewer:
    """Holds the packs and one worker thread, so model jobs never share the GPU."""

    def __init__(self, config: dict):
        self.config = config
        self.rules = load_playbook(ROOT / config["playbook"])
        self.packs: dict[str, Pack] = {}
        self.jobs: queue.Queue = queue.Queue()
        self._method = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def method(self):
        # I load the model on first use, so the server starts fast and tests stay light.
        with self._lock:
            if self._method is None:
                self._method = build_method(self.config["method"], self.config.get("params"))
            return self._method

    def start(self) -> None:
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()

    def _work(self) -> None:
        while True:
            job: DocumentJob = self.jobs.get()
            job.status = "running"
            t0 = time.perf_counter()
            try:
                doc = load_document(job.data, job.name)
                job.scanned = doc.looks_scanned
                job.result = review_document(doc, self.method, self.config["threshold"],
                                             self.rules)
                job.status = "done"
            except Exception as e:  # one bad file shouldn't stop the rest of the pack
                job.status, job.error = "failed", f"{type(e).__name__}: {e}"
            finally:
                job.data = b""
                job.seconds = time.perf_counter() - t0
                self.jobs.task_done()

    def submit(self, files: list[tuple[str, bytes]]) -> Pack:
        pack = Pack(uuid.uuid4().hex[:12], time.time())
        for name, data in files:
            job = DocumentJob(uuid.uuid4().hex[:12], name, data)
            pack.documents.append(job)
            self.jobs.put(job)
        self.packs[pack.id] = pack
        return pack


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.reviewer = Reviewer(load_config())
    app.state.reviewer.start()
    yield


app = FastAPI(title="ClauseScout", lifespan=lifespan)
# The Vite dev server runs on another port; in production the API serves the built frontend.
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def _reviewer() -> Reviewer:
    return app.state.reviewer


def _pack(pack_id: str) -> Pack:
    pack = _reviewer().packs.get(pack_id)
    if pack is None:
        raise HTTPException(404, "No such pack")
    return pack


def _doc_summary(d: DocumentJob) -> dict:
    out = {"id": d.id, "name": d.name, "status": d.status, "error": d.error,
           "seconds": d.seconds, "scanned": d.scanned}
    if d.result:
        r = d.result.review
        sev = [fl.rule.severity for fl in r.flags]
        found = {f.category for f in r.findings}
        out.update(n_findings=len(r.findings),
                   flag_counts={s: sev.count(s) for s in ("high", "medium", "low")},
                   high_stakes_found=[c for c in HIGH_STAKES if c in found])
    return out


@app.get("/api/health")
def health():
    cfg = _reviewer().config
    return {"status": "ok", "method": cfg["method"], "threshold": cfg["threshold"],
            "disclaimer": DISCLAIMER}


@app.get("/api/meta")
def meta():
    rules = [{"id": r.id, "severity": r.severity, "title": r.title, "explanation": r.explanation,
              "measurable": r.measurable} for r in _reviewer().rules]
    return {"categories": CATEGORIES, "high_stakes": HIGH_STAKES, "rules": rules,
            "supported": list(SUPPORTED), "disclaimer": DISCLAIMER}


@app.post("/api/packs")
async def create_pack(files: Annotated[list[UploadFile], File()]):
    cfg = _reviewer().config
    if len(files) > cfg["max_files"]:
        raise HTTPException(413, f"At most {cfg['max_files']} files per pack")
    loaded = []
    for f in files:
        name = Path(f.filename or "contract").name
        if Path(name).suffix.lower() not in SUPPORTED:
            raise HTTPException(415, f"{name}: use one of {', '.join(SUPPORTED)}")
        data = await f.read(cfg["max_file_mb"] * 2**20 + 1)
        if len(data) > cfg["max_file_mb"] * 2**20:
            raise HTTPException(413, f"{name} is over {cfg['max_file_mb']} MB")
        loaded.append((name, data))
    pack = _reviewer().submit(loaded)
    return {"id": pack.id, "documents": [_doc_summary(d) for d in pack.documents]}


@app.get("/api/packs/{pack_id}")
def get_pack(pack_id: str):
    pack = _pack(pack_id)
    return {"id": pack.id, "status": pack.status,
            "documents": [_doc_summary(d) for d in pack.documents]}


@app.get("/api/packs/{pack_id}/documents/{doc_id}")
def get_document(pack_id: str, doc_id: str):
    doc = next((d for d in _pack(pack_id).documents if d.id == doc_id), None)
    if doc is None:
        raise HTTPException(404, "No such document")
    if doc.result is None:
        return _doc_summary(doc)
    r = doc.result.review
    findings = [{"category": f.category, "text": f.text, "start": f.start, "end": f.end,
                 "score": f.score, "location": r.location(f),
                 "high_stakes": f.category in HIGH_STAKES} for f in r.findings]
    flags = [{"id": fl.rule.id, "severity": fl.rule.severity, "title": fl.rule.title,
              "explanation": fl.rule.explanation, "measurable": fl.rule.measurable,
              "evidence": [{"category": e.category, "start": e.start, "end": e.end,
                            "location": r.location(e)} for e in fl.evidence]}
             for fl in r.flags]
    return {**_doc_summary(doc), "text": doc.result.text, "findings": findings, "flags": flags,
            "missing": r.missing(),
            "segments": [{"kind": s.kind, "number": s.number, "start": s.start, "end": s.end}
                         for s in r.segments]}


def _done_reviews(pack: Pack):
    reviews = [d.result.review for d in pack.documents if d.result]
    if not reviews:
        raise HTTPException(409, "No finished documents in this pack yet")
    return reviews


@app.get("/api/packs/{pack_id}/report.xlsx")
def report_xlsx(pack_id: str):
    path = write_excel(_done_reviews(_pack(pack_id)), EXPORT_DIR / f"{pack_id}.xlsx")
    return FileResponse(path, filename=f"clausescout-{pack_id}.xlsx")


@app.get("/api/packs/{pack_id}/report.html", response_class=HTMLResponse)
def report_html(pack_id: str):
    return HTMLResponse(render_html(_done_reviews(_pack(pack_id))))


# The built React app, if there is one, is served from the same origin.
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
