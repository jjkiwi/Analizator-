from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from .classify import Classification
from .mapper import KeywordMapper
from .models import NewsItem


def _tokens(norm: str) -> set[str]:
    return {t for t in norm.split() if len(t) > 2}


def is_duplicate(norm: str, recent_norms: list[str], threshold: float = 0.8) -> bool:
    """Ten sam news z innego zrodla: identyczny albo prawie identyczny tytul."""
    a = _tokens(norm)
    if not a:
        return False
    for other in recent_norms:
        if other == norm:
            return True
        b = _tokens(other)
        if b and len(a & b) / len(a | b) >= threshold:
            return True
    return False


def _topic_key(match: dict) -> tuple:
    return (tuple(match.get("high_impact_hits", ())), tuple(sorted(match["direct"])))


def process_items(
    conn: sqlite3.Connection,
    items: list[NewsItem],
    mapper: KeywordMapper,
    classifier,
    cheap_classifier=None,
    max_age_hours: float = 24.0,
    now: datetime | None = None,
    repeat_cooldown_minutes: float = 60.0,
) -> list[tuple[NewsItem, Classification]]:
    """Filtr -> deduplikacja -> mapowanie -> klasyfikacja -> zapis. Zwraca NOWE, zmapowane newsy.

    `cheap_classifier` (reguly) dziala jako bramka przed drogim klasyfikatorem:
    do LLM trafiaja tylko newsy, ktore reguly ocenily na co najmniej 2.

    Jedno zdarzenie (np. odczyt CPI) opisuje w ciagu godziny kilkadziesiat redakcji roznymi slowami,
    wiec deduplikacja po tytule tego nie lapie. Dlatego waga 3 z regul dla tematu (te same frazy
    wysokiej wagi + ten sam instrument wprost), ktory dostal juz wage 3 w ostatnich
    `repeat_cooldown_minutes`, jest obnizana do 2. LLM nadal moze przyznac 3. Wartosc 0 wylacza.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    recent = [r["norm_title"] for r in conn.execute(
        "SELECT norm_title FROM news WHERE fetched >= datetime('now', '-2 days') ORDER BY fetched DESC LIMIT 500")]
    seen_topics: set[tuple] = set()
    if repeat_cooldown_minutes > 0:
        for r in conn.execute(
            "SELECT title, summary FROM news WHERE importance = 3 AND fetched >= datetime('now', ?)",
            (f"-{repeat_cooldown_minutes} minutes",),
        ):
            old = mapper.match(f"{r['title']}. {r['summary'] or ''}", r["title"])
            seen_topics.add(_topic_key(old))
    out = []
    for item in items:
        if item.published and item.published < cutoff:
            continue
        if conn.execute("SELECT 1 FROM news WHERE id=?", (item.id,)).fetchone():
            continue
        norm = item.norm_title
        dup = is_duplicate(norm, recent)
        match = mapper.match(item.text, item.title)
        cls = None
        if match["symbols"] and not dup:
            gate = cheap_classifier or classifier
            cls = gate.classify(item, match)
            if cls.classifier == "rules" and cls.importance == 3 and repeat_cooldown_minutes > 0:
                key = _topic_key(match)
                if key in seen_topics:
                    cls.importance, cls.reason = 2, "kolejny news o temacie, ktory juz dostal wage 3"
                seen_topics.add(key)
            if cheap_classifier is not None and cls.importance >= 2:
                cls = classifier.classify(item, match)
        conn.execute(
            """INSERT OR IGNORE INTO news (id, source, title, summary, url, published, norm_title, symbols,
                                           importance, direction, reason, classifier)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (item.id, item.source, item.title, item.summary, item.url,
             item.published.isoformat() if item.published else None, norm,
             ",".join(match["symbols"]),
             cls.importance if cls else (0 if dup else None),
             json.dumps(cls.directions) if cls else None,
             ("duplikat" if dup else None) if cls is None else cls.reason,
             cls.classifier if cls else None),
        )
        recent.insert(0, norm)
        if cls:
            out.append((item, cls))
    conn.commit()
    return out


def recent_news_direction(conn: sqlite3.Connection, symbol: str, hours: float = 12.0, min_importance: int = 2) -> int:
    """Znak sumy kierunkow istotnych newsow dla symbolu z ostatnich godzin (-1, 0, +1)."""
    rows = conn.execute(
        """SELECT direction, importance FROM news
           WHERE importance >= ? AND direction IS NOT NULL
             AND fetched >= datetime('now', ?) AND (',' || symbols || ',') LIKE ?""",
        (min_importance, f"-{hours} hours", f"%,{symbol},%"),
    ).fetchall()
    total = sum(json.loads(r["direction"]).get(symbol, 0) * r["importance"] for r in rows)
    return (total > 0) - (total < 0)
