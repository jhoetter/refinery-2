from refinery2.aggregate import aggregate_classification, source_quality


def test_weighted_vote():
    label, conf = aggregate_classification(
        [
            {"label": "Sports", "confidence": 0.9},
            {"label": "Sports", "confidence": 0.6},
            {"label": "World", "confidence": 0.8},
        ]
    )
    assert label == "Sports"
    assert 0.5 < conf <= 1.0


def test_empty():
    assert aggregate_classification([]) == (None, 0.0)


def test_aggregate_any_spans_picks_best_confidence():
    from refinery2.aggregate import aggregate_any

    label, conf = aggregate_any(
        [
            {"label": [{"start": 0, "end": 3, "entity": "ORG"}], "confidence": 0.5},
            {"label": [], "confidence": 0.9},
        ]
    )
    assert label == [] and conf == 0.9


def test_aggregate_any_empty():
    from refinery2.aggregate import aggregate_any

    assert aggregate_any([]) == (None, 0.0)


def test_source_quality():
    labels = [
        {"record_id": "a", "source": "hev", "label": "Sports", "confidence": 1},
        {"record_id": "b", "source": "hev", "label": "World", "confidence": 1},
        {"record_id": "a", "source": "llm", "label": "Sports", "confidence": 1},
        {"record_id": "b", "source": "llm", "label": "Sports", "confidence": 1},
    ]
    q = source_quality(labels, {"a": "Sports", "b": "World"})
    assert q["hev"]["accuracy"] == 1.0
    assert q["llm"]["accuracy"] == 0.5
