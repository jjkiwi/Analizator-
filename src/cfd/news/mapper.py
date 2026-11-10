from __future__ import annotations

import re
from pathlib import Path

import yaml

CS_PREFIX = "cs:"


def _pattern(words: list[str]) -> re.Pattern:
    """Jedno wyrazenie dla listy slow. Wpis "cs:Fed" jest dopasowywany z rozroznieniem wielkosci liter.

    Skroty (Fed, ETH, BoJ, LNG, CPI) sa wieloznaczne jako zwykle slowa ("fed up", "boj"), dlatego
    mozna wymusic dokladna pisownie. Pozostale wpisy ignoruja wielkosc liter.
    """
    alts = []
    for w in sorted(words, key=len, reverse=True):
        if w.startswith(CS_PREFIX):
            alts.append(re.escape(w[len(CS_PREFIX):]))
        else:
            alts.append("(?i:" + re.escape(w.lower()) + ")")
    # (?<!\w) / (?!\w) zamiast \b, zeby dzialaly frazy konczace sie znakiem, np. "opec+".
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)")


_NEVER = ["\x00"]


class KeywordMapper:
    """Przypisuje tekst do symboli XTB: wprost (slowa instrumentu) i posrednio (tematy makro).

    `exclude` (symbol -> frazy) uniewaznia dopasowanie wprost, gdy w tekscie jest fraza z innego
    znaczenia (np. "gold medal", detaliczne "gold rate today"). Frazy wysokiej wagi sa szukane tylko
    w tytule; `high_impact_moves` (surge, plunge...) licza sie wylacznie razem z dopasowaniem wprost,
    bo same w sobie opisuja ruch czegokolwiek.
    """

    def __init__(self, config: dict, known_symbols: set[str] | None = None):
        keep = (lambda s: known_symbols is None or s in known_symbols)
        self.direct = {s: _pattern(w) for s, w in config.get("instruments", {}).items() if w and keep(s)}
        self.exclude = {s: _pattern(w) for s, w in (config.get("exclude") or {}).items() if w}
        self.topics = {
            name: (_pattern(t["keywords"]), [s for s in t["symbols"] if keep(s)])
            for name, t in config.get("topics", {}).items()
        }
        self.high_impact = _pattern(config.get("high_impact") or _NEVER)
        self.high_impact_moves = _pattern(config.get("high_impact_moves") or _NEVER)

    @classmethod
    def from_file(cls, path: Path | str = "config/keywords.yaml", known_symbols: set[str] | None = None):
        return cls(yaml.safe_load(Path(path).read_text(encoding="utf-8")), known_symbols)

    def match(self, text: str, title: str | None = None) -> dict:
        """Dopasowuje tekst (tytul + opis). `title` zaweza szukanie fraz wysokiej wagi do samego tytulu."""
        head = text if title is None else title
        direct = [
            s for s, pat in self.direct.items()
            if pat.search(text) and not (s in self.exclude and self.exclude[s].search(text))
        ]
        topics = [name for name, (pat, _) in self.topics.items() if pat.search(text)]
        symbols = list(direct)
        for name in topics:
            symbols += [s for s in self.topics[name][1] if s not in symbols]
        hits = sorted({m.group(0).lower() for m in self.high_impact.finditer(head)})
        if direct:
            hits += sorted({m.group(0).lower() for m in self.high_impact_moves.finditer(head)} - set(hits))
        return {
            "symbols": symbols,
            "direct": direct,
            "topics": topics,
            "high_impact": bool(hits),
            "high_impact_hits": hits,
        }
