"""SQLite store: records, source labels, golden labels, aggregated labels."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  meta TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS source_labels (
  record_id TEXT, task TEXT, source TEXT, label TEXT, confidence REAL DEFAULT 1.0,
  PRIMARY KEY (record_id, task, source)
);
CREATE TABLE IF NOT EXISTS golden_labels (
  record_id TEXT, task TEXT, label TEXT,
  PRIMARY KEY (record_id, task)
);
CREATE TABLE IF NOT EXISTS agg_labels (
  record_id TEXT, task TEXT, label TEXT, confidence REAL DEFAULT 1.0,
  PRIMARY KEY (record_id, task)
);
"""


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(path), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    def upsert_records(self, records: list[dict]) -> int:
        n = 0
        for r in records:
            self.con.execute(
                "INSERT OR REPLACE INTO records (id, text, meta) VALUES (?,?,?)",
                (r["id"], r["text"], json.dumps(r.get("meta", {}))),
            )
            n += 1
        self.con.commit()
        return n

    def count_records(self) -> int:
        return self.con.execute("SELECT COUNT(*) c FROM records").fetchone()["c"]

    def get_record(self, rid: str) -> dict | None:
        row = self.con.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        if not row:
            return None
        return {"id": row["id"], "text": row["text"], "meta": json.loads(row["meta"])}

    def list_records(self, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = self.con.execute(
            "SELECT * FROM records ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [
            {"id": r["id"], "text": r["text"], "meta": json.loads(r["meta"])} for r in rows
        ]

    def add_source_label(
        self, record_id: str, task: str, source: str, label, confidence: float = 1.0
    ):
        self.con.execute(
            "INSERT OR REPLACE INTO source_labels VALUES (?,?,?,?,?)",
            (record_id, task, source, json.dumps(label), float(confidence)),
        )
        self.con.commit()

    def source_labels_for(self, record_id: str, task: str) -> list[dict]:
        rows = self.con.execute(
            "SELECT * FROM source_labels WHERE record_id=? AND task=?", (record_id, task)
        ).fetchall()
        return [
            {
                "source": r["source"],
                "label": json.loads(r["label"]),
                "confidence": r["confidence"],
            }
            for r in rows
        ]

    def all_source_labels(self, task: str) -> list[dict]:
        rows = self.con.execute("SELECT * FROM source_labels WHERE task=?", (task,)).fetchall()
        return [
            {
                "record_id": r["record_id"],
                "source": r["source"],
                "label": json.loads(r["label"]),
                "confidence": r["confidence"],
            }
            for r in rows
        ]

    def set_golden(self, record_id: str, task: str, label):
        self.con.execute(
            "INSERT OR REPLACE INTO golden_labels VALUES (?,?,?)",
            (record_id, task, json.dumps(label)),
        )
        self.con.commit()

    def get_golden(self, record_id: str, task: str):
        row = self.con.execute(
            "SELECT label FROM golden_labels WHERE record_id=? AND task=?", (record_id, task)
        ).fetchone()
        return json.loads(row["label"]) if row else None

    def golden_all(self, task: str) -> dict[str, object]:
        rows = self.con.execute("SELECT * FROM golden_labels WHERE task=?", (task,)).fetchall()
        return {r["record_id"]: json.loads(r["label"]) for r in rows}

    def set_agg(self, record_id: str, task: str, label, confidence: float):
        self.con.execute(
            "INSERT OR REPLACE INTO agg_labels VALUES (?,?,?,?)",
            (record_id, task, json.dumps(label), float(confidence)),
        )

    def commit(self):
        self.con.commit()

    def get_agg(self, record_id: str, task: str) -> dict | None:
        row = self.con.execute(
            "SELECT * FROM agg_labels WHERE record_id=? AND task=?", (record_id, task)
        ).fetchone()
        if not row:
            return None
        return {"label": json.loads(row["label"]), "confidence": row["confidence"]}

    def agg_all(self, task: str) -> dict[str, dict]:
        rows = self.con.execute("SELECT * FROM agg_labels WHERE task=?", (task,)).fetchall()
        return {
            r["record_id"]: {"label": json.loads(r["label"]), "confidence": r["confidence"]}
            for r in rows
        }
