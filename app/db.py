import sqlite3
from pathlib import Path

DB_PATH = Path("data") / "app.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                id TEXT PRIMARY KEY,
                original_filename TEXT,
                stored_filename TEXT,
                mime_type TEXT,
                size_bytes INTEGER,

                width INTEGER,
                height INTEGER,
                format TEXT,

                created_at TEXT,
                status TEXT,
                caption TEXT,
                error TEXT,
                processing_ms INTEGER,

                thumb_small_path TEXT,
                thumb_medium_path TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_images_created_at ON images(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_images_status ON images(status)")

    ensure_column("images", "processed_at", "TEXT")


def ensure_column(table: str, column: str, coltype: str) -> None:
    with get_conn() as conn:
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            conn.commit()