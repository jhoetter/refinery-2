"""API regression tests for the labeling flow (user reported: cannot label).

Uses an isolated project via REFINERY_PROJECT so the demo store is untouched.
"""
import importlib
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / "tasks").mkdir(parents=True)
    (proj / "data").mkdir()
    (proj / "golden").mkdir()
    (proj / "refinery.yaml").write_text("name: test\n")
    (proj / "tasks" / "topic.yaml").write_text(
        "name: topic\ntype: classification\nlabels: [A, B]\n"
    )
    (proj / "slices.yaml").write_text("[]\n")
    monkeypatch.setenv("REFINERY_PROJECT", str(proj))
    import refinery2.server as srv

    importlib.reload(srv)
    from refinery2.store import Store

    store = Store(proj / "data" / "store.db")
    store.upsert_records([{"id": "r1", "text": "some text here", "meta": {}}])
    return TestClient(srv.app)


def test_label_roundtrip(client):
    r = client.post("/api/labels", json={"record_id": "r1", "task": "topic", "label": "A"})
    assert r.status_code == 200, r.text
    rec = client.get("/api/record/r1?task=topic").json()
    assert rec["golden"] == "A"


def test_label_rejects_unknown_label(client):
    r = client.post("/api/labels", json={"record_id": "r1", "task": "topic", "label": "ZZZ"})
    assert r.status_code == 400


def test_label_rejects_unknown_task(client):
    r = client.post("/api/labels", json={"record_id": "r1", "task": "nope", "label": "A"})
    assert r.status_code == 400


def test_project_lists_tasks(client):
    p = client.get("/api/project").json()
    assert "topic" in p["tasks"]
    assert p["n_records"] == 1
