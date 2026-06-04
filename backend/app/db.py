import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id TEXT NOT NULL,
    title TEXT NOT NULL,
    youtube_id TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES materials(id),
    idx INTEGER NOT NULL,
    text TEXT NOT NULL,
    start REAL NOT NULL,
    end REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL REFERENCES sentences(id),
    score REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def add_material(self, show_id: str, title: str,
                     youtube_id: str, audio_path: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO materials (show_id, title, youtube_id, audio_path) "
            "VALUES (?, ?, ?, ?)",
            (show_id, title, youtube_id, audio_path),
        )
        self.conn.commit()
        return cur.lastrowid

    def add_sentences(self, material_id: int, sentences: list[dict]) -> None:
        self.conn.executemany(
            "INSERT INTO sentences (material_id, idx, text, start, end) "
            "VALUES (?, ?, ?, ?, ?)",
            [(material_id, i, s["text"], s["start"], s["end"])
             for i, s in enumerate(sentences)],
        )
        self.conn.commit()

    def get_sentences(self, material_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, idx, text, start, end FROM sentences "
            "WHERE material_id = ? ORDER BY idx",
            (material_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_material(self, material_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM materials WHERE id = ?", (material_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_sentence_text(self, sentence_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT text FROM sentences WHERE id = ?", (sentence_id,)
        ).fetchone()
        return row["text"] if row else None

    def record_attempt(self, sentence_id: int, score: float, status: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO attempts (sentence_id, score, status) VALUES (?, ?, ?)",
            (sentence_id, score, status),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_attempts(self, sentence_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, sentence_id, score, status FROM attempts "
            "WHERE sentence_id = ? ORDER BY id",
            (sentence_id,),
        ).fetchall()
        return [dict(r) for r in rows]
