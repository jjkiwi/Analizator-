"""Praca ciagla: skan techniczny, newsy, kalendarz makro, bias fundamentalny, kontrola zrodel."""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import journal
from .data import DataService, DataSourceError
from .fundamentals import compute_bias, read_bias, save_bias
from .fusion import confluence
from .macro import MacroRules, surprise_effects, upcoming, upsert_events
from .models import Instrument
from .news import fetch_feed, process_items
from .news.pipeline import recent_news_direction
from .notify import Notifier, format_macro_after, format_macro_before, format_news, format_signal
from .scanner import latest_signal
from .strategies import REGISTRY

log = logging.getLogger(__name__)


@dataclass
class Context:
    conn: sqlite3.Connection
    settings: dict
    instruments: dict[str, Instrument]
    data: DataService
    notifier: Notifier
    feeds: list = field(default_factory=list)
    mapper: object | None = None
    classifier: object | None = None
    cheap_classifier: object | None = None
    macro_source: object | None = None
    macro_rules: MacroRules | None = None
    fund_components: dict = field(default_factory=dict)
    fund_series: object | None = None  # callable: id serii -> pd.Series
    _last: dict = field(default_factory=dict)  # nazwa zadania/feedu -> czas ostatniego uruchomienia


# ---------- kontrola zrodel ----------

def health_ok(ctx: Context, source: str) -> None:
    ctx.conn.execute(
        """INSERT INTO source_health (source, last_ok, fail_streak) VALUES (?, datetime('now'), 0)
           ON CONFLICT(source) DO UPDATE SET last_ok=datetime('now'), fail_streak=0""", (source,))
    ctx.conn.commit()


def health_fail(ctx: Context, source: str, error: str, alert: bool = True) -> bool:
    """Zapisuje porazke zrodla. Zwraca True, gdy wlasnie przekroczono prog alertu."""
    ctx.conn.execute(
        """INSERT INTO source_health (source, last_error, last_error_time, fail_streak) VALUES (?, ?, datetime('now'), 1)
           ON CONFLICT(source) DO UPDATE SET last_error=excluded.last_error, last_error_time=datetime('now'),
                                             fail_streak=fail_streak+1""", (source, error[:300]))
    ctx.conn.commit()
    streak = ctx.conn.execute("SELECT fail_streak FROM source_health WHERE source=?", (source,)).fetchone()[0]
    crossed = streak == ctx.settings["health"]["alert_after_failures"]
    if crossed and alert:
        ctx.notifier.send(f"⚠️ Źródło '{source}' zawiodło {streak} razy z rzędu.\nOstatni błąd: {error[:200]}")
    return crossed


# ---------- zadania ----------

def job_scan(ctx: Context) -> int:
    cfg = ctx.settings["scan"]
    strategies = [REGISTRY[name]() for name in cfg["strategies"] if name in REGISTRY]
    new = 0
    broken: list[str] = []
    for inst in ctx.instruments.values():
        if not inst.sources:
            continue
        for interval in cfg["intervals"]:
            try:
                df, source = ctx.data.update(inst, interval)
                health_ok(ctx, f"candles:{source}")
            except DataSourceError as exc:
                # Alerty zbieramy w jedna wiadomosc: awaria sieci nie moze wyslac 40 powiadomien.
                if health_fail(ctx, f"candles:{inst.symbol}", str(exc), alert=False):
                    broken.append(f"{inst.symbol} ({interval})")
                continue
            journal.resolve(ctx.conn, inst.symbol, interval, df, inst.costs, cfg["expire_bars"])
            for strategy in strategies:
                sig = latest_signal(inst, strategy, df)
                if sig is None:
                    continue
                conf = confluence(sig.side, read_bias(ctx.conn, inst.symbol), recent_news_direction(ctx.conn, inst.symbol))
                if journal.record(ctx.conn, sig, interval, conf.score, {"confluence": conf.text, "label": conf.label}):
                    new += 1
                    if strategy.name in cfg["alert_strategies"]:
                        ctx.notifier.send(format_signal(sig, interval, conf))
    if broken:
        shown = ", ".join(broken[:15]) + (f" i {len(broken) - 15} innych" if len(broken) > 15 else "")
        ctx.notifier.send(f"⚠️ Brak świeżych świec ({len(broken)}): {shown}.\nSygnały dla tych instrumentów są wstrzymane.")
    return new


def job_news(ctx: Context) -> int:
    if not ctx.feeds or ctx.mapper is None:
        return 0
    cfg = ctx.settings["news"]
    items, now = [], time.monotonic()
    for feed in ctx.feeds:
        if now - ctx._last.get(f"feed:{feed.name}", -1e9) < feed.poll_seconds:
            continue
        ctx._last[f"feed:{feed.name}"] = now
        try:
            items += fetch_feed(feed)
            health_ok(ctx, f"feed:{feed.name}")
        except Exception as exc:  # zepsuty feed nie moze zatrzymac pozostalych
            health_fail(ctx, f"feed:{feed.name}", f"{type(exc).__name__}: {exc}")
    fresh = process_items(ctx.conn, items, ctx.mapper, ctx.classifier, ctx.cheap_classifier, cfg["max_age_hours"])
    sent = 0
    for item, cls in fresh:
        if cls.importance >= cfg["alert_min_importance"]:
            ctx.notifier.send(format_news(item, cls))
            ctx.conn.execute("UPDATE news SET alerted=1 WHERE id=?", (item.id,))
            sent += 1
    ctx.conn.commit()
    return sent


def job_macro(ctx: Context, now: datetime | None = None) -> int:
    if ctx.macro_rules is None:
        return 0
    cfg = ctx.settings["macro"]
    now = now or datetime.now(timezone.utc)
    if ctx.macro_source is not None and time.monotonic() - ctx._last.get("macro_refresh", -1e9) >= cfg["refresh_minutes"] * 60:
        ctx._last["macro_refresh"] = time.monotonic()
        try:
            upsert_events(ctx.conn, ctx.macro_source.fetch())
            health_ok(ctx, "macro")
        except Exception as exc:
            health_fail(ctx, "macro", f"{type(exc).__name__}: {exc}")
    sent = 0
    for ev in upcoming(ctx.conn, timedelta(minutes=cfg["alert_minutes_before"]), cfg["alert_min_importance"], now):
        row = ctx.conn.execute("SELECT alerted_before FROM macro_events WHERE id=?", (ev.id,)).fetchone()
        if row["alerted_before"]:
            continue
        symbols = [s for s in ctx.macro_rules.effects_for(ev) if s in ctx.instruments]
        if symbols:
            minutes = max(int((ev.time - now).total_seconds() // 60), 0)
            ctx.notifier.send(format_macro_before(ev, symbols, minutes))
            sent += 1
        ctx.conn.execute("UPDATE macro_events SET alerted_before=1 WHERE id=?", (ev.id,))
    # odczyty, ktore pojawily sie od ostatniego przebiegu
    rows = ctx.conn.execute(
        "SELECT id FROM macro_events WHERE actual IS NOT NULL AND forecast IS NOT NULL AND alerted_after=0 AND time >= ?",
        ((now - timedelta(hours=6)).isoformat(),)).fetchall()
    from .macro.calendar import _row_event
    for r in rows:
        ev = _row_event(ctx.conn.execute("SELECT * FROM macro_events WHERE id=?", (r["id"],)).fetchone())
        effects = {s: d for s, d in surprise_effects(ev, ctx.macro_rules).items() if s in ctx.instruments}
        if effects and ev.importance >= cfg["alert_min_importance"]:
            ctx.notifier.send(format_macro_after(ev, effects))
            sent += 1
        ctx.conn.execute("UPDATE macro_events SET alerted_after=1 WHERE id=?", (r["id"],))
    ctx.conn.commit()
    return sent


def job_fundamentals(ctx: Context) -> int:
    if ctx.fund_series is None:
        return 0
    n = 0
    for symbol, comps in ctx.fund_components.items():
        if symbol not in ctx.instruments:
            continue
        bias, details = compute_bias(comps, ctx.fund_series)
        if bias is not None:
            save_bias(ctx.conn, symbol, bias, details)
            n += 1
    (health_ok(ctx, "fundamentals") if n else health_fail(ctx, "fundamentals", "zadna skladowa nie zostala policzona"))
    return n


# ---------- petla ----------

def _due(ctx: Context, name: str, every_seconds: float) -> bool:
    now = time.monotonic()
    if now - ctx._last.get(name, -1e9) >= every_seconds:
        ctx._last[name] = now
        return True
    return False


def job_dashboard(ctx: Context) -> str:
    """Odswieza statyczny panel HTML, zeby dzialal bez osobnego harmonogramu."""
    from .dashboard import write

    cfg = ctx.settings.get("dashboard", {})
    return str(write(ctx.conn, cfg.get("path", "reports/panel.html")))


def run_once(ctx: Context) -> dict:
    """Jeden pelny przebieg wszystkich zadan. Blad jednego zadania nie zatrzymuje pozostalych."""
    out = {}
    for name, job in (("fundamentals", job_fundamentals), ("macro", job_macro), ("news", job_news), ("scan", job_scan)):
        try:
            out[name] = job(ctx)
        except Exception as exc:
            log.exception("zadanie %s padlo", name)
            out[name] = f"BLAD: {type(exc).__name__}: {exc}"
    return out


def run_forever(ctx: Context, tick: float = 15.0) -> None:
    s = ctx.settings
    schedule = (
        ("fundamentals", job_fundamentals, s["fundamentals"]["refresh_hours"] * 3600),
        ("macro", job_macro, 60),
        ("news", job_news, s["news"]["every_seconds"]),
        ("scan", job_scan, s["scan"]["every_minutes"] * 60),
    )
    dash_minutes = s.get("dashboard", {}).get("refresh_minutes", 5)
    if dash_minutes:
        schedule += (("dashboard", job_dashboard, dash_minutes * 60),)
    ctx.notifier.send("✅ Analizator CFD uruchomiony.")
    while True:
        for name, job, every in schedule:
            if _due(ctx, f"job:{name}", every):
                try:
                    job(ctx)
                except Exception:
                    log.exception("zadanie %s padlo", name)
        time.sleep(tick)
