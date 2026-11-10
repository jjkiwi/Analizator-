from datetime import datetime, timedelta, timezone

import pytest

from cfd.db import connect
from cfd.news import KeywordMapper, LLMClassifier, NewsItem, RuleClassifier, parse_feed, process_items
from cfd.news.pipeline import is_duplicate, recent_news_direction
from cfd.news.rss import load_feeds

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Gold surges &amp; hits record high</title><link>https://ex.com/a</link>
<description>&lt;p&gt;Bullion jumped.&lt;/p&gt;</description><pubDate>Mon, 09 Nov 2026 14:30:00 GMT</pubDate></item>
<item><title></title><link>https://ex.com/empty</link></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Fed holds rates</title>
<link rel="alternate" href="https://ex.com/b"/><summary>FOMC statement</summary>
<updated>2026-11-09T19:00:00Z</updated></entry></feed>"""

CFG = {
    "instruments": {"GOLD": ["gold", "bullion"], "OIL": ["brent"], "ETHEREUM": ["eth"], "ZZZ": ["zzz"]},
    "topics": {"fed": {"keywords": ["fed", "fomc"], "symbols": ["US500", "GOLD", "ZZZ"]},
               "oil": {"keywords": ["opec+"], "symbols": ["OIL"]}},
    "high_impact": ["record high", "holds rates"],
}
KNOWN = {"GOLD", "OIL", "US500", "ETHEREUM"}


def test_parse_rss_and_atom():
    (item,) = parse_feed(RSS, "src")
    assert item.title == "Gold surges & hits record high" and item.url == "https://ex.com/a"
    assert item.summary == "Bullion jumped." and item.published == datetime(2026, 11, 9, 14, 30, tzinfo=timezone.utc)
    (entry,) = parse_feed(ATOM, "fed")
    assert entry.url == "https://ex.com/b" and entry.published.hour == 19


def test_mapper_direct_topics_and_word_boundaries():
    m = KeywordMapper(CFG, KNOWN)
    r = m.match("Fed holds rates as gold slips")
    assert r["direct"] == ["GOLD"] and r["topics"] == ["fed"]
    assert r["symbols"] == ["GOLD", "US500"] and r["high_impact"]  # ZZZ nieznany -> odfiltrowany
    assert m.match("OPEC+ agrees output cut")["symbols"] == ["OIL"]
    assert m.match("Method to feed goldfish, Bethlehem")["symbols"] == []


def test_rule_classifier():
    m, c = KeywordMapper(CFG, KNOWN), RuleClassifier()
    item = NewsItem("s", "Gold surges & hits record high")
    cls = c.classify(item, m.match(item.text))
    assert cls.importance == 3 and cls.directions == {"GOLD": 1}
    item = NewsItem("s", "Fed officials speak on outlook")
    cls = c.classify(item, m.match(item.text))
    assert cls.importance == 1 and set(cls.directions.values()) == {0}


def test_llm_parse_and_fallback(monkeypatch):
    cls = LLMClassifier.parse('Oto: {"importance": 9, "directions": {"GOLD": -1, "XXX": 1}, "reason": "bo tak"}', ["GOLD", "US500"])
    assert cls.importance == 3 and cls.directions == {"GOLD": -1, "US500": 0} and cls.classifier == "llm"
    llm = LLMClassifier(api_key="k")
    monkeypatch.setattr(llm, "_call", lambda prompt: "to nie jest json")
    m = KeywordMapper(CFG, KNOWN)
    item = NewsItem("s", "Gold surges")
    assert llm.classify(item, m.match(item.text)).classifier == "rules"


def test_duplicate_detection():
    assert is_duplicate("fed holds rates steady in november", ["fed holds rates steady in november meeting"])
    assert not is_duplicate("fed holds rates steady", ["opec agrees output cut"])


class Counting(RuleClassifier):
    name = "expensive"

    def __init__(self):
        self.calls = 0

    def classify(self, item, match):
        self.calls += 1
        return super().classify(item, match)


def test_pipeline_filters_dedupes_and_gates_expensive_classifier():
    conn, m, expensive = connect(":memory:"), KeywordMapper(CFG, KNOWN), Counting()
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    items = [
        NewsItem("a", "Gold surges to record high", "https://x/1", published=now),
        NewsItem("b", "Gold surges to a record high", "https://y/1", published=now),      # duplikat z innego zrodla
        NewsItem("a", "Fed officials speak on outlook", "https://x/2", published=now),     # waga 1: bez drogiego klasyfikatora
        NewsItem("a", "Local sports results", "https://x/3", published=now),               # bez instrumentu
        NewsItem("a", "Brent old story", "https://x/4", published=now - timedelta(days=3)),  # za stary
    ]
    out = process_items(conn, items, m, expensive, RuleClassifier(), 24, now)
    assert [i.title for i, _ in out] == ["Gold surges to record high", "Fed officials speak on outlook"]
    assert expensive.calls == 1
    assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 4
    assert process_items(conn, items, m, expensive, RuleClassifier(), 24, now) == []  # drugi przebieg: nic nowego
    assert recent_news_direction(conn, "GOLD") == 1
    assert recent_news_direction(conn, "OIL") == 0


def test_feed_config_builds_google_news_urls(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text('feeds: [{name: a, url: "https://a/rss"}]\ngoogle_news: {enabled: true, params: {hl: en}, queries: ["gold price"]}\n')
    feeds = load_feeds(p)
    assert feeds[1].name == "gnews_gold_price" and "q=gold+price" in feeds[1].url and "hl=en" in feeds[1].url
