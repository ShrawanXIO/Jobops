import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "jobs.db"
SCHEMA_PATH = BASE_DIR / "data" / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema)
    print(f"Database initialised at {DB_PATH}")


def execute(query: str, params: tuple = ()) -> sqlite3.Cursor:
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor


def fetchall(query: str, params: tuple = ()) -> list[sqlite3.Row]:
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall()


def fetchone(query: str, params: tuple = ()) -> sqlite3.Row | None:
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchone()


def today_application_count(user_id: str) -> int:
    row = fetchone(
        """
        SELECT COUNT(*) as count FROM applications
        WHERE user_id = ?
        AND DATE(applied_at) = DATE('now')
        """,
        (user_id,),
    )
    return row["count"] if row else 0


def job_exists(job_id: str) -> bool:
    row = fetchone("SELECT id FROM jobs WHERE id = ?", (job_id,))
    return row is not None


def company_is_blocked(domain: str, user_id: str) -> bool:
    row = fetchone(
        """
        SELECT domain FROM companies_seen
        WHERE domain = ?
        AND user_id = ?
        AND (blocklist = 1 OR cooldown_until > DATETIME('now'))
        """,
        (domain, user_id),
    )
    return row is not None
