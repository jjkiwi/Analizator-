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

from .models import NewsItem

MAX_BYTES = 3_000_000
USER_AGENT = "analizator-cfd/0.2 (prywatne narzedzie; RSS)"
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class FeedConfig:
    name: str
    url: str
    poll_seconds: int = 300


def load_feeds(path: Path | str = "config/feeds.yaml") -> list[FeedConfig]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    feeds = [FeedConfig(**f) for f in raw.get("feeds", [])]
    g = raw.get("google_news") or {}
    if g.get("enabled"):
        for q in g.get("queries", []):
            qs = urlencode({"q": q, **g.get("params", {})})
            slug = re.sub(r"\W+", "_", q.lower()).strip("_")
            feeds.append(FeedConfig(f"gnews_{slug}", f"https://news.google.com/rss/search?{qs}", g.get("poll_seconds", 300)))
    return feeds


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
    """Parsuje RSS 2.0 i Atom. Zwraca pusta liste dla nieznanego formatu."""
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
        items.append(
            NewsItem(
                source=source,
                title=title,
                url=fields.get("link", "").strip(),
                summary=_clean(fields.get("description") or fields.get("summary") or fields.get("content"))[:1000],
                published=_parse_date(fields.get("pubdate") or fields.get("published") or fields.get("updated") or fields.get("date")),
            )
        )
    return items


def fetch_feed(feed: FeedConfig, client: httpx.Client | None = None, timeout: float = 15.0) -> list[NewsItem]:
    own = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        resp = client.get(feed.url)
        resp.raise_for_status()
        if len(resp.content) > MAX_BYTES:
            raise ValueError(f"feed {feed.name} przekracza {MAX_BYTES} bajtow")
        return parse_feed(resp.text, feed.name)
    finally:
        if own:
            client.close()
