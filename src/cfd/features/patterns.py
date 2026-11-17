"""Formacje techniczne na zamknietych swiecach: punkty zwrotne, wsparcia/opory, trend, kanal,
podwojny szczyt/dno, trojkaty, konsolidacja i wybicie z niej.

Wszystkie funkcje patrza wylacznie na przekazany `df` (przekazuj go bez ostatniej, niedomknietej
swiecy). Punkt zwrotny jest potwierdzony dopiero po `right` swiecach, wiec wynik na df[:n] nigdy
nie zalezy od swiec n.. . Wyniki sa deterministyczne (bez losowosci).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from cfd.features.indicators import atr as _atr

OHLC = ["open", "high", "low", "close"]


@dataclass(frozen=True)
class _Swing:
    pos: int
    kind: str  # "high" | "low"
    price: float


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna(subset=OHLC)


def _fmt(p: float) -> str:
    """Cena w czytelnej precyzji zaleznej od rzedu wielkosci."""
    a = abs(p)
    if a >= 1000:
        return f"{p:,.0f}".replace(",", " ")
    if a >= 10:
        return f"{p:.2f}"
    if a >= 1:
        return f"{p:.3f}"
    return f"{p:.5f}"


def _atr_last(df: pd.DataFrame, period: int = 14) -> float:
    """Ostatnia wartosc ATR, z zapasem na krotkie serie."""
    if len(df) > period:
        v = float(_atr(df, period).iloc[-1])
        if np.isfinite(v) and v > 0:
            return v
    rng = (df["high"] - df["low"]).to_numpy(float)
    v = float(np.nanmean(rng)) if len(rng) else 0.0
    return v if np.isfinite(v) and v > 0 else max(abs(float(df["close"].iloc[-1])) * 0.01, 1e-9)


def _swings(df: pd.DataFrame, left: int, right: int) -> list[_Swing]:
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    n = len(h)
    out: list[_Swing] = []
    if n < left + right + 1:
        return out
    win = left + right + 1
    hw = np.lib.stride_tricks.sliding_window_view(h, win)
    lw = np.lib.stride_tricks.sliding_window_view(lo, win)
    for j in range(len(hw)):
        i = j + left
        # Szczyt: scisle wyzej niz swiece z lewej, nie nizej niz z prawej (pierwszy z rownych).
        if (hw[j, :left] < h[i]).all() and (hw[j, left + 1:] <= h[i]).all():
            out.append(_Swing(i, "high", float(h[i])))
        if (lw[j, :left] > lo[i]).all() and (lw[j, left + 1:] >= lo[i]).all():
            out.append(_Swing(i, "low", float(lo[i])))
    return out


def swing_points(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    """Lokalne szczyty i dolki potwierdzone po `right` swiecach.

    Zwraca DataFrame z indeksem czasu i kolumnami: pos (numer swiecy w df), kind ("high"/"low"),
    price. Swieca z ostatnich `right` pozycji nigdy nie jest punktem zwrotnym (brak potwierdzenia).
    """
    df = _clean(df)
    sw = _swings(df, left, right)
    idx = df.index[[s.pos for s in sw]] if sw else df.index[:0]
    return pd.DataFrame(
        {"pos": [s.pos for s in sw], "kind": [s.kind for s in sw], "price": [s.price for s in sw]},
        index=idx,
    )


def support_resistance(df: pd.DataFrame, lookback: int = 120, max_levels: int = 4,
                       left: int = 3, right: int = 3, tol_atr: float = 0.5,
                       max_dist_atr: float = 6.0) -> list[dict]:
    """Poziomy wsparcia i oporu z klastrow punktow zwrotnych z ostatnich `lookback` swiec.

    Tolerancja klastra to `tol_atr` * ATR. Sila poziomu to liczba dotkniec (punktow zwrotnych
    w klastrze). Zwracane sa tylko poziomy w odleglosci do `max_dist_atr` ATR od ostatniego
    zamkniecia, najwyzej `max_levels` (po rowno nad i pod cena, jesli sie da), malejaco po cenie.
    Element: {"price", "role" ("opór"/"wsparcie"), "touches", "last", "distance_atr"}.
    """
    df = _clean(df)
    if len(df) < left + right + 5 or max_levels <= 0:
        return []
    a = _atr_last(df)
    part = df.iloc[-lookback:]
    sw = _swings(part, left, right)
    if not sw:
        return []
    close = float(part["close"].iloc[-1])
    tol = tol_atr * a
    pts = sorted(sw, key=lambda s: (s.price, s.pos))
    clusters: list[list[_Swing]] = [[pts[0]]]
    for s in pts[1:]:
        cur = clusters[-1]
        if s.price - float(np.mean([c.price for c in cur])) <= tol:
            cur.append(s)
        else:
            clusters.append([s])
    cands = []
    for cl in clusters:
        price = float(np.mean([c.price for c in cl]))
        dist = abs(price - close) / a
        if dist > max_dist_atr:
            continue
        last_pos = max(c.pos for c in cl)
        cands.append({
            "price": price,
            "role": "opór" if price >= close else "wsparcie",
            "touches": len(cl),
            "last": part.index[last_pos],
            "distance_atr": round(dist, 2),
            "_score": len(cl) - 0.25 * dist + 0.002 * last_pos,
        })

    def pick(role: str, k: int) -> list[dict]:
        side = [c for c in cands if c["role"] == role]
        strong = [c for c in side if c["touches"] >= 2]
        pool = strong if strong else side
        return sorted(pool, key=lambda c: -c["_score"])[:k]

    half = max_levels // 2
    res, sup = pick("opór", max_levels), pick("wsparcie", max_levels)
    chosen = res[:half] + sup[:max_levels - half]
    rest = sorted([c for c in res[half:] + sup[max_levels - half:]], key=lambda c: -c["_score"])
    chosen += rest[: max_levels - len(chosen)]
    chosen = chosen[:max_levels]
    for c in chosen:
        c.pop("_score", None)
    return sorted(chosen, key=lambda c: -c["price"])


# --- formacje ---------------------------------------------------------------------------------


class _Ctx:
    """Tablice wspolne dla wykrywaczy (pozycje wzgledem wycinka df)."""

    def __init__(self, df: pd.DataFrame, left: int, right: int):
        self.idx = df.index
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.n = len(df)
        self.sw = _swings(df, left, right)

    def t(self, pos: int) -> pd.Timestamp:
        return self.idx[int(min(max(pos, 0), self.n - 1))]


def _line(ctx: _Ctx, p0: int, v0: float, p1: int, v1: float, role: str) -> dict:
    return {"t0": ctx.t(p0), "p0": float(v0), "t1": ctx.t(p1), "p1": float(v1), "role": role}


def _fit(points: list[_Swing]) -> tuple[float, float, float]:
    """Prosta przez punkty (nachylenie, wyraz wolny, maks. odchylenie)."""
    x = np.array([p.pos for p in points], float)
    y = np.array([p.price for p in points], float)
    if len(points) == 2:
        slope = (y[1] - y[0]) / (x[1] - x[0]) if x[1] != x[0] else 0.0
        icpt = y[0] - slope * x[0]
        return float(slope), float(icpt), 0.0
    slope, icpt = np.polyfit(x, y, 1)
    resid = np.abs(y - (slope * x + icpt))
    return float(slope), float(icpt), float(resid.max())


def _trend(ctx: _Ctx, a: float) -> dict | None:
    highs = [s for s in ctx.sw if s.kind == "high"]
    lows = [s for s in ctx.sw if s.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return None
    h1, h2 = highs[-2], highs[-1]
    l1, l2 = lows[-2], lows[-1]
    if h2.price > h1.price and l2.price > l1.price:
        d = 1
    elif h2.price < h1.price and l2.price < l1.price:
        d = -1
    else:
        return None
    last = ctx.n - 1
    close = ctx.c[-1]
    # Trend naruszony, gdy zamkniecie przebilo ostatni dolek (wzrostowy) lub szczyt (spadkowy).
    if (d == 1 and close < l2.price) or (d == -1 and close > h2.price):
        return None
    word = "wzrostowy" if d == 1 else "spadkowy"
    end_pos = max(h2.pos, l2.pos)
    # Kanal: regresja przez ostatnie punkty zwrotne, oba boki w strone trendu i mniej wiecej rownolegle.
    start = max(min(h1.pos, l1.pos) - 40, 0)
    hh = [s for s in highs if s.pos >= start][-4:]
    ll = [s for s in lows if s.pos >= start][-4:]
    if len(hh) >= 2 and len(ll) >= 2 and len(hh) + len(ll) >= 5:
        su, bu, ru = _fit(hh)
        sl, bl, rl = _fit(ll)
        parallel = abs(su - sl) <= 0.5 * max(abs(su), abs(sl))
        if np.sign(su) == d and np.sign(sl) == d and parallel and max(ru, rl) <= 0.8 * a:
            p0 = min(hh[0].pos, ll[0].pos)
            up_now, lo_now = su * last + bu, sl * last + bl
            if lo_now - 0.5 * a <= close <= up_now + 0.5 * a and up_now - lo_now > a:
                return {
                    "type": "channel", "label": f"Kanał {word}", "direction": d,
                    "start": ctx.t(p0), "end": ctx.t(last), "status": "potwierdzona",
                    "lines": [_line(ctx, p0, su * p0 + bu, last, up_now, "opór"),
                              _line(ctx, p0, sl * p0 + bl, last, lo_now, "wsparcie")],
                    "levels": [],
                    "note": f"Kanał {word}: górna krawędź {_fmt(up_now)}, dolna {_fmt(lo_now)}.",
                    "_end": end_pos, "_w": 1.2,
                }
    # Linia trendu przez dwa ostatnie dolki (wzrostowy) lub szczyty (spadkowy), przedluzona do konca.
    p, q = (l1, l2) if d == 1 else (h1, h2)
    slope = (q.price - p.price) / (q.pos - p.pos)
    now = q.price + slope * (last - q.pos)
    broken = (d == 1 and close < now) or (d == -1 and close > now)
    note = ("wyższe szczyty i dołki" if d == 1 else "niższe szczyty i dołki")
    note += f"; linia trendu teraz {_fmt(now)}"
    if broken:
        note += ", zamknięcie po drugiej stronie linii (osłabienie)"
    return {
        "type": "trend", "label": f"Trend {word}", "direction": d,
        "start": ctx.t(min(h1.pos, l1.pos)), "end": ctx.t(last), "status": "potwierdzona",
        "lines": [_line(ctx, p.pos, p.price, last, now, "linia trendu")],
        "levels": [], "note": note + ".", "_end": end_pos, "_w": 1.0,
    }


def _double(ctx: _Ctx, a: float, top: bool) -> dict | None:
    """Podwojny szczyt (top=True) lub dno. Dno liczone na odbitej serii (ceny * -1)."""
    s = 1.0 if top else -1.0
    H = ctx.h if top else -ctx.l
    L = ctx.l if top else -ctx.h
    C = s * ctx.c
    kind = "high" if top else "low"
    peaks = [sw for sw in ctx.sw if sw.kind == kind]
    last = ctx.n - 1
    tol = 0.6 * a
    for j in range(len(peaks) - 1, max(len(peaks) - 4, 0) - 1, -1):
        p2 = peaks[j]
        if last - p2.pos > 45:
            break
        for i in range(j - 1, -1, -1):
            p1 = peaks[i]
            gap = p2.pos - p1.pos
            if gap < 8:
                continue
            if gap > 60:
                break
            v1, v2 = s * p1.price, s * p2.price
            if abs(v1 - v2) > tol:
                continue
            topv = max(v1, v2)
            if H[max(0, p1.pos - 10):p2.pos + 1].max() > topv + 1e-12:
                continue  # szczyty musza byc najwyzszym miejscem okolicy
            mid = L[p1.pos + 1:p2.pos]
            if not len(mid):
                continue
            neck = float(mid.min())
            neck_pos = p1.pos + 1 + int(mid.argmin())
            if min(v1, v2) - neck < 2.0 * a:
                continue
            before = L[max(0, p1.pos - 30):p1.pos]
            if not len(before) or before.min() > neck + 0.5 * (topv - neck):
                continue  # brak ruchu prowadzacego do formacji
            post_h = H[p2.pos + 1:]
            if len(post_h) and post_h.max() > topv + tol:
                continue  # uniewazniona: cena wyszla ponad szczyty
            brk = None
            for k in range(p2.pos + 1, ctx.n):
                if C[k] < neck:
                    brk = k
                    break
            if brk is not None and last - brk > 20:
                continue
            target = neck - (topv - neck)
            neck_p, target_p, top_p = s * neck, s * target, s * topv
            status = "potwierdzona" if brk is not None else "w budowie"
            name = "Podwójny szczyt" if top else "Podwójne dno"
            side = "pod" if top else "nad"
            note = (f"Linia szyi {_fmt(neck_p)}, zasięg {_fmt(target_p)}; "
                    + (f"potwierdzona zamknięciem {side} szyją." if brk is not None
                       else f"potwierdzenie dopiero po zamknięciu {side} szyją."))
            return {
                "type": "double_top" if top else "double_bottom", "label": name,
                "direction": -1 if top else 1,
                "start": ctx.t(p1.pos), "end": ctx.t(brk if brk is not None else last),
                "status": status,
                "lines": [_line(ctx, p1.pos, p1.price, p2.pos, p2.price, "opór" if top else "wsparcie"),
                          _line(ctx, neck_pos, neck_p, last, neck_p, "szyja")],
                "levels": [{"price": float(neck_p), "role": "szyja"},
                           {"price": float(target_p), "role": "cel"},
                           {"price": float(top_p), "role": "unieważnienie"}],
                "note": note, "_end": brk if brk is not None else p2.pos,
                "_w": 3.0 if brk is not None else 2.0,
            }
    return None


def _triangle(ctx: _Ctx, a: float) -> dict | None:
    last = ctx.n - 1
    recent = [s for s in ctx.sw if s.pos >= last - 70]
    best = None
    # Probujemy formacje konczace sie na ostatnim punkcie zwrotnym i kilku wczesniejszych
    # (pozwala to wykryc trojkat, z ktorego cena juz wybila i zrobila nowy punkt zwrotny).
    for drop in range(0, 3):
        pts = recent[: len(recent) - drop] if drop else recent
        highs = [s for s in pts if s.kind == "high"][-3:]
        lows = [s for s in pts if s.kind == "low"][-3:]
        if len(highs) < 2 or len(lows) < 2:
            continue
        start = min(highs[0].pos, lows[0].pos)
        end = max(highs[-1].pos, lows[-1].pos)
        span = end - start
        if span < 8:
            continue
        su, bu, ru = _fit(highs)
        sl, bl, rl = _fit(lows)
        if max(ru, rl) > 0.6 * a:
            continue
        w0 = (su * start + bu) - (sl * start + bl)
        w1 = (su * end + bu) - (sl * end + bl)
        if w0 < 2.0 * a or w1 <= 0 or w1 > 0.75 * w0:
            continue
        flat = 0.6 * a / span
        up_flat, lo_flat = abs(su) <= flat, abs(sl) <= flat
        if up_flat and sl > flat:
            typ, label, d = "triangle_asc", "Trójkąt wznoszący", 1
        elif lo_flat and su < -flat:
            typ, label, d = "triangle_desc", "Trójkąt zniżający", -1
        elif su < -flat and sl > flat:
            typ, label, d = "triangle_sym", "Trójkąt zbieżny", 0
        else:
            continue
        xs = np.arange(start, end + 1)
        upper, lower = su * xs + bu, sl * xs + bl
        cc = ctx.c[start:end + 1]
        if (cc > upper + 0.5 * a).any() or (cc < lower - 0.5 * a).any():
            continue
        brk, bdir = None, 0
        for k in range(end + 1, ctx.n):
            if ctx.c[k] > su * k + bu:
                brk, bdir = k, 1
                break
            if ctx.c[k] < sl * k + bl:
                brk, bdir = k, -1
                break
        if brk is not None and last - brk > 15:
            continue
        if brk is None and (last - end > 20 or (su - sl) * last + (bu - bl) <= 0):
            continue
        stop = brk if brk is not None else last
        lines = [_line(ctx, start, su * start + bu, stop, su * stop + bu, "opór"),
                 _line(ctx, start, sl * start + bl, stop, sl * stop + bl, "wsparcie")]
        if brk is not None:
            status, d_out = "potwierdzona", bdir
            label_out = label + (" – wybicie górą" if bdir == 1 else " – wybicie dołem")
            note = f"Zamknięcie {'nad górną' if bdir == 1 else 'pod dolną'} linią formacji."
        else:
            status, d_out, label_out = "w budowie", d, label
            note = (f"Opór {_fmt(su * last + bu)}, wsparcie {_fmt(sl * last + bl)}; "
                    "czekaj na zamknięcie poza liniami.")
        best = {
            "type": typ, "label": label_out, "direction": int(d_out),
            "start": ctx.t(start), "end": ctx.t(stop), "status": status,
            "lines": lines, "levels": [], "note": note,
            "_end": brk if brk is not None else end, "_w": 3.0 if brk is not None else 2.0,
        }
        break
    return best


def _consolidation(ctx: _Ctx, a_ref: float, min_len: int = 12, k_atr: float = 3.0,
                   max_back: int = 10) -> dict | None:
    last = ctx.n - 1
    thr = k_atr * a_ref
    for k in range(0, max_back + 1):
        e = last - k
        if e < min_len:
            break
        hi, lo, s = ctx.h[e], ctx.l[e], e
        while s - 1 >= 0:
            nh, nl = max(hi, ctx.h[s - 1]), min(lo, ctx.l[s - 1])
            if nh - nl > thr:
                break
            hi, lo, s = nh, nl, s - 1
        if e - s + 1 < min_len:
            continue
        brk, bdir = None, 0
        for j in range(e + 1, ctx.n):
            if ctx.c[j] > hi:
                brk, bdir = j, 1
                break
            if ctx.c[j] < lo:
                brk, bdir = j, -1
                break
        if k > 0 and brk is None:
            # Zakres lekko poszerzony knotami, ale bez zamkniecia poza nim: nadal konsolidacja.
            hi, lo = max(hi, ctx.h[e + 1:].max()), min(lo, ctx.l[e + 1:].min())
        stop = brk if brk is not None else last
        lines = [_line(ctx, s, hi, stop, hi, "opór"), _line(ctx, s, lo, stop, lo, "wsparcie")]
        levels = [{"price": float(hi), "role": "opór"}, {"price": float(lo), "role": "wsparcie"}]
        n_bars = e - s + 1
        if brk is not None:
            word = "w górę" if bdir == 1 else "w dół"
            return {
                "type": "breakout", "label": f"Wybicie z konsolidacji {word}", "direction": bdir,
                "start": ctx.t(s), "end": ctx.t(brk), "status": "potwierdzona",
                "lines": lines, "levels": levels,
                "note": (f"Zakres {_fmt(lo)}–{_fmt(hi)} przez {n_bars} świec, "
                         f"zamknięcie {'nad' if bdir == 1 else 'pod'} zakresem."),
                "_end": brk, "_w": 3.0,
            }
        return {
            "type": "consolidation", "label": "Konsolidacja", "direction": 0,
            "start": ctx.t(s), "end": ctx.t(last), "status": "w budowie",
            "lines": lines, "levels": levels,
            "note": f"Wąski zakres {_fmt(lo)}–{_fmt(hi)} od {n_bars} świec; czekaj na zamknięcie poza nim.",
            "_end": last, "_w": 1.5,
        }
    return None


def detect_patterns(df: pd.DataFrame, lookback: int = 150, max_patterns: int = 3,
                    left: int = 3, right: int = 3) -> list[dict]:
    """Wykrywa formacje na zamknietych swiecach (ostatnie `lookback` swiec).

    Element listy: {"type", "label", "direction" (+1/-1/0), "start", "end",
    "status" ("w budowie"/"potwierdzona"), "lines": [{"t0","p0","t1","p1","role"}],
    "levels": [{"price","role"}], "note"}. Najwyzej `max_patterns`, najwazniejsze i najswiezsze
    pierwsze.
    """
    df = _clean(df)
    if len(df) < 30:
        return []
    a = _atr_last(df)
    atr_series = _atr(df, 14).iloc[-100:].dropna()
    a_ref = float(atr_series.median()) if len(atr_series) else a
    part = df.iloc[-lookback:]
    ctx = _Ctx(part, left, right)
    found = [
        _double(ctx, a, top=True),
        _double(ctx, a, top=False),
        _triangle(ctx, a),
        _consolidation(ctx, a_ref),
        _trend(ctx, a),
    ]
    found = [f for f in found if f is not None]
    tops = [f for f in found if f["type"] in ("double_top", "double_bottom")]
    if len(tops) == 2:  # sprzeczne formacje: zostaje swiezsza
        found.remove(min(tops, key=lambda f: (f["_end"], f["type"])))
    last = ctx.n - 1
    for f in found:
        f["_score"] = f["_w"] - (last - f["_end"]) / 40.0
    found.sort(key=lambda f: (-f["_score"], f["type"]))
    out = []
    for f in found[:max_patterns]:
        out.append({k: v for k, v in f.items() if not k.startswith("_")})
    return out


def patterns_json(patterns: list[dict]) -> list[dict]:
    """Formacje w postaci gotowej do JSON (czas jako ISO, ceny zaokraglone)."""
    def ts(t) -> str:
        return pd.Timestamp(t).isoformat()

    def px(p: float) -> float:
        return float(f"{p:.6g}")

    out = []
    for p in patterns:
        out.append({
            "type": p["type"], "label": p["label"], "direction": int(p["direction"]),
            "status": p["status"], "start": ts(p["start"]), "end": ts(p["end"]), "note": p["note"],
            "lines": [{"t0": ts(ln["t0"]), "p0": px(ln["p0"]), "t1": ts(ln["t1"]), "p1": px(ln["p1"]),
                       "role": ln["role"]} for ln in p.get("lines", [])],
            "levels": [{"price": px(lv["price"]), "role": lv["role"]} for lv in p.get("levels", [])],
        })
    return out


def levels_json(levels: list[dict]) -> list[dict]:
    """Poziomy wsparcia/oporu do JSON."""
    return [{"price": float(f"{lv['price']:.6g}"), "role": lv["role"], "touches": int(lv.get("touches", 0)),
             "last": pd.Timestamp(lv["last"]).isoformat() if lv.get("last") is not None else None,
             "distance_atr": float(lv.get("distance_atr", 0.0))} for lv in levels]
