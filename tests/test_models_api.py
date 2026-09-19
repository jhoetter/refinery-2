"""Registry/train/benchmark/predict flow on an isolated project."""
import importlib

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
    for i in range(30):
        lab = "A" if i % 2 == 0 else "B"
        store.upsert_records([{"id": f"r{i}", "text": f"sample text number {i} about {lab}", "meta": {}}])
        store.add_source_label(f"r{i}", "topic", "heuristic", lab, 0.9)
        store.set_agg(f"r{i}", "topic", lab, 0.9)
        if i < 8:
            store.set_golden(f"r{i}", "topic", lab)
    store.commit()
    return TestClient(srv.app), proj


def test_templates_and_task_creation(client):
    api, proj = client
    names = [t["template"] for t in api.get("/api/templates").json()["templates"]]
    assert "text-classification" in names
    assert "support-ticket-bundle" in names
    r = api.post("/api/tasks/from-template", json={"template": "ner-spans"})
    assert r.status_code == 200, r.text
    assert (proj / "tasks" / "entities.yaml").exists()
    r = api.post("/api/tasks", json={"name": "vibe", "type": "classification", "labels": ["X", "Y"]})
    assert r.status_code == 200, r.text
    assert (proj / "tasks" / "vibe.yaml").exists()
    r = api.post("/api/tasks", json={"name": "bad", "type": "nope", "labels": []})
    assert r.status_code == 400


def test_train_benchmark_predict(client):
    api, proj = client
    r = api.post("/api/models/train", json={"task": "topic", "name": "s1", "min_conf": 0.5})
    assert r.status_code == 200, r.text
    assert (proj / "models" / "s1.pkl").exists()
    assert (proj / "models" / "models.yaml").exists()
    models = [m["name"] for m in api.get("/api/models").json()["models"]]
    assert "s1" in models
    r = api.post("/api/models/benchmark", json={"task": "topic"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "s1" in body["models"]
    assert body["models"]["s1"]["accuracy"] is not None
    r = api.post("/api/predict", json={"model": "s1", "task": "topic", "text": "sample text about A"})
    assert r.status_code == 200, r.text
    assert r.json()["label"] in ("A", "B")
    r = api.post("/api/predict", json={"model": "ghost", "task": "topic", "text": "x"})
    assert r.status_code == 404
