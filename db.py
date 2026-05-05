import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "app.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

DEMO_KIDS = [("tamar", "תמר"), ("noa", "נועה"), ("shira", "שירה")]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA_PATH.read_text())
    if conn.execute("SELECT COUNT(*) FROM kids").fetchone()[0] == 0:
        conn.executemany("INSERT INTO kids(id, display_name) VALUES(?, ?)", DEMO_KIDS)
        conn.commit()
    conn.close()
