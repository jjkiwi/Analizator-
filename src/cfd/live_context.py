"""Kontekst sygnalu zapisywany do dziennika oraz ocena rozliczonych sygnalow wedlug kontekstu.

Newsow i kalendarza makro nie da sie przetestowac wstecz (brak darmowego archiwum). Dlatego kazdy sygnal
dostaje przy zapisie pelny obraz kontekstu z tej chwili, a po rozliczeniu mozna sprawdzic, czy sygnaly
w danym kontekscie wypadaly lepiej. To jedyna uczciwa droga do oceny newsow: zbieranie w przod.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd

from .fundamentals import read_bias
from .now import FEATURE_NAMES, VALUE_NAMES, _context_for

NEWS_HOURS = 12.0
MACRO_NEAR_HOURS = 6.0
MIN_N = 30


def news_context(conn: sqlite3.Connection, symbol: str, side: int, now: datetime, hours: float = NEWS_HOURS) -> dict:
    """Istotne newsy dla symbolu z ostatnich godzin: liczba, najwyzsza waga i zgodnosc kierunku z sygnalem."""
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """SELECT importance, direction, classifier FROM news
           WHERE importance >= 2 AND fetched >= ? AND fetched <= ? AND (',' || symbols || ',') LIKE ?""",
        (since, now.strftime("%Y-%m-%d %H:%M:%S"), f"%,{symbol},%"),
    ).fetchall()
    total = 0
    for r in rows:
        if r["direction"]:
            total += json.loads(r["direction"]).get(symbol, 0) * r["importance"]
    sign = (total > 0) - (total < 0)
    label = "brak" if not rows else "zgodny" if sign * side > 0 else "przeciwny" if sign * side < 0 else "bez_kierunku"
    return {"news_n": len(rows), "news_max": max((r["importance"] for r in rows), default=0), "news_dir": sign,
            "news_llm": sum(1 for r in rows if r["classifier"] and r["classifier"] != "rules"), "news": label}


def macro_context(conn: sqlite3.Connection, now: datetime, near_hours: float = MACRO_NEAR_HOURS) -> dict:
    """Odleglosc w godzinach do najblizszej i od ostatniej publikacji makro o najwyzszej wadze."""
    iso = now.isoformat()
    nxt = conn.execute("SELECT MIN(time) FROM macro_events WHERE importance >= 3 AND time > ?", (iso,)).fetchone()[0]
    prev = conn.execute("SELECT MAX(time) FROM macro_events WHERE importance >= 3 AND time <= ?", (iso,)).fetchone()[0]
    hours = lambda t: None if t is None else round(abs((datetime.fromisoformat(t) - now).total_seconds()) / 3600, 1)
    to_next, since_prev = hours(nxt), hours(prev)
    known = conn.execute("SELECT COUNT(*) FROM macro_events").fetchone()[0] > 0
    label = ("brak" if not known else "przed_publikacja" if to_next is not None and to_next <= near_hours
             else "po_publikacji" if since_prev is not None and since_prev <= near_hours else "daleko")
    return {"macro_next_h": to_next, "macro_prev_h": since_prev, "macro": label}


def signal_context(conn: sqlite3.Connection, inst, side: int, df: pd.DataFrame, daily: pd.DataFrame, interval: str,
                   vix: pd.Series | None, now: datetime | None = None) -> dict:
    """Pelny kontekst sygnalu w chwili wykrycia: technika, fundamenty, newsy, makro."""
    now = now or datetime.now(timezone.utc)
    bias = read_bias(conn, inst.symbol)
    ctx: dict = dict(_context_for(side, df, daily, interval, vix, bias))
    ctx["bias_value"] = bias
    ctx.update(news_context(conn, inst.symbol, side, now))
    ctx.update(macro_context(conn, now))
    return ctx


LABELS = ("news", "macro", "regime", "d1_trend", "bias", "vol", "vix", "session")
LABEL_NAMES = {**FEATURE_NAMES, "news": "newsy z 12 h", "macro": "kalendarz makro"}
LABEL_VALUES = {**VALUE_NAMES, "bez_kierunku": "są, bez kierunku", "przed_publikacja": "do 6 h przed publikacją",
                "po_publikacji": "do 6 h po publikacji", "daleko": "daleko od publikacji"}


def journal_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    """Rozliczone sygnaly z dziennika z rozwinietym kontekstem (tylko te zapisane z pelnym kontekstem)."""
    rows = []
    for r in conn.execute("SELECT symbol, strategy, interval, time, side, status, r_result, context FROM signals "
                          "WHERE status != 'open' AND r_result IS NOT NULL"):
        ctx = json.loads(r["context"] or "{}")
        if "news" not in ctx:
            continue
        rows.append({"symbol": r["symbol"], "strategy": r["strategy"], "interval": r["interval"], "time": r["time"],
                     "side": r["side"], "status": r["status"], "r": r["r_result"], **{k: ctx.get(k, "brak") for k in LABELS}})
    return pd.DataFrame(rows)


def journal_report(df: pd.DataFrame, total_open: int = 0) -> str:
    """Skutecznosc rozliczonych sygnalow w podziale na kontekst. Male proby sa oznaczane, a nie interpretowane."""
    if df.empty:
        return (f"Brak rozliczonych sygnalow z zapisanym kontekstem (otwartych: {total_open}). "
                "Dziennik zbiera je przy kazdym skanie; wynik pojawi sie po rozliczeniu pierwszych sygnalow.")
    n, mean = len(df), df["r"].mean()
    lines = [f"Rozliczonych sygnalow z kontekstem: {n} (otwartych: {total_open}). Srednio {mean:+.3f} R, "
             f"zyskownych {100 * (df['r'] > 0).mean():.0f}%.", "",
             "| Cecha | Wartość | Sygnałów | Zyskownych | Średnio R | t | Ocena |", "|---|---|---|---|---|---|---|"]
    for feat in LABELS:
        for value, part in sorted(df.groupby(feat), key=lambda kv: -len(kv[1])):
            if value in ("brak", "dzienny"):
                continue
            k, m = len(part), part["r"].mean()
            sd = part["r"].std(ddof=1) if k > 1 else 0.0
            t = m / (sd / math.sqrt(k)) if sd and sd > 0 else 0.0
            verdict = "za mało danych" if k < MIN_N else "lepiej niż ogół" if t >= 2 and m > 0 else "gorzej niż ogół" if t <= -2 else "bez różnicy"
            lines.append(f"| {LABEL_NAMES[feat]} | {LABEL_VALUES.get(value, value)} | {k} | {100 * (part['r'] > 0).mean():.0f}% "
                         f"| {m:+.3f} | {t:.1f} | {verdict} |")
    lines += ["", f"Ocena wymaga co najmniej {MIN_N} sygnalow w grupie. Przy kilkunastu grupach jedna lub dwie "
                  "wyjda 'lepiej' przez przypadek: wniosek ma sens dopiero, gdy utrzyma sie na kolejnych sygnalach."]
    return "\n".join(lines)
