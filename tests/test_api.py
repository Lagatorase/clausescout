"""The API end to end with the keyword method, which needs no model or GPU."""

import time

import pytest
from fastapi.testclient import TestClient

from api.main import app

CONTRACT = (
    "DISTRIBUTION AGREEMENT\n\n"
    "This Agreement is governed by the laws of the State of New York.\n\n"
    "Neither party may assign this Agreement without the prior written consent of the other "
    "party.\n\n"
    "Distributor shall be the exclusive distributor of the Products in the Territory.\n"
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _wait(client, pack_id):
    for _ in range(100):
        pack = client.get(f"/api/packs/{pack_id}").json()
        if pack["status"] == "done":
            return pack
        time.sleep(0.05)
    raise AssertionError("pack did not finish")


def test_health_and_meta(client):
    assert client.get("/api/health").json()["method"] == "keywords"
    meta = client.get("/api/meta").json()
    assert len(meta["categories"]) == 41 and "not legal advice" in meta["disclaimer"]


def test_pack_round_trip(client):
    files = [("files", ("dist.txt", CONTRACT.encode(), "text/plain")),
             ("files", ("broken.pdf", b"not a pdf", "application/pdf"))]
    pack = _wait(client, client.post("/api/packs", files=files).json()["id"])
    ok, bad = pack["documents"]
    assert ok["status"] == "done" and bad["status"] == "failed"

    doc = client.get(f"/api/packs/{pack['id']}/documents/{ok['id']}").json()
    cats = {f["category"] for f in doc["findings"]}
    assert {"Governing Law", "Anti-Assignment"} <= cats
    # Every quote is really in the text at the offsets given.
    for f in doc["findings"]:
        assert doc["text"][f["start"]:f["end"]] == f["text"]
    assert any(fl["id"] == "governing-law-not-singapore" for fl in doc["flags"])

    xlsx = client.get(f"/api/packs/{pack['id']}/report.xlsx")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    assert "not legal advice" in client.get(f"/api/packs/{pack['id']}/report.html").text


def test_rejects_unsupported_files(client):
    r = client.post("/api/packs", files=[("files", ("x.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 415
    assert client.get("/api/packs/nope").status_code == 404
