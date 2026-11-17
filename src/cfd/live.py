"""Tor "na zywo" dla dashboardu: swieze newsy i notowania, zapisywane co kilka minut do live.json.

Strona (dashboard) doczytuje ten plik z galezi `live` bez przebudowy calej strony. Newsy pokazuja, jakich instrumentow
dotycza i o ile cena ruszyla sie od publikacji (z notowan godzinowych, opoznionych o kilkanascie minut).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd

from .data import DataSourceError

DEFAULT_WATCHLIST = ["US500", "US100", "DE40", "W20", "UK100", "JP225", "USDIDX", "VIX",
                     "GOLD", "SILVER", "OIL", "NATGAS", "COPPER", "BITCOIN", "ETHEREUM"]


def quotes(instruments: dict, data_service, symbols: list[str], refresh: bool = True) -> dict[str, dict]:
    """Ostatnia cena (swieca 1h, takze niedomknieta), zmiana od zamkniecia poprzedniej sesji i krotki przebieg 48 h."""
    out: dict[str, dict] = {}
    for sym in symbols:
        inst = instruments.get(sym)
        if inst is None or not inst.sources:
            continue
        try:
            h = data_service.get(inst, "1h", refresh=refresh)
            d = data_service.get(inst, "1d")
        except DataSourceError:
            continue
        if h.empty or len(d) < 2:
            continue
        last_t, last = h.index[-1], float(h["close"].iloc[-1])
        prev_days = d[d.index.normalize() < last_t.normalize()]
        prev = float(prev_days["close"].iloc[-1]) if len(prev_days) else float(d["close"].iloc[-2])
        spark = h["close"].iloc[-48:]
        out[sym] = {"name": inst.name, "category": inst.category, "price": last, "time": last_t.isoformat(),
                    "change_pct": 100 * (last / prev - 1) if prev else None,
                    "spark": [round(float(x), 6) for x in spark]}
    return out


def _price_at(h: pd.DataFrame, t: pd.Timestamp) -> float | None:
    """Cena z swiecy godzinowej obejmujacej chwile t (otwarcie tej swiecy), None gdy brak danych."""
    pos = h.index.searchsorted(t, side="right") - 1
    if pos < 0 or pos >= len(h):
        return None
    return float(h["open"].iloc[pos]) if h.index[pos] + timedelta(hours=1) > t else float(h["close"].iloc[pos])


def news_feed(conn: sqlite3.Connection, instruments: dict, data_service, hours: float = 24, limit: int = 80,
              min_importance: int = 1, now: datetime | None = None) -> list[dict]:
    """Newsy z ostatnich godzin z mapowaniem na instrumenty i ruchem ceny pierwszego instrumentu od publikacji."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """SELECT title, source, url, published, fetched, symbols, importance, direction, reason FROM news
           WHERE fetched >= ? AND importance >= ? AND symbols != '' ORDER BY COALESCE(published, fetched) DESC LIMIT ?""",
        (since, min_importance, limit)).fetchall()
    hourly: dict[str, pd.DataFrame | None] = {}
    out = []
    for r in rows:
        syms = [s for s in (r["symbols"] or "").split(",") if s]
        moved = None
        when = r["published"] or (r["fetched"].replace(" ", "T") + "+00:00")
        try:
            t = pd.Timestamp(when).tz_convert("UTC") if pd.Timestamp(when).tzinfo else pd.Timestamp(when).tz_localize("UTC")
        except (ValueError, TypeError):
            t = None
        if syms and t is not None and syms[0] in instruments:
            if syms[0] not in hourly:
                try:
                    hourly[syms[0]] = data_service.get(instruments[syms[0]], "1h")
                except DataSourceError:
                    hourly[syms[0]] = None
            h = hourly[syms[0]]
            if h is not None and len(h):
                p0 = _price_at(h, t)
                if p0 and h.index[-1] >= t:
                    moved = {"symbol": syms[0], "pct": 100 * (float(h["close"].iloc[-1]) / p0 - 1)}
        direction = json.loads(r["direction"]) if r["direction"] else {}
        out.append({"title": r["title"], "source": r["source"], "url": r["url"], "time": t.isoformat() if t is not None else None,
                    "symbols": syms, "importance": r["importance"], "direction": direction, "reason": r["reason"], "moved": moved})
    return out


def build_live(conn, instruments: dict, data_service, watchlist: list[str] | None = None, refresh: bool = True,
               now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    q = quotes(instruments, data_service, watchlist or DEFAULT_WATCHLIST, refresh=refresh)
    news = news_feed(conn, instruments, data_service, now=now)
    return {"generated": now.isoformat(), "quotes": q, "news": news}
