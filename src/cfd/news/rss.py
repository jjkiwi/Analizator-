from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx
import yaml

from ..data.base import DataSourceError
from .models import NewsItem

MAX_BYTES = 3_000_000
USER_AGENT = "analizator-cfd/0.2 (prywatne narzedzie; RSS)"
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class FeedConfig:
    name: str
    url: str
    poll_seconds: int = 300
    enabled: bool = True


def load_feeds(path: Path | str = "config/feeds.yaml", include_disabled: bool = False) -> list[FeedConfig]:
    """Czyta liste feedow. Wpisy z `enabled: false` sa pomijane, chyba ze `include_disabled`.

    Zapytanie Google News to napis albo slownik {q, hl, gl, ceid} (np. polska edycja).
    `when` (np. "1d") zaweza wyniki do swiezych: bez tego wyszukiwarka zwraca tez artykuly sprzed tygodni.
    Komplet hl/gl/ceid jest wymagany: bez niego Google odpowiada przekierowaniem 302.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    feeds = [FeedConfig(**f) for f in raw.get("feeds", [])]
    g = raw.get("google_news") or {}
    if g.get("enabled"):
        for entry in g.get("queries", []):
            entry = {"q": entry} if isinstance(entry, str) else dict(entry)
            q = entry.pop("q")
            params = {**g.get("params", {}), **entry}
            text = f"{q} when:{g['when']}" if g.get("when") else q
            qs = urlencode({"q": text, **params})
            slug = re.sub(r"\W+", "_", q.lower()).strip("_")
            feeds.append(FeedConfig(f"gnews_{slug}", f"https://news.google.com/rss/search?{qs}", g.get("poll_seconds", 300)))
    return feeds if include_disabled else [f for f in feeds if f.enabled]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _clean(text: str | None) -> str:
    return html.unescape(_TAGS.sub(" ", text or "")).strip()


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def parse_feed(xml_text: str, source: str) -> list[NewsItem]:
    """Parsuje RSS 2.0 i Atom. Zwraca pusta liste dla nieznanego formatu.

    Google News dokleja do tytulu " - Wydawca", a opis to ten sam tytul z linkiem. Wydawce odcinamy
    (trafia na poczatek opisu), bo nazwy typu "Bitcoin Magazine" czy "Kitco Gold" falszowaly mapowanie
    slow kluczowych i psuly wykrywanie duplikatow.
    """
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        fields: dict[str, str] = {}
        for child in node:
            key = _local(child.tag)
            if key == "link":
                value = (child.text or "").strip() or child.attrib.get("href", "")
                if child.attrib.get("rel", "alternate") != "alternate" and "link" in fields:
                    continue
            else:
                value = child.text or ""
            fields.setdefault(key, value)
        title = _clean(fields.get("title"))
        if not title:
            continue
        summary = _clean(fields.get("description") or fields.get("summary") or fields.get("content"))[:1000]
        publisher = _clean(fields.get("source"))
        if publisher and _local(node.tag) == "item" and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3].rstrip()
            summary = ""  # opis Google News to powtorzony tytul i nazwa wydawcy
        if not title:
            continue
        items.append(
            NewsItem(
                source=source,
                title=title,
                url=fields.get("link", "").strip(),
                summary=summary,
                published=_parse_date(fields.get("pubdate") or fields.get("published") or fields.get("updated") or fields.get("date")),
            )
        )
    return items


def fetch_feed(feed: FeedConfig, client: httpx.Client | None = None, timeout: float = 15.0) -> list[NewsItem]:
    """Pobiera i parsuje feed. Kazda porazka to `DataSourceError` z przyczyna, nigdy cicha pusta lista."""
    own = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        try:
            resp = client.get(feed.url)
        except httpx.HTTPError as exc:
            raise DataSourceError(f"feed {feed.name}: blad sieci ({type(exc).__name__}: {exc})") from exc
        final = str(resp.url)
        if "/sorry/" in final or "consent.google" in final:
            raise DataSourceError(f"feed {feed.name}: Google przekierowal na strone blokady/zgody ({final[:80]})")
        if resp.status_code == 429:
            raise DataSourceError(f"feed {feed.name}: HTTP 429, serwis ogranicza liczbe zapytan")
        if resp.status_code >= 400:
            guard = " (ochrona przed botami)" if resp.headers.get("cf-mitigated") or "Access Denied" in resp.text[:300] else ""
            raise DataSourceError(f"feed {feed.name}: HTTP {resp.status_code}{guard}")
        if len(resp.content) > MAX_BYTES:
            raise DataSourceError(f"feed {feed.name} przekracza {MAX_BYTES} bajtow")
        try:
            items = parse_feed(resp.text, feed.name)
        except ET.ParseError as exc:
            raise DataSourceError(f"feed {feed.name}: odpowiedz nie jest poprawnym XML ({exc}); poczatek: {resp.text[:60]!r}") from exc
        if not items:
            raise DataSourceError(f"feed {feed.name}: brak pozycji (zmieniony format albo to nie jest RSS/Atom)")
        return items
    finally:
        if own:
            client.close()
