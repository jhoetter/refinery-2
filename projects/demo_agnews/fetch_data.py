"""Fetch classic AG News subset from HuggingFace into the demo project.

Tries the HF datasets-server JSON API (stdlib only, no `datasets` package).
Falls back to an expanded synthetic sample when HF is unreachable, so the
demo always boots.
"""
from __future__ import annotations

import itertools
import json
import sys
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
DATA = PROJECT / "data" / "records.jsonl"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400

API = "https://datasets-server.huggingface.co/rows"


def fetch_hf(n: int) -> list[dict]:
    # AG News train is class-sorted (30k blocks); spread offsets for balance
    per = max(1, n // 4)
    offsets = [0, 30000, 60000, 90000]
    rows: list[dict] = []
    for block, base in enumerate(offsets):
        want = per if block < 3 else n - len(rows)
        step = 100
        for offset in range(base, base + want, step):
            length = min(step, base + want - offset)
            url = (
                f"{API}?dataset=fancyzhx%2Fag_news&config=default"
                f"&split=train&offset={offset}&length={length}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "refinery-2"})
            with urllib.request.urlopen(req, timeout=20) as r:
                payload = json.load(r)
            for i, row in enumerate(payload.get("rows", [])):
                rdata = row.get("row", {})
                rows.append(
                    {
                        "id": f"ag-{offset + i}",
                        "text": f"{rdata.get('title', '')} {rdata.get('text', '')}".strip(),
                        "meta": {"hf_label": rdata.get("label")},
                    }
                )
    return rows


TEMPLATES = {
    "Sports": [
        "The {team} win the {game} as coach praises {player} after a strong {season} match",
        "{player} scores late as {team} takes the {league} {game} in front of home fans",
    ],
    "Business": [
        "Stocks rally as {firm} profit rises with bank {shares} gaining on strong {sales}",
        "{firm} CEO warns on {market} prices as {economy} fears hit {shares}",
    ],
    "Sci/Tech": [
        "{firm} announces new AI {software} as NASA plans a {space} data mission",
        "New {computer} {chip} speeds up {internet} {software} for data centers",
    ],
    "World": [
        "{leader} meets ministers in {city} to discuss {election} and government plans",
        "{war} fears grow as the {country} conflict dominates UN debate in {year}",
    ],
}
SLOTS = {
    "team": ["Lakers", "Yankees", "FIFA XI", "Olympic squad"],
    "game": ["game", "match", "final", "derby"],
    "player": ["star player", "captain", "rookie striker", "veteran goalie"],
    "season": ["season", "league campaign", "playoff run"],
    "league": ["league", "cup", "championship"],
    "firm": ["Google", "Microsoft", "Apple", "IBM"],
    "shares": ["shares", "stock", "equity"],
    "sales": ["sales", "revenue", "orders"],
    "market": ["market", "oil", "chip"],
    "economy": ["economy", "inflation", "trade"],
    "software": ["software", "platform", "cloud suite"],
    "space": ["space", "lunar", "satellite"],
    "computer": ["computer", "server", "laptop"],
    "chip": ["chip", "processor", "GPU"],
    "internet": ["internet", "network", "broadband"],
    "leader": ["President", "Prime minister", "Chancellor"],
    "city": ["Berlin", "London", "Paris", "Tokyo"],
    "election": ["election", "referendum", "coalition talks"],
    "war": ["War", "Conflict", "Border clash"],
    "country": ["Iraq", "China", "European"],
    "year": ["2004", "2005", "2003"],
}


def fallback(n: int) -> list[dict]:
    rows: list[dict] = []
    i = 0
    for topic, tmpls in TEMPLATES.items():
        for tmpl in tmpls:
            keys = sorted({k for k in SLOTS if "{" + k + "}" in tmpl})
            for combo in itertools.product(*[SLOTS[k] for k in keys]):
                if len(rows) >= n:
                    return rows
                text = tmpl.format(**dict(zip(keys, combo)))
                rows.append({"id": f"fb-{i}", "text": text + ".", "meta": {"fallback_topic": topic}})
                i += 1
    return rows[:n]


def main() -> None:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    try:
        rows = fetch_hf(N)
        print(f"loaded {len(rows)} rows from HF fancyzhx/ag_news")
    except Exception as e:
        print(f"HF fetch failed ({e}); using synthetic fallback sample")
        rows = fallback(N)
    with DATA.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} rows to {DATA}")


if __name__ == "__main__":
    main()
