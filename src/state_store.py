# src/state_store.py
"""
SQLite-based persistent state for tracking seen URLs.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent.parent / "state" / "seen_urls.sqlite"


def init_db(db_path: Path = DB_PATH) -> None:
    """Create the database and schema if it doesn't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_urls (
                url TEXT PRIMARY KEY,
                first_seen_utc TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def is_url_seen(url: str, db_path: Path = DB_PATH) -> bool:
    """Check if a URL has been seen before."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT 1 FROM seen_urls WHERE url = ?", (url,))
        return cur.fetchone() is not None
    finally:
        conn.close()


def mark_url_seen(url: str, db_path: Path = DB_PATH, timestamp: Optional[str] = None) -> None:
    """Mark a URL as seen (insert if not exists)."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen_urls (url, first_seen_utc) VALUES (?, ?)",
            (url, timestamp)
        )
        conn.commit()
    finally:
        conn.close()


def get_all_seen_urls(db_path: Path = DB_PATH) -> list[str]:
    """Return all seen URLs (useful for debugging)."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT url FROM seen_urls")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
