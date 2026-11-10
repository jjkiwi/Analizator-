from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

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
    r"\b(ahead of|await(?:s|ing)?|looms?|loom(?:ing)?|brac(?:e|es|ed|ing)|eyes?|eyed|in focus|forecasts?|outlook|"
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

Naglowek: {title}
Opis: {summary}
Zrodlo: {source}
Instrumenty: {symbols}

importance: 3 = nowe, nieoczekiwane zdarzenie mogace ruszyc cena w ciagu godzin; 2 = istotne tlo; 1 = szum, komentarz, zapowiedz, podsumowanie znanych faktow.
directions: dla kazdego podanego symbolu "up" (wzrostowo), "down" (spadkowo) albo "none" (niejasne lub brak wplywu). Uzyj dokladnie podanych symboli. Gdy masz watpliwosci, dawaj "none".
reason: jedno zdanie po polsku."""

# Structured outputs (output_config.format): odpowiedz jest gwarantowanym JSON-em zgodnym ze schematem.
_SCHEMA = {
    "type": "object",
    "properties": {
        "importance": {"type": "integer", "enum": [1, 2, 3]},
        "directions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}, "direction": {"type": "string", "enum": ["up", "down", "none"]}},
                "required": ["symbol", "direction"],
                "additionalProperties": False,
            },
        },
        "reason": {"type": "string"},
    },
    "required": ["importance", "directions", "reason"],
    "additionalProperties": False,
}
_DIR = {"up": 1, "down": -1, "none": 0}

DEFAULT_MODEL = "claude-haiku-5-5"
# Cennik Claude Haiku 5.5 (USD za 1 mln tokenow, prompt do 100 tys. tokenow). Do szacowania kosztu.
PRICE_INPUT_PER_MTOK, PRICE_OUTPUT_PER_MTOK = 0.10, 0.50


class LLMClassifier:
    """Klasyfikacja przez Messages API Anthropic (oficjalne SDK `anthropic`).

    Wymaga ANTHROPIC_API_KEY i pakietu `anthropic`; przy kazdym bledzie wraca do regul.
    Claude Haiku 5.5 ma domyslnie wlaczone myslenie, ktore wlicza sie do `max_tokens`: stad zapas
    tokenow i `effort: low` (klasyfikacja naglowka nie wymaga dlugiego rozumowania).
    """

    name = "llm"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 30.0,
                 fallback=None, client=None, max_tokens: int = 1024, effort: str = "low"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("CFD_LLM_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self.fallback = fallback or RuleClassifier()
        self.max_tokens = max_tokens
        self.effort = effort
        self._client = client
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    @property
    def cost_usd(self) -> float:
        """Koszt dotychczasowych wywolan wg cennika Haiku 5.5 (inny model = inne stawki)."""
        return (self.input_tokens * PRICE_INPUT_PER_MTOK + self.output_tokens * PRICE_OUTPUT_PER_MTOK) / 1e6

    def _get_client(self):
        if self._client is None:
            import anthropic  # import leniwy: bez klucza pakiet nie jest potrzebny

            self._client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout, max_retries=1)
        return self._client

    def _call(self, prompt: str) -> str:
        resp = self._get_client().messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
        usage = getattr(resp, "usage", None)
        self.calls += 1
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        if resp.stop_reason in ("refusal", "max_tokens"):
            raise ValueError(f"odpowiedz przerwana: stop_reason={resp.stop_reason}")
        # Odpowiedz moze zaczynac sie od blokow `thinking`: czytamy po typie, nie po pozycji.
        return "".join(b.text for b in resp.content if b.type == "text")

    @staticmethod
    def parse(text: str, symbols: list[str]) -> Classification:
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start : end + 1])
        importance = min(3, max(1, int(data["importance"])))
        raw = data.get("directions") or {}
        if isinstance(raw, list):  # format ze schematu: [{"symbol": ..., "direction": "up"|"down"|"none"}]
            raw = {d.get("symbol"): d.get("direction") for d in raw if isinstance(d, dict)}

        def to_int(v) -> int:
            return _DIR[v] if v in _DIR else max(-1, min(1, int(v or 0)))

        directions = {s: to_int(raw.get(s, 0)) for s in symbols}
        return Classification(importance, directions, str(data.get("reason", ""))[:300], "llm")

    def classify(self, item: NewsItem, match: dict) -> Classification:
        if not self.api_key and self._client is None:
            return self.fallback.classify(item, match)
        prompt = _PROMPT.format(title=item.title, summary=item.summary[:500] or "-", source=item.source, symbols=", ".join(match["symbols"]))
        try:
            return self.parse(self._call(prompt), match["symbols"])
        except Exception as exc:  # siec, limit, brak pakietu, odmowa, zly JSON: alert wazniejszy niz idealna ocena
            log.warning("LLM nie odpowiedzial poprawnie (%s: %s), uzywam regul", type(exc).__name__, exc)
            return self.fallback.classify(item, match)
