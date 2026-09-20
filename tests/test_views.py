"""Views: complex saved filters (nested groups, negate, cross-task conditions)."""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def setup(tmp_path, monkeypatch):
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
    texts = ["alpha foo", "beta bar", "alpha beta", "nothing here"]
    for i, t in enumerate(texts):
        lab = "A" if i % 2 == 0 else "B"
        store.upsert_records([{"id": f"r{i}", "text": t, "meta": {}}])
        store.add_source_label(f"r{i}", "topic", "s1", lab, 0.9 if i < 2 else 0.4)
        store.add_source_label(f"r{i}", "topic", "s2", lab if i != 1 else "A", 0.8)
        store.set_agg(f"r{i}", "topic", lab, 0.9 if i < 2 else 0.4)
        if i == 0:
            store.set_golden(f"r{i}", "topic", lab)
    store.commit()
    return TestClient(srv.app), store


def test_nested_groups_and_negate(setup):
    api, store = setup
    from refinery2.views import eval_view

    view = {
        "logic": "and",
        "groups": [
            {"logic": "or", "conditions": [
                {"field": "text_contains", "value": "alpha"},
                {"field": "text_contains", "value": "beta"},
            ]},
            {"logic": "and", "negate": True, "conditions": [
                {"field": "golden", "task": "topic", "op": "present"},
            ]},
        ],
    }
    assert eval_view(store, [], view) == ["r1", "r2"]


def test_disagreement_and_confidence(setup):
    api, store = setup
    from refinery2.views import eval_view

    view = {"logic": "and", "groups": [
        {"conditions": [{"field": "disagreement", "task": "topic", "op": "true"}]},
    ]}
    assert eval_view(store, [], view) == ["r1"]
    view2 = {"logic": "and", "groups": [
        {"conditions": [{"field": "confidence", "task": "topic", "op": "lt", "value": 0.5}]},
    ]}
    assert eval_view(store, [], view2) == ["r2", "r3"]


def test_view_crud_and_run(setup):
    api, store = setup
    body = {"name": "my-view", "logic": "and", "groups": [
        {"conditions": [{"field": "agg_label", "task": "topic", "op": "eq", "value": "A"}]}
    ]}
    r = api.post("/api/views", json=body)
    assert r.status_code == 200, r.text
    names = [v["name"] for v in api.get("/api/views").json()["views"]]
    assert "my-view" in names
    r = api.post("/api/views/run", json={"view": "my-view", "task": "topic"})
    assert r.status_code == 200, r.text
    assert r.json()["n"] == 2
    # inline preview without saving
    r = api.post("/api/views/run", json={"definition": body, "task": "topic"})
    assert r.json()["n"] == 2
    assert api.delete("/api/views/my-view").status_code == 200
    assert "my-view" not in [v["name"] for v in api.get("/api/views").json()["views"]]
    assert api.post("/api/views/run", json={"view": "my-view"}).status_code == 404
