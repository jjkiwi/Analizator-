"""Kontrola jakosci swiec z cache: luki, swiece o zerowym zasiegu, skoki ceny, swiece rolowania."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

STEP = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4), "1d": pd.Timedelta(days=1)}
JUMP_ATR = 8.0
ATR_PERIOD = 14
# Tyle kolejnych dni roboczych bez swiecy uznajemy jeszcze za swieta (np. Boze Narodzenie + drugi dzien).
HOLIDAY_BDAYS = 2


@dataclass
class QualityReport:
    symbol: str
    interval: str
    bars: int = 0
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None
    gaps: list[tuple[pd.Timestamp, pd.Timestamp]] = field(default_factory=list)  # (ostatnia swieca przed, pierwsza po)
    zero_range: int = 0
    jumps: list[tuple[pd.Timestamp, float]] = field(default_factory=list)  # (czas, skok w ATR ze znakiem)
    roll_bars: int = 0  # swiece oznaczone jako rolowanie wg kalendarza wygasania (tylko znane kontrakty)
    jumps_on_roll: int = 0

    @property
    def longest_gap(self) -> pd.Timedelta | None:
        return max((b - a for a, b in self.gaps), default=None)


def _missing_bdays(prev: pd.DatetimeIndex, cur: pd.DatetimeIndex) -> np.ndarray:
    """Liczba dni roboczych (pon-pt) lezacych w calosci miedzy dwiema swiecami."""
    a = (prev.normalize() + pd.Timedelta(days=1)).tz_localize(None).to_numpy().astype("datetime64[D]")
    b = cur.normalize().tz_localize(None).to_numpy().astype("datetime64[D]")
    return np.busday_count(a, b)


def find_gaps(index: pd.DatetimeIndex, interval: str, always_open: bool = False) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Luki dluzsze niz oczekiwane. Weekendy, swieta i stale przerwy miedzy sesjami sa pomijane.

    - rynek calodobowy (krypto): kazda brakujaca swieca to luka,
    - 1d: luka = wiecej niz HOLIDAY_BDAYS dni roboczych bez swiecy,
    - 1h/4h: przerwa jest "oczekiwana", gdy jej dlugosc powtarza sie regularnie (przerwa dobowa, noc)
      albo gdy obejmuje weekend lub swieto (do HOLIDAY_BDAYS dni roboczych). Reszta to luki.
    """
    if len(index) < 2:
        return []
    step = STEP[interval]
    prev, cur = index[:-1], index[1:]
    diff = cur - prev
    if always_open:
        mask = diff > step
    else:
        missing = _missing_bdays(prev, cur)
        if interval == "1d":
            mask = missing > HOLIDAY_BDAYS
        else:
            counts = pd.Series(diff).value_counts()
            sessions = max(index.normalize().nunique(), 1)
            regular = set(counts[counts >= max(3, 0.05 * sessions)].index)
            crosses_day = cur.normalize() > prev.normalize()
            calendar_break = crosses_day & (diff >= pd.Timedelta(hours=12)) & (missing <= HOLIDAY_BDAYS)
            mask = (diff > step) & ~np.isin(diff, list(regular)) & ~calendar_break
            mask |= missing > HOLIDAY_BDAYS
    return [(prev[i], cur[i]) for i in np.flatnonzero(np.asarray(mask))]


def atr_prev(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """ATR (srednia prosta z TR) z poprzednich swiec: nie zawiera biezacej, wiec skok nie zawyza wlasnej miary."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period).mean().shift(1)


def find_jumps(df: pd.DataFrame, k: float = JUMP_ATR) -> list[tuple[pd.Timestamp, float]]:
    """Swiece, w ktorych luka otwarcia albo zmiana zamkniecia wobec poprzedniego zamkniecia przekracza k x ATR."""
    atr = atr_prev(df)
    prev_close = df["close"].shift(1)
    gap = (df["open"] - prev_close) / atr
    move = (df["close"] - prev_close) / atr
    size = gap.where(gap.abs() >= move.abs(), move)
    hit = size.abs() > k
    return [(t, float(size.loc[t])) for t in df.index[hit.fillna(False).to_numpy()]]


# ---------- rolowanie kontraktow ----------

def expiry_dates(source_symbol: str, sessions: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Ostatnie dni handlu kolejnych kontraktow wg regul gieldy, liczone na faktycznych dniach sesyjnych.

    Obslugiwane: CL=F (WTI: 3 dni robocze przed 25. dniem miesiaca poprzedzajacego dostawe) i
    NG=F (gaz: 3. dzien roboczy od konca miesiaca poprzedzajacego dostawe). Inne symbole: pusta lista.
    Dni wolne bierzemy z samych danych, wiec wynik moze roznic sie o 1 sesje od kalendarza gieldy.
    """
    days = pd.DatetimeIndex(sessions.normalize().unique()).sort_values()
    if source_symbol not in ("CL=F", "NG=F") or len(days) < 30:
        return []
    out = []
    for period in days.tz_localize(None).to_period("M").unique():
        d = days[(days.year == period.year) & (days.month == period.month)]
        if source_symbol == "NG=F":
            ref, pick = d, 3  # 3. sesja od konca miesiaca
        else:
            # 3 dni robocze przed 25. dniem; gdy 25. jest wolny, przed ostatnim dniem roboczym sprzed 25.
            ref, pick = d[d.day <= 25], 4
        if len(ref) >= pick:
            out.append(ref[-pick])
    # ostatni miesiac w danych moze byc niepelny: regula "od konca miesiaca" bylaby wtedy bledna
    last = days[-1]
    if out and (out[-1].year, out[-1].month) == (last.year, last.month):
        month_end = (last + pd.offsets.BMonthEnd(0)).normalize()
        if source_symbol == "NG=F" and last < month_end:
            out.pop()
        elif source_symbol == "CL=F" and last.day < 25:
            out.pop()
    return out


def roll_flags(df: pd.DataFrame, source_symbol: str) -> pd.Series:
    """True dla swiec pierwszej sesji po wygasnieciu kontraktu (seria ciagla przeskakuje tam na nowy kontrakt).

    Zmiana ceny na takiej swiecy zawiera roznice miedzy kontraktami, ktorej nie da sie zarobic ani stracic
    na CFD (broker koryguje ja punktami swapowymi przy rolowaniu). Sygnaly z tych swiec sa podejrzane.
    Dla symboli bez znanego kalendarza zwraca same False.
    """
    flags = pd.Series(False, index=df.index)
    expiries = expiry_dates(source_symbol, df.index)
    if not expiries:
        return flags
    days = pd.DatetimeIndex(df.index.normalize().unique()).sort_values()
    pos = days.searchsorted(pd.DatetimeIndex(expiries), side="right")
    roll_days = days[pos[pos < len(days)]]
    flags[:] = df.index.normalize().isin(roll_days)
    return flags


def quality_report(df: pd.DataFrame, symbol: str, interval: str, always_open: bool = False,
                   source_symbol: str | None = None) -> QualityReport:
    rep = QualityReport(symbol=symbol, interval=interval)
    if df is None or df.empty:
        return rep
    rep.bars, rep.start, rep.end = len(df), df.index[0], df.index[-1]
    rep.gaps = find_gaps(df.index, interval, always_open)
    rep.zero_range = int((df["high"] == df["low"]).sum())
    rep.jumps = find_jumps(df)
    if source_symbol:
        flags = roll_flags(df, source_symbol)
        rep.roll_bars = int(flags.sum())
        rep.jumps_on_roll = sum(1 for t, _ in rep.jumps if flags.loc[t])
    return rep


def format_reports(reports: list[QualityReport], markdown: bool = False) -> str:
    head = ["symbol", "swiec", "od", "do", "luki", "najdl. luka", "zero-zasieg", f"skoki>{JUMP_ATR:g}ATR", "najwiekszy skok"]
    rows = []
    for r in reports:
        if not r.bars:
            rows.append([r.symbol, "0", "-", "-", "-", "-", "-", "-", "brak danych w cache"])
            continue
        big = max(r.jumps, key=lambda j: abs(j[1]), default=None)
        gap = r.longest_gap
        rows.append([
            r.symbol, str(r.bars), str(r.start.date()), str(r.end.date()), str(len(r.gaps)),
            "-" if gap is None else (f"{gap.days} dni" if gap >= pd.Timedelta(days=2) else f"{gap / pd.Timedelta(hours=1):.0f} h"),
            str(r.zero_range), str(len(r.jumps)),
            "-" if big is None else f"{big[1]:+.1f} ATR {big[0].date()}",
        ])
    if markdown:
        lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rows])
    widths = [max(len(x[i]) for x in [head] + rows) for i in range(len(head))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(x, widths)) for x in [head] + rows)
