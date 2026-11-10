from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

import httpx

from .models import NewsItem

log = logging.getLogger(__name__)


@dataclass
class Classification:
    importance: int  # 1 tlo, 2 istotne, 3 pilne
    directions: dict[str, int] = field(default_factory=dict)  # symbol -> -1 | 0 | +1
    reason: str = ""
    classifier: str = "rules"


_UP = re.compile(r"\b(surge[sd]?|soar[sed]*|jump[sed]*|rall(?:y|ies|ied)|climb[sed]*|gain[sed]*|record high|rośnie|rosną|drożeje|rekord)\b", re.I)
_DOWN = re.compile(r"\b(plunge[sd]?|tumble[sd]?|slump[sed]*|sink[s]?|sank|drop[sped]*|fall[s]?|fell|slide[sd]?|crash(?:es|ed)?|record low|spada|spadają|tanieje|traci)\b", re.I)


class RuleClassifier:
    """Darmowy klasyfikator bez sieci.

    Wage ocenia przyzwoicie. Kierunek podaje tylko wtedy, gdy news mowi wprost o ruchu ceny
    instrumentu ("gold surges"), bo znaczenia zdarzen (np. "Fed tnie stopy") reguly nie rozumieja.
    """

    name = "rules"

    def classify(self, item: NewsItem, match: dict) -> Classification:
        importance = 3 if match["high_impact"] else 2 if match["direct"] else 1
        up, down = bool(_UP.search(item.title)), bool(_DOWN.search(item.title))
        d = 1 if up and not down else -1 if down and not up else 0
        directions = {s: (d if s in match["direct"] else 0) for s in match["symbols"]}
        reason = "fraza wysokiej wagi" if match["high_impact"] else "dotyczy instrumentu wprost" if match["direct"] else "temat makro"
        return Classification(importance, directions, reason, self.name)


_PROMPT = """Jestes analitykiem rynkow finansowych. Ocen naglowek pod katem krotkoterminowego wplywu na wskazane instrumenty CFD.

Naglowek: {title}
Opis: {summary}
Zrodlo: {source}
Instrumenty: {symbols}

Odpowiedz WYLACZNIE obiektem JSON, bez zadnego innego tekstu:
{{"importance": 1|2|3, "directions": {{"SYMBOL": -1|0|1}}, "reason": "jedno zdanie po polsku"}}

importance: 3 = nowe, nieoczekiwane zdarzenie mogace ruszyc cena w ciagu godzin; 2 = istotne tlo; 1 = szum, komentarz, podsumowanie znanych faktow.
directions: +1 wzrostowo, -1 spadkowo, 0 niejasne lub brak wplywu. Uzyj dokladnie podanych symboli. Gdy masz watpliwosci, dawaj 0."""


class LLMClassifier:
    """Klasyfikacja przez API Anthropic. Wymaga ANTHROPIC_API_KEY; przy bledzie wraca do regul."""

    name = "llm"
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 30.0, fallback=None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("CFD_LLM_MODEL", "claude-haiku-5-5")
        self.timeout = timeout
        self.fallback = fallback or RuleClassifier()

    def _call(self, prompt: str) -> str:
        resp = httpx.post(
            self.URL,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": self.model, "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return "".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text")

    @staticmethod
    def parse(text: str, symbols: list[str]) -> Classification:
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start : end + 1])
        importance = min(3, max(1, int(data["importance"])))
        raw = data.get("directions") or {}
        directions = {s: max(-1, min(1, int(raw.get(s, 0)))) for s in symbols}
        return Classification(importance, directions, str(data.get("reason", ""))[:300], "llm")

    def classify(self, item: NewsItem, match: dict) -> Classification:
        if not self.api_key:
            return self.fallback.classify(item, match)
        prompt = _PROMPT.format(title=item.title, summary=item.summary[:500] or "-", source=item.source, symbols=", ".join(match["symbols"]))
        try:
            return self.parse(self._call(prompt), match["symbols"])
        except Exception as exc:  # siec, limit, zly JSON: alert wazniejszy niz idealna ocena
            log.warning("LLM nie odpowiedzial poprawnie (%s), uzywam regul", exc)
            return self.fallback.classify(item, match)
