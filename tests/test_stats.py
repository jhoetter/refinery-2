"""Stats endpoint: distributions for dashboard + data browser."""
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
    (proj / "slices.yaml").write_text("- {name: has_a, match: {text_contains: 'a'}}\n")
    monkeypatch.setenv("REFINERY_PROJECT", str(proj))
    import refinery2.server as srv

    importlib.reload(srv)
    from refinery2.store import Store

    store = Store(proj / "data" / "store.db")
    for i in range(10):
        lab = "A" if i % 2 == 0 else "B"
        store.upsert_records([{"id": f"r{i}", "text": f"sample {i} a", "meta": {}}])
        store.add_source_label(f"r{i}", "topic", "heuristic", lab, 0.9)
        store.set_agg(f"r{i}", "topic", lab, 0.9)
        if i < 4:
            store.set_golden(f"r{i}", "topic", lab)
    store.commit()
    return TestClient(srv.app)


def test_stats_distributions(client):
    s = client.get("/api/stats?task=topic").json()
    assert s["n_records"] == 10
    assert s["n_golden"] == 4
    assert s["dist_agg"] == {"A": 5, "B": 5}
    assert sum(s["dist_golden"].values()) == 4
    assert sum(s["conf_hist"]) == 10
    assert s["slices"]["has_a"] == 10
    assert s["sources"]["heuristic"]["accuracy"] == 1.0


def test_stats_rejects_unknown_task(client):
    assert client.get("/api/stats?task=nope").status_code == 400
