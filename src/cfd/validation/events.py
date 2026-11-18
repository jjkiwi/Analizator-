"""Hipotezy H13 (dzien decyzji FOMC) i H14 (dzien przed swietem gieldowym w USA)."""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

from cfd.validation.calendar_vol import SHARE, t_stat

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9

_HIST = re.compile(r"^(\w+) (\d+)(?:-(?:(\w+) )?(\d+))? Meeting - (\d{4})$")
UNSCHEDULED_CLOSURES = (date(2001, 9, 11), date(2001, 9, 12), date(2001, 9, 13), date(2001, 9, 14),
                        date(2012, 10, 29), date(2012, 10, 30))


def parse_historical(html: str) -> list[date]:
    """Dni decyzji planowych posiedzen ze strony fomchistoricalYYYY.htm (bez telekonferencji i nadzwyczajnych)."""
    out = []
    for h in re.findall(r"<h5[^>]*>([^<]*)", html):
        m = _HIST.match(" ".join(h.split()))
        if not m:
            continue
        mon1, d1, mon2, d2, y = m.groups()
        mon = MONTHS[(mon2 or mon1).lower()]
        out.append(date(int(y), mon, int(d2 or d1)))
    return out


def parse_current(html: str, today: date) -> list[date]:
    """Dni decyzji ze strony fomccalendars.htm (lata biezace), tylko przeszle."""
    out = []
    for year, body in re.findall(r'(\d{4}) FOMC Meetings</a>(.*?)(?=\d{4} FOMC Meetings</a>|$)', html, re.S):
        months = re.findall(r'fomc-meeting__month[^>]*><strong>([^<]*)', body)
        days = re.findall(r'fomc-meeting__date[^>]*>([^<]*)', body)
        for mo, dd in zip(months, days):
            if "notation" in dd.lower() or "unscheduled" in dd.lower():
                continue
            mon = MONTHS[mo.split("/")[-1].strip().lower()]
            d = date(int(year), mon, int(dd.replace("*", "").split("-")[-1].split()[0]))
            if d < today:
                out.append(d)
    return out


def holidays_from_index(idx: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Ostatnie sesje przed dniem roboczym bez notowan (swieta), bez zamkniec nieplanowanych."""
    idx = pd.DatetimeIndex(idx).normalize()
    bdays = pd.bdate_range(idx[0], idx[-1])
    missing = bdays.difference(idx)
    skip = {pd.Timestamp(d) for d in UNSCHEDULED_CLOSURES}
    pre = set()
    for d in missing:
        if d in skip:
            continue
        before = idx[idx < d]
        if len(before):
            pre.add(before[-1])
    return sorted(pre)


def event_report(close: pd.Series, days, min_ret: float = 0.001) -> dict:
    """Stopa zamkniecie->zamkniecie w dniach zdarzen wobec sredniej wszystkich dni; podzial 60/40."""
    r = close.pct_change().dropna()
    ev = r[r.index.isin(pd.DatetimeIndex(days))]
    cut = int(len(ev) * SHARE)
    out = {"n": len(ev)}
    for name, part in (("discovery", ev.iloc[:cut]), ("confirmation", ev.iloc[cut:])):
        lo, hi = part.index.min(), part.index.max()
        base = r[(r.index >= lo) & (r.index <= hi)].mean()
        ex = part - base
        out[name] = {"n": len(part), "od": str(lo.date()), "do": str(hi.date()),
                     "mean_ret": float(part.mean()), "base": float(base),
                     "excess": float(ex.mean()), "t": t_stat(ex), "hit": float((part > 0).mean())}
    d, c = out["discovery"], out["confirmation"]
    out["pass"] = bool(d["excess"] > 0 and d["t"] >= 2 and c["excess"] > 0 and c["t"] >= 1.65
                       and c["mean_ret"] > min_ret)
    return out
