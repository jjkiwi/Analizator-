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


# ---------- testy na probkach prawdziwych odpowiedzi (C1-C3) ----------

import json
from pathlib import Path
from types import SimpleNamespace

import httpx

from cfd.data.base import DataSourceError
from cfd.news.rss import FeedConfig, fetch_feed

FIX = Path(__file__).parent / "fixtures"
REAL_KEYWORDS = Path(__file__).parent.parent / "config" / "keywords.yaml"


def _fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_parse_real_google_news_strips_publisher():
    items = parse_feed(_fixture("news_gnews_gold_price.xml"), "gnews_gold_price")
    assert len(items) == 4
    second = items[1]
    assert second.title == "Gold falls more than 2% as CPI tops forecasts, lifting dollar and yields"  # bez " - Reuters"
    assert second.summary == "" and second.url.startswith("https://news.google.com/rss/articles/")
    assert second.published == datetime(2026, 11, 10, 3, 31, tzinfo=timezone.utc)
    pl = parse_feed(_fixture("news_gnews_pl_nbp.xml"), "gnews_pl")
    assert pl[0].title.startswith("RPP może podnieść stopy procentowe") and pl[0].published.tzinfo is not None


def test_parse_real_fed_press():
    items = parse_feed(_fixture("news_fed_press.xml"), "fed_press")
    assert len(items) == 3 and items[0].title.startswith("Federal Reserve Board announces")
    assert items[0].url.startswith("https://www.federalreserve.gov/") and items[0].published.year == 2026


def test_load_feeds_disabled_polish_query_and_when(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text(
        'feeds: [{name: a, url: "https://a/rss"}, {name: wyl, url: "https://b/rss", enabled: false}]\n'
        'google_news: {enabled: true, when: "1d", params: {hl: en-US, gl: US, ceid: "US:en"},\n'
        '  queries: ["gold price", {q: "NBP stopy", hl: pl, gl: PL, ceid: "PL:pl"}]}\n', encoding="utf-8")
    feeds = load_feeds(p)
    assert [f.name for f in feeds] == ["a", "gnews_gold_price", "gnews_nbp_stopy"]
    assert "q=gold+price+when%3A1d" in feeds[1].url and "ceid=US%3Aen" in feeds[1].url
    assert "hl=pl" in feeds[2].url and "gl=PL" in feeds[2].url and "ceid=PL%3Apl" in feeds[2].url
    assert [f.name for f in load_feeds(p, include_disabled=True)][1] == "wyl"


def test_real_feeds_yaml_loads():
    feeds = load_feeds(Path(__file__).parent.parent / "config" / "feeds.yaml", include_disabled=True)
    assert len({f.name for f in feeds}) == len(feeds)
    assert all(f.url.startswith("https://") for f in feeds)
    assert all("hl=" in f.url and "gl=" in f.url and "ceid=" in f.url for f in feeds if f.name.startswith("gnews_"))


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_fetch_feed_follows_redirect_and_reports_clear_errors():
    feed = FeedConfig("g", "https://news.google.com/rss/search?q=gold")
    body = _fixture("news_gnews_gold_price.xml")

    def redirecting(request: httpx.Request) -> httpx.Response:
        if "ceid" not in str(request.url):  # tak odpowiada Google bez kompletu hl/gl/ceid
            return httpx.Response(302, headers={"location": str(request.url) + "&hl=en-US&gl=US&ceid=US:en"})
        return httpx.Response(200, text=body)

    assert len(fetch_feed(feed, _client(redirecting))) == 4
    cases = {
        "ochrona przed botami": lambda r: httpx.Response(403, headers={"cf-mitigated": "challenge"}, text="<html>Just a moment...</html>"),
        "429": lambda r: httpx.Response(429, text="too many"),
        "nie jest poprawnym XML": lambda r: httpx.Response(200, text="<html><body>captcha<br></body></html>"),
        "brak pozycji": lambda r: httpx.Response(200, text="<rss><channel></channel></rss>"),
        "strone blokady": lambda r: httpx.Response(302, headers={"location": "https://www.google.com/sorry/index"})
        if "sorry" not in str(r.url) else httpx.Response(200, text="<html/>"),
    }
    for expected, handler in cases.items():
        with pytest.raises(DataSourceError, match=expected):
            fetch_feed(feed, _client(handler))


def test_real_keywords_ambiguous_words():
    """Przypadki z zywych danych 2026-11-10 (C2): wieloznaczne slowa nie moga mapowac sie na instrument."""
    m = KeywordMapper.from_file(REAL_KEYWORDS)
    no_direct = {
        "GOLD": ["Gold rates today 10 Nov Tuesday: check retail rates of 24K, 22K", "Why Gold Miners Rose on Gold’s Down Day",
                 "Barrick Gold earnings analysis", "She won a gold medal"],
        "ETHEREUM": ["Method eth results", "the ether of space"],
        "JP225": ["Polski boj o medale"],
        "NATGAS": ["LNG Traffic Through Hormuz Hits Highest Level"],
        "SUGAR": ["Blood sugar drug wins approval"],
        "CORN": ["Corn dogs are back at the fair"],
        "SOYBEAN": ["As Crude Oil Prices Retreat, Sell Soybean Oil Now"],
        "US500": ["Here's what Wall Street has to say about the scandal"],
    }
    for symbol, texts in no_direct.items():
        for text in texts:
            assert symbol not in m.match(text)["direct"], (symbol, text)
    assert m.match("They fed the cattle and got fed up")["symbols"] == []
    assert "fed" in m.match("Fed's Waller backs December rate hike")["topics"]
    assert m.match("Bitcoin, Ether Fall as ETH lags")["direct"] == ["BITCOIN", "ETHEREUM"]
    assert m.match("Gold falls more than 2% as CPI tops forecasts")["direct"] == ["GOLD"]
    assert m.match("Greek inflation rises further in October")["symbols"] == []  # inflacja spoza USA
    assert "nbp" in m.match("RPP może podnieść stopy procentowe")["topics"]


def test_high_impact_only_in_title_and_moves_need_direct():
    m = KeywordMapper.from_file(REAL_KEYWORDS)
    assert not m.match("Stocks mixed. Analysts mention CPI in passing", "Stocks mixed")["high_impact"]
    assert not m.match("Global Carbon Emissions Set to Dip After Iran War Oil Prices Surge", "x")["high_impact"]
    r = m.match("US Treasury yields surge as inflation data exceeds forecasts")
    assert r["symbols"] and not r["direct"] and not r["high_impact"]  # "surge" bez instrumentu wprost
    r = m.match("Gold surges past $4,200")
    assert r["high_impact"] and r["high_impact_hits"] == ["surges"]


def test_rules_demote_previews_and_questions():
    m, c = KeywordMapper.from_file(REAL_KEYWORDS), RuleClassifier()

    def imp(title: str) -> int:
        item = NewsItem("s", title)
        return c.classify(item, m.match(item.text, item.title)).importance

    assert imp("U.S. CPI rose stronger than expected 0.4% in October; core rate rose 0.3%") == 3
    assert imp("Fed’s Waller puts half-point rate hike into the mix for December") == 3
    assert imp("Gold drifts lower as traders eye US CPI and dip-buying support") == 2
    assert imp("British Pound steadies ahead of US CPI data") <= 2
    assert imp("Will the Federal Reserve raise interest rates in December?") <= 2
    assert imp("Bitcoin Price Forecast: Can US CPI revive the BTC bulls?") == 2


def test_pipeline_repeat_topic_cooldown():
    conn, m, rules = connect(":memory:"), KeywordMapper.from_file(REAL_KEYWORDS), RuleClassifier()
    now = datetime.now(timezone.utc)
    items = [
        NewsItem("a", "U.S. CPI rose stronger than expected 0.4% in October", "https://x/1", published=now),
        NewsItem("b", "Inflation remained elevated in October, CPI report shows", "https://x/2", published=now),
        NewsItem("c", "OPEC output returns to 90% of pre-war levels", "https://x/3", published=now),
    ]
    out = process_items(conn, items, m, rules, None, 24, now)
    assert [c.importance for _, c in out] == [3, 2, 3]  # drugi news o CPI to juz powtorka tematu
    more = [NewsItem("d", "US core CPI rises by more than forecast", "https://x/4", published=now)]
    assert process_items(conn, more, m, rules, None, 24, now)[0][1].importance == 2  # pamiec z bazy
    again = [NewsItem("e", "CPI report shows prices hot enough", "https://x/5", published=now)]
    assert process_items(conn, again, m, rules, None, 24, now, repeat_cooldown_minutes=0)[0][1].importance == 3
