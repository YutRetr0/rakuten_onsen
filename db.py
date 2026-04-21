"""SQLite storage backend for watcher state."""
import os
import sqlite3
import threading
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "rakuten_onsen.db")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS watches (
    id            TEXT PRIMARY KEY,
    region        TEXT NOT NULL,
    hotel_no      INTEGER NOT NULL,
    hotel_name    TEXT,
    checkin       TEXT NOT NULL,
    checkout      TEXT NOT NULL,
    adults        INTEGER NOT NULL DEFAULT 2,
    rooms         INTEGER NOT NULL DEFAULT 1,
    room_keywords TEXT NOT NULL DEFAULT '[]',
    max_price     INTEGER,
    channels      TEXT NOT NULL DEFAULT '["wecom"]',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watch_state (
    watch_id          TEXT PRIMARY KEY REFERENCES watches(id) ON DELETE CASCADE,
    last_available    INTEGER NOT NULL DEFAULT 0,
    last_notified_at  TEXT,
    last_check_at     TEXT,
    matched_count     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notification_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    watch_id      TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    notified_at   TEXT NOT NULL,
    matched_count INTEGER NOT NULL,
    channels      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_watch ON notification_history(watch_id, notified_at);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_conn():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
