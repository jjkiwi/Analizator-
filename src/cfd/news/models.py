from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

_PUNCT = re.compile(r"[^\w\s&+%.]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    return _SPACE.sub(" ", _PUNCT.sub(" ", title.lower())).strip()


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    url: str = ""
    summary: str = ""
    published: datetime | None = None

    @property
    def id(self) -> str:
        return hashlib.sha1((self.url or self.title).encode("utf-8")).hexdigest()[:16]

    @property
    def norm_title(self) -> str:
        return normalize_title(self.title)

    @property
    def text(self) -> str:
        return f"{self.title}. {self.summary}".strip()
