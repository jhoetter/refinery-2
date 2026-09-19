import pytest

from refinery2.tasks import TaskDef, validate_label


def test_classification_ok():
    t = TaskDef(name="topic", type="classification", labels=["A", "B"])
    assert validate_label(t, "A") == "A"
    with pytest.raises(ValueError):
        validate_label(t, "C")


def test_spans_ok():
    t = TaskDef(name="ent", type="spans", entities=["ORG"])
    out = validate_label(t, [{"start": 0, "end": 3, "entity": "ORG"}])
    assert out[0]["entity"] == "ORG"
    with pytest.raises(ValueError):
        validate_label(t, [{"start": 0, "end": 3, "entity": "NOPE"}])
