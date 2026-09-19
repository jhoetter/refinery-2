"""Distillation: train a small cheap student on aggregated teacher labels.

MVP uses a pure-stdlib multinomial Naive Bayes (word unigrams + bigrams)
so the project runs without scipy/sklearn. The point is the loop
(expensive labels -> small model -> slice eval), not SOTA.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

TOKEN = re.compile(r"[a-z0-9]+")


def featurize(text: str) -> Counter:
    toks = TOKEN.findall(text.lower())
    feats: Counter = Counter(toks)
    feats.update(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    return feats


class NBStudent:
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.classes: list[str] = []
        self.log_prior: dict[str, float] = {}
        self.log_prob: dict[str, dict[str, float]] = {}
        self.vocab: set[str] = set()

    def fit(self, texts: list[str], labels: list[str]) -> "NBStudent":
        counts: dict[str, Counter] = defaultdict(Counter)
        docs: Counter = Counter(labels)
        for t, lab in zip(texts, labels):
            counts[lab].update(featurize(t))
        self.classes = sorted(docs)
        n_docs = len(labels)
        self.vocab = set()
        for c in self.classes:
            self.vocab.update(counts[c])
        V = len(self.vocab)
        for c in self.classes:
            self.log_prior[c] = math.log(docs[c] / n_docs)
            total = sum(counts[c].values()) + self.alpha * V
            self.log_prob[c] = {
                w: math.log((counts[c][w] + self.alpha) / total) for w in self.vocab
            }
        return self

    def predict_one(self, text: str) -> str:
        feats = featurize(text)
        best, best_score = None, float("-inf")
        for c in self.classes:
            lp = self.log_prior[c]
            probs = self.log_prob[c]
            for w, n in feats.items():
                if w in probs:
                    lp += n * probs[w]
            if lp > best_score:
                best, best_score = c, lp
        return best  # type: ignore[return-value]

    def predict(self, texts: list[str]) -> list[str]:
        return [self.predict_one(t) for t in texts]


def train_classifier(texts: list[str], labels: list[str]) -> NBStudent:
    return NBStudent().fit(texts, labels)


def evaluate(clf: NBStudent, texts: list[str], labels: list[str]) -> dict:
    if not texts:
        return {"n": 0, "accuracy": None, "f1_macro": None}
    pred = clf.predict(texts)
    acc = sum(p == g for p, g in zip(pred, labels)) / len(labels)
    classes = sorted(set(labels) | set(pred))
    f1s = []
    for c in classes:
        tp = sum(1 for p, g in zip(pred, labels) if p == c and g == c)
        fp = sum(1 for p, g in zip(pred, labels) if p == c and g != c)
        fn = sum(1 for p, g in zip(pred, labels) if p != c and g == c)
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    return {
        "n": len(texts),
        "accuracy": round(acc, 3),
        "f1_macro": round(sum(f1s) / len(f1s), 3) if f1s else None,
    }


def evaluate_slices(
    clf: NBStudent,
    records: list[dict],
    golden: dict[str, str],
    slice_of,
) -> dict[str, dict]:
    buckets: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    for r in records:
        rid = r["id"]
        if rid not in golden:
            continue
        for s in slice_of(rid):
            buckets[s][0].append(r["text"])
            buckets[s][1].append(golden[rid])
    return {s: {**evaluate(clf, t, lab), "slice": s} for s, (t, lab) in buckets.items()}
