from refinery2.distill import evaluate, train_classifier


def test_train_eval():
    texts = [
        "lakers win the game season match",
        "team coach players score league",
        "stocks market profit bank shares",
        "company sales price economy ceo",
    ] * 6
    labels = ["Sports", "Sports", "Business", "Business"] * 6
    clf = train_classifier(texts, labels)
    m = evaluate(clf, texts[:4], labels[:4])
    assert m["accuracy"] == 1.0
    assert m["n"] == 4
