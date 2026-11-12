from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from .fusion import Confluence
from .macro.calendar import MacroEvent
from .models import Signal

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def send(self, text: str) -> bool: ...


class ConsoleNotifier:
    def send(self, text: str) -> bool:
        print("\n" + text + "\n", flush=True)
        return True


def in_quiet_hours(now: datetime, start: int, end: int, tz: str) -> bool:
    """Czy `now` (UTC) wypada w ciszy nocnej [start, end) liczonej w strefie `tz`. start == end wylacza cisze."""
    if start == end:
        return False
    hour = now.astimezone(ZoneInfo(tz)).hour
    return start <= hour < end if start < end else hour >= start or hour < end


class QuietNotifier:
    """Opakowanie na powiadomienia: w ciszy nocnej odklada wiadomosci do bazy, rano wysyla je jako jedno podsumowanie."""

    def __init__(self, inner: Notifier, conn: sqlite3.Connection, start: int = 23, end: int = 8, tz: str = "Europe/Warsaw", clock=None):
        self.inner, self.conn, self.start, self.end, self.tz = inner, conn, start, end, tz
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def send(self, text: str) -> bool:
        if in_quiet_hours(self._clock(), self.start, self.end, self.tz):
            self.conn.execute("INSERT INTO outbox (text) VALUES (?)", (text,))
            self.conn.commit()
            return True
        self.flush()
        return self.inner.send(text)

    def flush(self) -> int:
        """Wysyla zalegle wiadomosci (poza cisza). Zwraca ich liczbe."""
        if in_quiet_hours(self._clock(), self.start, self.end, self.tz):
            return 0
        rows = self.conn.execute("SELECT id, text FROM outbox ORDER BY id").fetchall()
        if not rows:
            return 0
        header = f"🌙 Podsumowanie nocy: {len(rows)} powiadomień\n\n"
        chunks, current = [], header
        for r in rows:
            block = r["text"] + "\n\n———\n\n"
            if len(current) + len(block) > 3800:
                chunks.append(current)
                current = ""
            current += block
        chunks.append(current)
        if all(self.inner.send(c.rstrip("—\n ")) for c in chunks):
            self.conn.execute("DELETE FROM outbox WHERE id <= ?", (rows[-1]["id"],))
            self.conn.commit()
        return len(rows)


def notifier_from_env() -> Notifier:
    """Powiadomienia trafiaja do logu. Wysylka na Telegram zostala usunieta razem z torem szybkim (decyzja z 2026-11-12)."""
    return ConsoleNotifier()


def _fmt(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ") if abs(x) >= 100 else f"{x:.4g}"


def format_signal(sig: Signal, interval: str, conf: Confluence | None = None, validated: bool = True) -> str:
    risk, reward = abs(sig.ref_price - sig.stop_loss), abs(sig.take_profit - sig.ref_price)
    lines = [
        f"📈 SYGNAŁ {sig.direction} {sig.symbol} ({interval})" if sig.side > 0 else f"📉 SYGNAŁ {sig.direction} {sig.symbol} ({interval})",
        f"Strategia: {sig.strategy}" + ("" if validated else " (NIEZWALIDOWANA)"),
        f"Cena ref.: {_fmt(sig.ref_price)} | SL {_fmt(sig.stop_loss)} | TP {_fmt(sig.take_profit)} | R:R 1:{reward / risk:.1f}" if risk else f"Cena ref.: {_fmt(sig.ref_price)}",
        f"Powód: {sig.rationale}",
    ]
    if conf:
        lines.append(f"Zgodność: {conf.label} ({conf.score:+.1f}) – {conf.text}")
    lines.append("Ceny ze źródła danych, nie z XTB. Poziomy przelicz w xStation.")
    return "\n".join(lines)


def format_news(item, cls) -> str:
    arrows = {1: "↑", -1: "↓", 0: "·"}
    syms = " ".join(f"{s}{arrows[d]}" for s, d in cls.directions.items())
    head = {3: "🔴 PILNE", 2: "🟡 ISTOTNE"}.get(cls.importance, "NEWS")
    lines = [f"{head}: {item.title}", f"Instrumenty: {syms}"]
    if cls.reason:
        lines.append(f"Ocena ({cls.classifier}): {cls.reason}")
    if item.url:
        lines.append(item.url)
    return "\n".join(lines)


def format_macro_before(event: MacroEvent, symbols: list[str], minutes: int) -> str:
    fc = f"prognoza {event.forecast:g}" if event.forecast is not None else "brak prognozy"
    pv = f", poprzednio {event.previous:g}" if event.previous is not None else ""
    return (f"⏰ Za {minutes} min: {event.country} {event.name}\n{fc}{pv}\n"
            f"Dotyczy: {', '.join(symbols) if symbols else 'brak reguły dla Twoich instrumentów'}")


def format_macro_after(event: MacroEvent, effects: dict[str, int]) -> str:
    arrows = {1: "↑", -1: "↓", 0: "·"}
    return (f"📊 {event.country} {event.name}: odczyt {event.actual:g} vs prognoza {event.forecast:g}\n"
            f"Podręcznikowa reakcja: {' '.join(f'{s}{arrows[d]}' for s, d in effects.items())}")
