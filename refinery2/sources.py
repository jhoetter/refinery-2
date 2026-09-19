"""Label sources: heuristic, mock-llm (expensive), jev-fast (cheap typed).

Real deployments swap MockLLM for an OpenAI-compatible endpoint via
LLM_BASE_URL / LLM_API_KEY / LLM_MODEL env vars. The mock is deterministic
so the demo + tests run offline.
"""
from __future__ import annotations

import os
import re

TOPIC_KEYWORDS = {
    "Sports": ["game", "team", "win", "player", "coach", "season", "match", "league", "score", "olympic",
               "goal", "cup", "tournament", "athlete", "championship", " yankees", "lakers", "fifa", "nba"],
    "Business": ["stock", "market", "profit", "company", "bank", "sales", "economy", "price", "shares", "ceo",
                 "dollar", "trade", "deficit", "oil", "wall street", "earnings", "revenue", "investor",
                 "financial", "funds", "retail", "deficit", "imports", "exports", "forbes", "money"],
    "Sci/Tech": ["software", "computer", "internet", "tech", "space", "nasa", "chip", "data", "google", "microsoft",
                 "apple", "ibm", "tech", "digital", "broadband", "satellite", "robot", "cyber"],
    "World": ["minister", "president", "government", "war", "election", "iraq", "china", "europe",
              "military", "troops", "palestinian", "israel", "kerry", "bush", "senate", "nuclear", "refugee"],
}

_WORD_RES = {k: [re.compile(r"\b" + re.escape(w.strip()) + r"\b") for w in words] for k, words in TOPIC_KEYWORDS.items()}


def _keyword_scores(text: str, title_boost: float = 2.0) -> dict[str, float]:
    title = " ".join(text.split()[:15]).lower()
    body = text.lower()
    scores: dict[str, float] = {}
    for label, patterns in _WORD_RES.items():
        s = sum(len(p.findall(body)) for p in patterns)
        s += title_boost * sum(len(p.findall(title)) for p in patterns)
        scores[label] = s
    return scores

ENTITY_PATTERNS = [
    ("ORG", re.compile(r"\b(NASA|Google|Microsoft|Apple|IBM|United Nations|EU|FBI|NBA|FIFA)\b")),
    ("MONEY", re.compile(r"\$\s?\d[\d,\.]*\s?(million|billion)?", re.I)),
    ("DATE", re.compile(r"\b(19|20)\d{2}\b")),
    ("LOC", re.compile(r"\b(Iraq|China|Europe|USA|U\.S\.|Berlin|London|Paris|Tokyo)\b")),
]


def heuristic_topic(text: str) -> tuple[str, float]:
    scores = _keyword_scores(text)
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "World", 0.34
    total = sum(scores.values())
    return best, round(0.5 + 0.5 * scores[best] / max(total, 1), 3)


def heuristic_spans(text: str) -> tuple[list[dict], float]:
    spans = []
    for entity, pat in ENTITY_PATTERNS:
        for m in pat.finditer(text):
            spans.append({"start": m.start(), "end": m.end(), "entity": entity})
    spans.sort(key=lambda s: s["start"])
    conf = 0.9 if spans else 0.5
    return spans, conf


def heuristic_extraction(text: str) -> tuple[dict, float]:
    """Naive extraction: headline-ish first sentence + org/date mentions."""
    first = text.split(".")[0][:160].strip()
    orgs = sorted({m.group(0) for _, pat in ENTITY_PATTERNS[:1] for m in pat.finditer(text)})
    return {"summary": first, "orgs": ", ".join(orgs)}, 0.6


def mock_llm_topic(text: str) -> tuple[str, float]:
    """Simulates the expensive frontier model: stronger title prior + outlet cues."""
    scores = _keyword_scores(text, title_boost=3.0)
    t = text.lower()
    if "forbes" in t:
        scores["Business"] += 4
    if "olympic" in t or "fifa" in t:
        scores["Sports"] += 4
    if "nasa" in t or "satellite" in t:
        scores["Sci/Tech"] += 3
    if "iraq" in t or "troops" in t or "palestinian" in t:
        scores["World"] += 3
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "World", 0.4
    total = sum(scores.values())
    return best, round(min(0.95, 0.55 + 0.45 * scores[best] / max(total, 1)), 3)


def jev_fast_topic(text: str) -> tuple[str, dict[str, float], float]:
    """Simulates a Jev-style typed decision: parallel probs over labels, calibrated.

    Returns (top_label, probs, confidence=top prob). Fast/cheap by design,
    slightly less accurate than mock-llm on ambiguous texts.
    """
    raw = _keyword_scores(text, title_boost=1.0)
    # flatten: Jev is calibrated, rarely overconfident without evidence
    total = sum(raw.values())
    if total == 0:
        probs = {k: 0.25 for k in TOPIC_KEYWORDS}
    else:
        probs = {k: round((v + 0.5) / (total + 2.0), 3) for k, v in raw.items()}
    top = max(probs, key=lambda k: probs[k])
    return top, probs, probs[top]


def run_sources_for_record(text: str) -> dict[str, dict]:
    """Run all built-in sources for all demo tasks. Returns {task: {source: ...}}."""
    topic_h, conf_h = heuristic_topic(text)
    topic_m, conf_m = mock_llm_topic(text)
    topic_j, probs_j, conf_j = jev_fast_topic(text)
    spans_h, sconf_h = heuristic_spans(text)
    spans_m = spans_h  # mock-llm agrees with spans but more confident
    extr_h, econf_h = heuristic_extraction(text)
    return {
        "topic": {
            "heuristic": {"label": topic_h, "confidence": conf_h},
            "mock-llm": {"label": topic_m, "confidence": conf_m},
            "jev-fast": {"label": topic_j, "confidence": conf_j, "probs": probs_j},
        },
        "entities": {
            "heuristic": {"label": spans_h, "confidence": sconf_h},
            "mock-llm": {"label": spans_m, "confidence": min(0.95, sconf_h + 0.05)},
        },
        "brief": {
            "heuristic": {"label": extr_h, "confidence": econf_h},
            "mock-llm": {"label": extr_h, "confidence": 0.8},
        },
    }


def llm_env_configured() -> dict | None:
    base = os.environ.get("LLM_BASE_URL")
    key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")
    if base and model:
        return {"base_url": base, "api_key": key, "model": model}
    return None
