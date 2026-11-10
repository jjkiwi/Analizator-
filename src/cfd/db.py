"""Jedna baza SQLite na stan aplikacji: dziennik sygnalow, newsy, kalendarz, bias fundamentalny."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL, strategy TEXT NOT NULL, interval TEXT NOT NULL,
    time TEXT NOT NULL, side INTEGER NOT NULL,
    ref_price REAL NOT NULL, stop_loss REAL NOT NULL, take_profit REAL NOT NULL,
    rationale TEXT, score REAL, context TEXT,
    status TEXT NOT NULL DEFAULT 'open',      -- open | tp | sl | expired
    resolved_time TEXT, r_result REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(symbol, strategy, interval, time)
);
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    source TEXT, title TEXT NOT NULL, summary TEXT, url TEXT,
    published TEXT, fetched TEXT NOT NULL DEFAULT (datetime('now')),
    norm_title TEXT, symbols TEXT,            -- symbole rozdzielone przecinkiem
    importance INTEGER, direction TEXT,       -- JSON: {symbol: -1|0|1}
    reason TEXT, classifier TEXT, alerted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS news_published ON news(published);
CREATE TABLE IF NOT EXISTS macro_events (
    id TEXT PRIMARY KEY,
    time TEXT NOT NULL, country TEXT, name TEXT NOT NULL, importance INTEGER,
    actual REAL, forecast REAL, previous REAL, unit TEXT,
    alerted_before INTEGER NOT NULL DEFAULT 0, alerted_after INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fundamental_bias (
    symbol TEXT PRIMARY KEY, bias REAL NOT NULL, components TEXT, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_health (
    source TEXT PRIMARY KEY, last_ok TEXT, last_error TEXT, last_error_time TEXT, fail_streak INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path | str = "data/cfd.sqlite") -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
