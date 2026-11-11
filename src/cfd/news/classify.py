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


# Zapowiedzi, prognozy i komentarze: fraza wysokiej wagi ("CPI", "rate hike") pada w nich bez nowego zdarzenia.
_SOFT = re.compile(
    r"\b(ahead|tests?|next|focus|market today|markets today|markets wrap|recap|await(?:s|ing)?|looms?|loom(?:ing)?|brac(?:e|es|ed|ing)|eyes?|eyed|forecasts?|outlook|"
    r"preview|what to expect|predictions?|analysis|could|might|expected to|explained|live updates?|week ahead|"
    r"here(?:'|’)s what|opinion|odds|bets?|przed|prognoz\w*|zapowied\w*|komentarz\w*)\b|\?",
    re.I,
)


class RuleClassifier:
    """Darmowy klasyfikator bez sieci.

    Wage ocenia zgrubnie: 3 = fraza wysokiej wagi w tytule, o ile tytul nie jest zapowiedzia, prognoza
    ani pytaniem (te dostaja 2). Kierunek podaje tylko wtedy, gdy news mowi wprost o ruchu ceny
    instrumentu ("gold surges"), bo znaczenia zdarzen (np. "Fed tnie stopy") reguly nie rozumieja.
    """

    name = "rules"

    def classify(self, item: NewsItem, match: dict) -> Classification:
        importance = 3 if match["high_impact"] else 2 if match["direct"] else 1
        reason = "fraza wysokiej wagi" if match["high_impact"] else "dotyczy instrumentu wprost" if match["direct"] else "temat makro"
        if importance == 3 and _SOFT.search(item.title):
            importance, reason = 2, "fraza wysokiej wagi, ale zapowiedz/prognoza/komentarz"
        up, down = bool(_UP.search(item.title)), bool(_DOWN.search(item.title))
        d = 1 if up and not down else -1 if down and not up else 0
        directions = {s: (d if s in match["direct"] else 0) for s in match["symbols"]}
        return Classification(importance, directions, reason, self.name)


_PROMPT = """Jestes analitykiem rynkow finansowych. Ocen naglowek pod katem krotkoterminowego wplywu na wskazane instrumenty CFD.

Naglowek (moze byc w dowolnym jezyku): {title}
Opis: {summary}
Zrodlo: {source}
Instrumenty: {symbols}

importance: 3 = nowe, nieoczekiwane zdarzenie mogace ruszyc cena w ciagu godzin; 2 = istotne tlo; 1 = szum, komentarz, zapowiedz, podsumowanie znanych faktow.
directions: dla kazdego podanego symbolu "up" (wzrostowo), "down" (spadkowo) albo "none" (niejasne lub brak wplywu). Uzyj dokladnie podanych symboli. Gdy masz watpliwosci, dawaj "none".
reason: jedno zdanie po polsku."""

# Structured outputs (output_config.format): odpowiedz jest gwarantowanym JSON-em zgodnym ze schematem.
def parse_llm_json(text: str, symbols: list[str], classifier: str = "llm") -> Classification:
    """Wyciaga obiekt JSON z odpowiedzi modelu (modele czesto dodaja tekst lub ```json wokol)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("brak obiektu JSON w odpowiedzi")
    data = json.loads(text[start : end + 1])
    importance = min(3, max(1, int(data["importance"])))
    raw = data.get("directions") or {}
    directions = {s: max(-1, min(1, int(raw.get(s, 0)))) for s in symbols}
    return Classification(importance, directions, str(data.get("reason", ""))[:300], classifier)


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    model: str
    key_env: str


class ChainClassifier:
    """Lancuch dostawcow zgodnych z API OpenAI. Pierwsza poprawna odpowiedz wygrywa, na koncu reguly.

    Dostawca, ktory zawiodl, jest pomijany przez `cooldown` sekund, zeby nie tracic czasu
    na endpoint z wyczerpanym limitem przy kazdym newsie.
    """

    name = "chain"

    def __init__(self, providers: list[Provider], timeout: float = 20.0, fallback=None, cooldown: float = 600.0, post=None):
        self.providers = [p for p in providers if os.environ.get(p.key_env)]
        self.timeout, self.cooldown = timeout, cooldown
        self.fallback = fallback or RuleClassifier()
        self._blocked_until: dict[str, float] = {}
        self._post = post or self._http_post

    @classmethod
    def from_file(cls, path="config/llm.yaml", **kw):
        import yaml
        from pathlib import Path

        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls([Provider(**p) for p in raw.get("providers", [])], timeout=raw.get("timeout_seconds", 20.0), **kw)

    def _http_post(self, provider: Provider, prompt: str) -> str:
        resp = httpx.post(
            provider.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {os.environ[provider.key_env]}", "Content-Type": "application/json"},
            json={"model": provider.model, "temperature": 0, "max_tokens": 300,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""

    def classify(self, item: NewsItem, match: dict) -> Classification:
        import time

        prompt = _PROMPT.format(title=item.title, summary=item.summary[:500] or "-", source=item.source, symbols=", ".join(match["symbols"]))
        now = time.monotonic()
        for p in self.providers:
            if self._blocked_until.get(p.name, 0) > now:
                continue
            try:
                return parse_llm_json(self._post(p, prompt), match["symbols"], f"llm:{p.name}")
            except Exception as exc:  # limit, awaria, zly JSON: probujemy nastepnego
                log.warning("dostawca %s zawiodl (%s)", p.name, type(exc).__name__)
                self._blocked_until[p.name] = now + self.cooldown
        return self.fallback.classify(item, match)


class LLMClassifier:
    """Klasyfikacja przez API Anthropic (opcja platna). Wymaga ANTHROPIC_API_KEY; przy bledzie wraca do regul."""

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
        return parse_llm_json(text, symbols, "llm")

    def classify(self, item: NewsItem, match: dict) -> Classification:
        if not self.api_key:
            return self.fallback.classify(item, match)
        prompt = _PROMPT.format(title=item.title, summary=item.summary[:500] or "-", source=item.source, symbols=", ".join(match["symbols"]))
        try:
            return self.parse(self._call(prompt), match["symbols"])
        except Exception as exc:  # siec, limit, zly JSON: alert wazniejszy niz idealna ocena
            log.warning("LLM nie odpowiedzial poprawnie (%s), uzywam regul", exc)
            return self.fallback.classify(item, match)
