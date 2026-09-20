"""Live Jev teacher (TypeSafe System One) via POST /v1/systemone.

Key from JEV_API_KEY env (see .env, never committed). Task mapping:
classification -> single `choice` question with per-label criteria.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"


def jev_choice(
    state: str,
    instructions: str,
    options: dict[str, str],
    model: str = MODEL,
    timeout: int = 30,
) -> tuple[str, float, dict[str, float], float]:
    """Returns (label, confidence, probs, latency_ms). Raises RuntimeError."""
    key = os.environ.get("JEV_API_KEY", "")
    if not key:
        raise RuntimeError("JEV_API_KEY not set")
    body = {
        "state": state,
        "model": model,
        "questions": {"q": {"type": "choice", "instructions": instructions, "criteria": options}},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.load(r)
    except Exception as e:
        raise RuntimeError(f"jev request failed: {e}")
    latency = (time.time() - t0) * 1000
    return parse_choice(payload, latency)


def parse_choice(payload: dict, latency: float) -> tuple[str, float, dict[str, float], float]:
    """Defensive parser for Jev choice answers (shape verified by live probe)."""
    # candidate shapes: {answers:{q:{...}}} | {results:{q:{...}}} | {q:{...}}
    node = payload
    for key in ("answers", "results", "decisions"):
        if isinstance(node, dict) and key in node and isinstance(node[key], dict):
            node = node[key]
            break
    ans = node.get("q", node) if isinstance(node, dict) else {}
    if not isinstance(ans, dict):
        raise RuntimeError(f"unexpected jev shape: {str(payload)[:300]}")
    label = ans.get("choice") or ans.get("label") or ans.get("value") or ans.get("answer")
    probs = ans.get("probabilities") or ans.get("probs") or ans.get("distribution") or {}
    if label is None and probs:
        label = max(probs, key=lambda k: probs[k])
    if label is None:
        raise RuntimeError(f"unexpected jev answer shape: {str(payload)[:300]}")
    conf = float(probs.get(label, ans.get("confidence", 0.8))) if isinstance(probs, dict) else 0.8
    return str(label), round(conf, 3), {str(k): float(v) for k, v in (probs or {}).items()}, round(latency, 1)


TOPIC_OPTIONS = {
    "World": "international politics, war, elections, governments, diplomacy",
    "Sports": "games, teams, players, scores, leagues, tournaments",
    "Business": "stocks, markets, companies, profit, economy, finance",
    "Sci/Tech": "software, computers, internet, space, AI, gadgets",
}


def jev_topic(text: str, timeout: int = 30) -> tuple[str, float, dict[str, float], float]:
    return jev_choice(
        text,
        "Classify this news article into exactly one topic.",
        TOPIC_OPTIONS,
        timeout=timeout,
    )
