"""Fuzja: sygnal techniczny + bias fundamentalny + swieze newsy = jedna ocena zgodnosci."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Confluence:
    score: float  # od -1 (wszystko przeciw) do 3 (wszystko za)
    label: str  # mocny | neutralny | pod prad
    text: str


def confluence(side: int, bias: float | None, news_dir: int = 0) -> Confluence:
    fund = 0.0 if bias is None else max(-1.0, min(1.0, side * bias / 2))
    news = float(side * news_dir)
    score = round(1.0 + fund + news, 2)
    label = "mocny" if score >= 2 else "neutralny" if score >= 1 else "pod prad"
    parts = []
    if bias is None:
        parts.append("fundamenty: brak danych")
    else:
        rel = "zgodne" if fund > 0.15 else "przeciwne" if fund < -0.15 else "neutralne"
        parts.append(f"fundamenty {rel} (bias {bias:+.1f})")
    parts.append("newsy zgodne" if news > 0 else "newsy przeciwne" if news < 0 else "newsy neutralne")
    return Confluence(score, label, ", ".join(parts))
