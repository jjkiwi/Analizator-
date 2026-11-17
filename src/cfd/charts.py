"""Samodzielne wykresy SVG (bez bibliotek i bez JS) do ekranu „stan na teraz”.

Kolory ida przez zmienne CSS strony (--up, --down, --mut, --line, --accent) z wartosciami
zapasowymi, wiec wykres pasuje do jasnego i ciemnego motywu.
"""

from __future__ import annotations

import html
import math

import pandas as pd

from cfd.features.patterns import (
    _fmt,
    detect_patterns,
    levels_json,
    patterns_json,
    support_resistance,
)

_STYLE = (
    ".cs-u{fill:var(--up,#16a34a);stroke:var(--up,#16a34a)}"
    ".cs-d{fill:var(--down,#dc2626);stroke:var(--down,#dc2626)}"
    ".cs-g{stroke:var(--line,#8884);stroke-width:1}"
    ".cs-t{fill:var(--mut,#888);font:10px system-ui,sans-serif}"
    ".cs-h{fill:var(--mut,#888);font:600 11px system-ui,sans-serif}"
    ".cs-lv{stroke-width:1;stroke-dasharray:4 3;opacity:.55}"
    ".cs-ld{stroke:var(--down,#dc2626)}.cs-lu{stroke:var(--up,#16a34a)}"
    ".cs-p{fill:none;stroke-width:1.6}"
    ".cs-p0{stroke:var(--accent,#4f8cff)}.cs-p1{stroke:var(--up,#16a34a)}.cs-p-1{stroke:var(--down,#dc2626)}"
    ".cs-f0{fill:var(--accent,#4f8cff)}.cs-f1{fill:var(--up,#16a34a)}.cs-f-1{fill:var(--down,#dc2626)}"
    ".cs-sz{stroke-dasharray:6 3}"
)


def _nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    first = math.ceil(lo / step) * step
    out, v = [], first
    while v <= hi + 1e-9 * span:
        out.append(v)
        v += step
    return out


def _r(v: float) -> str:
    """Wspolrzedna z jednym miejscem po przecinku, bez zbednych zer."""
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def _date_label(t: pd.Timestamp, intraday: bool) -> str:
    return t.strftime("%d.%m %H:%M") if intraday else t.strftime("%d.%m.%y")


def candle_svg(df: pd.DataFrame, patterns: list[dict] | None = None, levels: list[dict] | None = None,
               title: str = "", width: int = 640, height: int = 260, bars: int = 90) -> str:
    """Wykres swiecowy jako inline SVG z poziomami (przerywane) i liniami formacji."""
    data = df.dropna(subset=["open", "high", "low", "close"])
    view = data.iloc[-bars:] if bars else data
    n = len(view)
    w, h = int(width), int(height)
    esc = html.escape
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" '
            f'preserveAspectRatio="xMidYMid meet" role="img" aria-label="{esc(title or "wykres")}" '
            f'class="cs-chart"><style>{_STYLE}</style>')
    if n == 0:
        return head + f'<text class="cs-t" x="8" y="{h // 2}">brak danych</text></svg>'

    patterns = patterns or []
    levels = levels or []
    ml, mr, mt, mb = 6, 66, 30 if patterns else 20, 18
    pw, ph = w - ml - mr, h - mt - mb
    o = view["open"].to_numpy(float)
    hi = view["high"].to_numpy(float)
    lo = view["low"].to_numpy(float)
    c = view["close"].to_numpy(float)
    pmin, pmax = float(lo.min()), float(hi.max())
    span0 = max(pmax - pmin, abs(pmax) * 1e-4, 1e-9)
    # Poziomy i linie blisko widocznego zakresu poszerzaja skale (najwyzej o 25% zakresu).
    extra = [lv["price"] for lv in levels]
    for p in patterns:
        extra += [lv["price"] for lv in p.get("levels", []) if lv.get("role") != "cel"]
    for x in extra:
        if pmin - 0.25 * span0 <= x <= pmax + 0.25 * span0:
            pmin, pmax = min(pmin, x), max(pmax, x)
    pad = (pmax - pmin) * 0.04 or span0 * 0.04
    pmin, pmax = pmin - pad, pmax + pad

    def y(p: float) -> float:
        return mt + (pmax - p) / (pmax - pmin) * ph

    step = pw / n
    bw = max(step * 0.65, 1.0)

    def xc(i: float) -> float:
        return ml + (i + 0.5) * step

    full_pos = {t: i for i, t in enumerate(data.index)}
    off = len(data) - n

    def pos_of(t) -> float | None:
        t = pd.Timestamp(t)
        if t in full_pos:
            return float(full_pos[t] - off)
        k = int(data.index.searchsorted(t))
        if k >= len(data):
            return float(len(data) - 1 - off)
        return float(k - off)

    parts = [head]
    if title:
        parts.append(f'<text class="cs-h" x="{ml + 2}" y="13">{esc(title)}</text>')
    # poziomy wsparcia/oporu: linia przez wykres, etykieta w prawym marginesie (kolor = rola)
    lv_parts, lv_y = [], []
    for lv in sorted(levels, key=lambda v: -int(v.get("touches", 0) or 0)):
        p = float(lv["price"])
        if not (pmin <= p <= pmax):
            continue
        yy = y(p)
        k = "d" if lv.get("role") == "opór" else "u"
        lv_parts.append(f'<line class="cs-lv cs-l{k}" x1="{ml}" x2="{ml + pw}" y1="{_r(yy)}" y2="{_r(yy)}"/>')
        if all(abs(u - yy) >= 11 for u in lv_y):
            lv_y.append(yy)
            touches = lv.get("touches")
            txt = _fmt(p) + (f" ×{touches}" if touches and touches > 1 else "")
            role = esc(str(lv.get("role", "")))
            lv_parts.append(f'<text class="cs-t cs-f{"-1" if k == "d" else "1"}" x="{ml + pw + 3}" '
                            f'y="{_r(yy + 3.5)}"><title>{role}</title>{esc(txt)}</text>')
    # siatka i os cen (etykiety, ktore nie koliduja z poziomami)
    for tv in _nice_ticks(pmin, pmax, 4):
        yy = y(tv)
        parts.append(f'<line class="cs-g" x1="{ml}" x2="{ml + pw}" y1="{_r(yy)}" y2="{_r(yy)}"/>')
        if all(abs(u - yy) >= 11 for u in lv_y) and mt + 4 <= yy <= mt + ph:
            parts.append(f'<text class="cs-t" x="{ml + pw + 3}" y="{_r(yy + 3.5)}">{esc(_fmt(tv))}</text>')
    # daty
    intraday = n > 1 and (view.index[-1] - view.index[0]) / max(n - 1, 1) < pd.Timedelta(hours=20)
    for i in sorted({0, n // 3, 2 * n // 3, n - 1}):
        anchor = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        parts.append(f'<text class="cs-t" x="{_r(xc(i))}" y="{h - 4}" text-anchor="{anchor}">'
                     f'{esc(_date_label(view.index[i], intraday))}</text>')
    # swiece: jedna sciezka dla wzrostowych i jedna dla spadkowych
    up_d, dn_d = [], []
    for i in range(n):
        x = xc(i)
        top, bot = y(max(o[i], c[i])), y(min(o[i], c[i]))
        bh = max(bot - top, 0.8)
        seg = (f"M{_r(x)} {_r(y(hi[i]))}V{_r(y(lo[i]))}"
               f"M{_r(x - bw / 2)} {_r(top)}h{_r(bw)}v{_r(bh)}h{_r(-bw)}z")
        (up_d if c[i] >= o[i] else dn_d).append(seg)
    parts.append(f'<g class="cs-candles" data-n="{n}" stroke-width="1">')
    if up_d:
        parts.append(f'<path class="cs-u" d="{"".join(up_d)}"/>')
    if dn_d:
        parts.append(f'<path class="cs-d" d="{"".join(dn_d)}"/>')
    parts.append("</g>")
    parts += lv_parts
    # formacje
    legend = []
    for p in patterns:
        d = int(p.get("direction", 0))
        cls = f"cs-p cs-p{d}"
        drawn = False
        for ln in p.get("lines", []):
            a0, a1 = pos_of(ln["t0"]), pos_of(ln["t1"])
            if a0 is None or a1 is None or a1 < 0:
                continue
            v0, v1 = float(ln["p0"]), float(ln["p1"])
            if a0 < 0:  # przyciecie do lewej krawedzi okna
                v0 = v0 + (v1 - v0) * (0 - a0) / (a1 - a0) if a1 != a0 else v1
                a0 = 0.0
            extra_cls = " cs-sz" if ln.get("role") == "szyja" else ""
            parts.append(f'<line class="{cls}{extra_cls}" x1="{_r(xc(a0))}" y1="{_r(y(v0))}" '
                         f'x2="{_r(xc(a1))}" y2="{_r(y(v1))}"/>')
            drawn = True
        for lv in p.get("levels", []):
            pr = float(lv["price"])
            if lv.get("role") == "cel" and pmin <= pr <= pmax:
                parts.append(f'<line class="{cls} cs-sz" x1="{_r(ml + pw - 30)}" x2="{ml + pw}" '
                             f'y1="{_r(y(pr))}" y2="{_r(y(pr))}" opacity=".7"/>'
                             f'<text class="cs-t cs-f{d}" x="{_r(ml + pw - 32)}" y="{_r(y(pr) + 3.5)}" '
                             f'text-anchor="end">cel</text>')
        mark = "▲" if d > 0 else ("▼" if d < 0 else "◆")
        legend.append((d, f"{mark} {p.get('label', '')}" + (" (w budowie)" if p.get("status") == "w budowie" else ""),
                       drawn))
    if legend:
        x = ml + 2
        for d, txt, _ in legend:
            parts.append(f'<text class="cs-t cs-f{d}" x="{_r(x)}" y="26">{esc(txt)}</text>')
            x += 6.2 * len(txt) + 14
    parts.append("</svg>")
    return "".join(parts)


def chart_panel(inst, df_closed: pd.DataFrame, interval: str, bars: int = 90,
                width: int = 640, height: int = 260) -> dict:
    """Panel wykresu dla dashboardu: SVG + formacje i poziomy w postaci JSON.

    `inst` to Instrument albo sam symbol. `df_closed` musi byc bez ostatniej, niedomknietej swiecy.
    """
    symbol = getattr(inst, "symbol", inst)
    pats = detect_patterns(df_closed)
    levels = support_resistance(df_closed)
    svg = candle_svg(df_closed, pats, levels, title=f"{symbol} · {interval}",
                     width=width, height=height, bars=bars)
    return {"symbol": str(symbol), "interval": interval, "svg": svg,
            "patterns": patterns_json(pats), "levels": levels_json(levels)}


__all__ = ["candle_svg", "chart_panel"]
