from __future__ import annotations

import re
from pathlib import Path

import yaml


def _pattern(words: list[str]) -> re.Pattern:
    alts = sorted((re.escape(w.lower()) for w in words), key=len, reverse=True)
    # (?<!\w) / (?!\w) zamiast \b, zeby dzialaly frazy konczace sie znakiem, np. "opec+".
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)", re.IGNORECASE)


class KeywordMapper:
    """Przypisuje tekst do symboli XTB: wprost (slowa instrumentu) i posrednio (tematy makro)."""

    def __init__(self, config: dict, known_symbols: set[str] | None = None):
        keep = (lambda s: known_symbols is None or s in known_symbols)
        self.direct = {s: _pattern(w) for s, w in config.get("instruments", {}).items() if w and keep(s)}
        self.topics = {
            name: (_pattern(t["keywords"]), [s for s in t["symbols"] if keep(s)])
            for name, t in config.get("topics", {}).items()
        }
        self.high_impact = _pattern(config.get("high_impact") or ["\x00"])

    @classmethod
    def from_file(cls, path: Path | str = "config/keywords.yaml", known_symbols: set[str] | None = None):
        return cls(yaml.safe_load(Path(path).read_text(encoding="utf-8")), known_symbols)

    def match(self, text: str) -> dict:
        direct = [s for s, pat in self.direct.items() if pat.search(text)]
        topics = [name for name, (pat, _) in self.topics.items() if pat.search(text)]
        symbols = list(direct)
        for name in topics:
            symbols += [s for s in self.topics[name][1] if s not in symbols]
        return {
            "symbols": symbols,
            "direct": direct,
            "topics": topics,
            "high_impact": bool(self.high_impact.search(text)),
        }
