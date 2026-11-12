"""Fundamenty spolek: wycena, dynamika wynikow, zadluzenie, konsensus, data raportu (Yahoo przez yfinance).

Wynik to lista kontrolna, nie prognoza. Kazdy filar dostaje -1, 0 albo +1 wedlug jawnych progow, a suma daje
ocene opisowa dla spolki, ktora uzytkownik juz posiada: trzymac / mozna rozwazyc dokupienie / rozwazyc redukcje.
Progi sa podrecznikowe i NIE byly walidowane na historii (darmowych historycznych fundamentow nie ma),
wiec ocena porzadkuje fakty, a nie mierzy szanse zysku.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, datetime, timezone

from ..data.base import DataSourceError, Throttle

_THROTTLE = Throttle(2.0)
INFO_KEYS = (
    "currency", "marketCap", "currentPrice", "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
    "enterpriseToEbitda", "revenueGrowth", "earningsGrowth", "profitMargins", "operatingMargins", "returnOnEquity",
    "debtToEquity", "freeCashflow", "dividendYield", "targetMeanPrice", "numberOfAnalystOpinions", "recommendationMean",
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "sector", "industry", "trailingEps", "forwardEps",
)
REPORT_SOON_DAYS = 14


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def shape_snapshot(info: dict, calendar: dict | None, quarterly: dict | None) -> dict:
    """Sklada surowe odpowiedzi yfinance w jeden slownik. `quarterly`: {wiersz: {data ISO: wartosc}}."""
    if not info or _num(info.get("currentPrice")) is None and _num(info.get("marketCap")) is None:
        raise DataSourceError("yahoo: brak danych o spolce (zly symbol albo blokada)")
    snap = {k: (info.get(k) if isinstance(info.get(k), str) else _num(info.get(k))) for k in INFO_KEYS}
    dates = (calendar or {}).get("Earnings Date") or []
    dates = [d if isinstance(d, date) else date.fromisoformat(str(d)[:10]) for d in (dates if isinstance(dates, (list, tuple)) else [dates])]
    snap["earnings_date"] = min(dates).isoformat() if dates else None
    rev = {k: _num(v) for k, v in ((quarterly or {}).get("Total Revenue") or {}).items()}
    rev = {k: v for k, v in rev.items() if v is not None}
    net = {k: _num(v) for k, v in ((quarterly or {}).get("Net Income") or {}).items()}
    periods = sorted(rev, reverse=True)
    snap["quarter"] = periods[0] if periods else None
    snap["quarter_revenue"] = rev[periods[0]] if periods else None
    snap["quarter_net_income"] = net.get(periods[0]) if periods else None
    # ten sam kwartal rok wczesniej: piaty okres wstecz, o ile daty dziela ok. 12 miesiecy
    snap["quarter_revenue_yoy"] = None
    if len(periods) >= 5:
        gap = (date.fromisoformat(periods[0][:10]) - date.fromisoformat(periods[4][:10])).days
        if 350 <= gap <= 380 and rev[periods[4]]:
            snap["quarter_revenue_yoy"] = rev[periods[0]] / rev[periods[4]] - 1
    return snap


def fetch_snapshot(yahoo_symbol: str) -> dict:
    """Pobiera dane jednej spolki (trzy zapytania z odstepem). Kazdy blad to DataSourceError."""
    import yfinance as yf

    try:
        t = yf.Ticker(yahoo_symbol)
        _THROTTLE.wait()
        info = dict(t.info or {})
        _THROTTLE.wait()
        try:
            calendar = dict(t.calendar or {})
        except Exception:
            calendar = {}
        _THROTTLE.wait()
        try:
            q = t.quarterly_income_stmt
            quarterly = {row: {str(c)[:10]: q.loc[row, c] for c in q.columns} for row in ("Total Revenue", "Net Income") if row in q.index}
        except Exception:
            quarterly = {}
    except Exception as exc:
        raise DataSourceError(f"yahoo {yahoo_symbol}: {exc}") from exc
    try:
        return shape_snapshot(info, calendar, quarterly)
    except DataSourceError as exc:
        raise DataSourceError(f"yahoo {yahoo_symbol}: {exc}") from exc


def _pillar(name: str, score: int | None, text: str) -> dict:
    return {"name": name, "score": score, "text": text}


def _pct(v: float) -> str:
    return f"{100 * v:+.0f}%"


def assess(snap: dict, price_above_sma200: bool | None = None, today: date | None = None) -> dict:
    """Lista kontrolna: filary -1/0/+1 (None = brak danych) i ocena opisowa."""
    today = today or datetime.now(timezone.utc).date()
    p: list[dict] = []

    g = snap.get("quarter_revenue_yoy") if snap.get("quarter_revenue_yoy") is not None else snap.get("revenueGrowth")
    p.append(_pillar("Wzrost przychodów", None, "brak danych") if g is None else
             _pillar("Wzrost przychodów", 1 if g > 0.10 else -1 if g < 0 else 0, f"{_pct(g)} rok do roku"))

    m, roe = snap.get("profitMargins"), snap.get("returnOnEquity")
    if m is None:
        p.append(_pillar("Zyskowność", None, "brak danych"))
    else:
        s = -1 if m < 0 else 1 if m > 0.10 and (roe is None or roe > 0.10) else 0
        p.append(_pillar("Zyskowność", s, f"marża netto {_pct(m)}" + (f", ROE {_pct(roe)}" if roe is not None else "")))

    fpe, tpe = snap.get("forwardPE"), snap.get("trailingPE")
    pe = fpe if fpe is not None else tpe
    if pe is None:
        loss = (snap.get("trailingEps") or 0) < 0
        p.append(_pillar("Wycena", -1 if loss else None, "spółka ze stratą, brak C/Z" if loss else "brak danych"))
    else:
        s = -1 if pe < 0 or pe > 40 else 1 if pe < 15 else 0
        p.append(_pillar("Wycena", s, f"C/Z {'prognozowane' if fpe is not None else 'historyczne'} {pe:.0f}"))

    d = snap.get("debtToEquity")
    p.append(_pillar("Zadłużenie", None, "brak danych") if d is None else
             _pillar("Zadłużenie", 1 if d < 50 else -1 if d > 150 else 0, f"dług do kapitału {d:.0f}%"))

    tgt, price, n = snap.get("targetMeanPrice"), snap.get("currentPrice"), snap.get("numberOfAnalystOpinions") or 0
    if tgt is None or not price or n < 3:
        p.append(_pillar("Konsensus analityków", None, "za mało rekomendacji"))
    else:
        up = tgt / price - 1
        p.append(_pillar("Konsensus analityków", 1 if up > 0.15 else -1 if up < -0.05 else 0, f"cena docelowa {_pct(up)} od kursu ({n:.0f} analityków)"))

    p.append(_pillar("Trend kursu", None, "brak danych") if price_above_sma200 is None else
             _pillar("Trend kursu", 1 if price_above_sma200 else -1, "kurs powyżej średniej z 200 sesji" if price_above_sma200 else "kurs poniżej średniej z 200 sesji"))

    known = [x["score"] for x in p if x["score"] is not None]
    total = sum(known)
    if len(known) < 3:
        verdict, cls = "za mało danych do oceny", "unknown"
    elif total >= 3:
        verdict, cls = "mocny obraz: trzymać, można rozważyć dokupienie", "good"
    elif total <= -3:
        verdict, cls = "słaby obraz: rozważyć redukcję", "bad"
    else:
        verdict, cls = "obraz mieszany: trzymać i obserwować", "neutral"
    days = None
    if snap.get("earnings_date"):
        days = (date.fromisoformat(snap["earnings_date"]) - today).days
    return {"pillars": p, "total": total, "known": len(known), "verdict": verdict, "class": cls,
            "earnings_in_days": days, "report_soon": days is not None and 0 <= days <= REPORT_SOON_DAYS}


def save(conn: sqlite3.Connection, symbol: str, snap: dict) -> None:
    conn.execute(
        """INSERT INTO stock_fundamentals (symbol, data, updated) VALUES (?, ?, datetime('now'))
           ON CONFLICT(symbol) DO UPDATE SET data=excluded.data, updated=excluded.updated""",
        (symbol, json.dumps(snap, ensure_ascii=False)))
    conn.commit()


def read_all(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["symbol"]: {**json.loads(r["data"]), "updated": r["updated"]} for r in conn.execute("SELECT * FROM stock_fundamentals")}
