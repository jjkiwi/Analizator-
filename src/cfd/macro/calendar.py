from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

_NUM = re.compile(r"^\s*([-+]?\d+(?:[.,]\d+)?)\s*([KMBT%]?)", re.I)
_MULT = {"": 1.0, "%": 1.0, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def parse_value(text) -> float | None:
    """'0.3%' -> 0.3, '215K' -> 215000, '<0.1%' -> 0.1, '' -> None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = _NUM.match(str(text).replace("<", "").replace(">", "").replace("\u2212", "-"))
    if not m:
        return None
    return float(m.group(1).replace(",", ".")) * _MULT[m.group(2).upper()]


@dataclass(frozen=True)
class MacroEvent:
    time: datetime  # UTC
    country: str  # kod waluty: USD, EUR, ...
    name: str
    importance: int  # 1-3
    actual: float | None = None
    forecast: float | None = None
    previous: float | None = None
    unit: str = ""

    @property
    def id(self) -> str:
        key = f"{self.time:%Y-%m-%dT%H:%M}|{self.country}|{self.name}".lower()
        return hashlib.sha1(key.encode()).hexdigest()[:16]


class MacroRules:
    def __init__(self, rules: list[dict]):
        self.rules = rules

    @classmethod
    def from_file(cls, path: Path | str = "config/macro_rules.yaml"):
        return cls(yaml.safe_load(Path(path).read_text(encoding="utf-8"))["rules"])

    def effects_for(self, event: MacroEvent) -> dict[str, int]:
        name = event.name.lower()
        for rule in self.rules:
            if rule.get("country") in (None, event.country) and any(m in name for m in rule["match"]):
                return dict(rule["effects"])
        return {}


def surprise_effects(event: MacroEvent, rules: MacroRules, min_rel: float = 0.0) -> dict[str, int]:
    """Kierunek pierwszej reakcji per symbol dla odczytu innego niz prognoza. Pusty slownik = brak niespodzianki."""
    if event.actual is None or event.forecast is None:
        return {}
    diff = event.actual - event.forecast
    scale = max(abs(event.forecast), 1e-9)
    if diff == 0 or abs(diff) / scale < min_rel:
        return {}
    sign = 1 if diff > 0 else -1
    return {s: d * sign for s, d in rules.effects_for(event).items()}


def upsert_events(conn: sqlite3.Connection, events: list[MacroEvent]) -> int:
    """Wstawia nowe wydarzenia i uzupelnia odczyty juz znanych. Nie nadpisuje odczytu wartoscia pusta."""
    n = 0
    for e in events:
        cur = conn.execute(
            """INSERT INTO macro_events (id, time, country, name, importance, actual, forecast, previous, unit)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                   actual=COALESCE(excluded.actual, actual),
                   forecast=COALESCE(excluded.forecast, forecast),
                   previous=COALESCE(excluded.previous, previous),
                   importance=excluded.importance""",
            (e.id, e.time.isoformat(), e.country, e.name, e.importance, e.actual, e.forecast, e.previous, e.unit),
        )
        n += cur.rowcount
    conn.commit()
    return n


def _row_event(row) -> MacroEvent:
    return MacroEvent(datetime.fromisoformat(row["time"]), row["country"], row["name"], row["importance"],
                      row["actual"], row["forecast"], row["previous"], row["unit"] or "")


def upcoming(conn: sqlite3.Connection, within: timedelta, min_importance: int = 1, now: datetime | None = None) -> list[MacroEvent]:
    now = now or datetime.now(timezone.utc)
    rows = conn.execute(
        "SELECT * FROM macro_events WHERE time >= ? AND time <= ? AND importance >= ? ORDER BY time",
        (now.isoformat(), (now + within).isoformat(), min_importance),
    ).fetchall()
    return [_row_event(r) for r in rows]


def set_actual(conn: sqlite3.Connection, name_fragment: str, actual: float, now: datetime | None = None) -> MacroEvent | None:
    """Reczne wpisanie odczytu dla najblizszego (w czasie) wydarzenia pasujacego do nazwy."""
    now = now or datetime.now(timezone.utc)
    rows = conn.execute("SELECT * FROM macro_events WHERE lower(name) LIKE ?", (f"%{name_fragment.lower()}%",)).fetchall()
    if not rows:
        return None
    row = min(rows, key=lambda r: abs((datetime.fromisoformat(r["time"]) - now).total_seconds()))
    conn.execute("UPDATE macro_events SET actual=? WHERE id=?", (actual, row["id"]))
    conn.commit()
    return _row_event(conn.execute("SELECT * FROM macro_events WHERE id=?", (row["id"],)).fetchone())
