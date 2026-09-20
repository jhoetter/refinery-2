"""Jev response parser tests (canned payloads, no network)."""
from refinery2.jev import parse_choice


def test_answers_shape():
    payload = {"answers": {"q": {"choice": "Sports", "probabilities": {"Sports": 0.9, "World": 0.1}}}}
    assert parse_choice(payload, 100.0) == ("Sports", 0.9, {"Sports": 0.9, "World": 0.1}, 100.0)


def test_results_shape_with_proba_fallback():
    payload = {"results": {"q": {"probabilities": {"A": 0.2, "B": 0.8}}}}
    label, conf, probs, _ = parse_choice(payload, 50.0)
    assert label == "B" and conf == 0.8


def test_bare_shape_with_confidence():
    payload = {"choice": "X", "confidence": 0.7}
    assert parse_choice(payload, 10.0) == ("X", 0.7, {}, 10.0)


def test_garbage_raises():
    import pytest

    with pytest.raises(RuntimeError):
        parse_choice({"nonsense": True}, 1.0)
