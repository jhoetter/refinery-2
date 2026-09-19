"""MCP dispatch tests on an isolated project (no stdio needed)."""
import importlib

import pytest


@pytest.fixture()
def mcp(tmp_path, monkeypatch):
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
    import refinery2.mcp_server as m

    importlib.reload(m)
    from refinery2.store import Store

    store = Store(proj / "data" / "store.db")
    for i in range(20):
        lab = "A" if i % 2 == 0 else "B"
        store.upsert_records([{"id": f"r{i}", "text": f"text {i} about {lab}", "meta": {}}])
        store.add_source_label(f"r{i}", "topic", "heuristic", lab, 0.9)
        store.set_agg(f"r{i}", "topic", lab, 0.9)
        if i < 6:
            store.set_golden(f"r{i}", "topic", lab)
    store.commit()
    return m


def test_mcp_templates_and_status(mcp):
    tpl = mcp.dispatch("list_templates", {})
    assert any(t["template"] == "text-classification" for t in tpl["templates"])
    st = mcp.dispatch("project_status", {})
    assert st["records"] == 20
    assert "topic" in st["tasks"]


def test_mcp_create_train_benchmark_predict(mcp):
    out = mcp.dispatch("create_task", {"template": "extraction"})
    assert out["tasks"] == ["brief"]
    out = mcp.dispatch("create_task", {"task_def": {"name": "vibe", "type": "classification", "labels": ["X", "Y"]}})
    assert out["tasks"] == ["vibe"]
    entry = mcp.dispatch("train_student", {"task": "topic", "name": "m1", "min_conf": 0.5})
    assert entry["name"] == "m1"
    bench = mcp.dispatch("benchmark", {"task": "topic"})
    assert bench["models"]["m1"]["accuracy"] is not None
    pred = mcp.dispatch("predict", {"model": "m1", "task": "topic", "text": "text about A"})
    assert pred["label"] in ("A", "B")
    with pytest.raises(ValueError):
        mcp.dispatch("nope", {})
