from __future__ import annotations

import logging
import os
from typing import Protocol

import httpx

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


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, timeout: float = 15.0):
        self.token, self.chat_id, self.timeout = token, chat_id, timeout

    def send(self, text: str) -> bool:
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text[:4000], "disable_web_page_preview": True},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            log.error("Telegram: nie udalo sie wyslac: %s", type(exc).__name__)
            return False


def notifier_from_env() -> Notifier:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    return TelegramNotifier(token, chat) if token and chat else ConsoleNotifier()


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
