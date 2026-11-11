"""Synchronizacja z Supabase (PostgREST). SQLite zostaje lokalnym stanem roboczym toru wolnego,
a Supabase jest wspolna baza dla panelu i toru szybkiego (funkcje brzegowe).

Kierunki:
  push: signals, fundamental_bias, source_health  (SQLite -> Supabase, upsert)
  pull: otwarte sygnaly (gdy lokalna baza jest pusta, np. po utracie cache w GitHub Actions)
        oraz kierunek swiezych newsow per symbol (pisze je tor szybki)
"""
from __future__ import annotations

import json
import os
import sqlite3

import httpx


class SupabaseClient:
    def __init__(self, url: str | None = None, key: str | None = None, timeout: float = 30.0, transport=None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not self.url or not self.key:
            raise RuntimeError("Brak SUPABASE_URL lub SUPABASE_SERVICE_KEY")
        self._client = httpx.Client(
            base_url=f"{self.url}/rest/v1", timeout=timeout, transport=transport,
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )

    def upsert(self, table: str, rows: list[dict], on_conflict: str) -> int:
        for i in range(0, len(rows), 500):
            resp = self._client.post(
                f"/{table}", params={"on_conflict": on_conflict}, content=json.dumps(rows[i : i + 500], default=str),
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
            resp.raise_for_status()
        return len(rows)

    def select(self, table: str, params: dict) -> list[dict]:
        resp = self._client.get(f"/{table}", params=params)
        resp.raise_for_status()
        return resp.json()


SIGNAL_COLS = ["symbol", "strategy", "interval", "time", "side", "ref_price", "stop_loss", "take_profit",
               "rationale", "score", "context", "status", "resolved_time", "r_result"]


def push(conn: sqlite3.Connection, sb: SupabaseClient) -> dict:
    signals = [{c: r[c] for c in SIGNAL_COLS} for r in conn.execute("SELECT * FROM signals")]
    for s in signals:
        s["context"] = json.loads(s["context"] or "{}")
    bias = [{"symbol": r["symbol"], "bias": r["bias"], "components": json.loads(r["components"] or "[]"), "updated": r["updated"]}
            for r in conn.execute("SELECT * FROM fundamental_bias")]
    health = [dict(r) for r in conn.execute("SELECT * FROM source_health")]
    return {
        "signals": sb.upsert("signals", signals, "symbol,strategy,interval,time") if signals else 0,
        "fundamental_bias": sb.upsert("fundamental_bias", bias, "symbol") if bias else 0,
        "source_health": sb.upsert("source_health", health, "source") if health else 0,
    }


def pull_open_signals(conn: sqlite3.Connection, sb: SupabaseClient) -> int:
    """Odtwarza otwarte sygnaly w lokalnej bazie, zeby dalo sie je rozliczyc po utracie stanu."""
    rows = sb.select("signals", {"status": "eq.open", "select": ",".join(SIGNAL_COLS)})
    n = 0
    for r in rows:
        cur = conn.execute(
            """INSERT OR IGNORE INTO signals (symbol, strategy, interval, time, side, ref_price, stop_loss, take_profit,
                                              rationale, score, context, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'open')""",
            (r["symbol"], r["strategy"], r["interval"], r["time"], r["side"], r["ref_price"], r["stop_loss"],
             r["take_profit"], r["rationale"], r["score"], json.dumps(r.get("context") or {}, ensure_ascii=False)),
        )
        n += cur.rowcount
    conn.commit()
    return n


def pull_news_directions(conn: sqlite3.Connection, sb: SupabaseClient, hours: int = 12) -> int:
    """Kopiuje swieze, istotne newsy z Supabase do lokalnej tabeli `news`, zeby fuzja sygnalow je widziala."""
    from datetime import datetime, timedelta, timezone

    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = sb.select("news", {"importance": "gte.2", "fetched": f"gte.{since}",
                              "select": "id,source,title,url,published,norm_title,symbols,importance,direction,reason,classifier"})
    n = 0
    for r in rows:
        cur = conn.execute(
            """INSERT OR IGNORE INTO news (id, source, title, url, published, norm_title, symbols, importance, direction, reason, classifier, alerted)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
            (r["id"], r["source"], r["title"], r["url"], r["published"], r["norm_title"], r["symbols"], r["importance"],
             json.dumps(r["direction"]) if r["direction"] is not None else None, r["reason"], r["classifier"]),
        )
        n += cur.rowcount
    conn.commit()
    return n
