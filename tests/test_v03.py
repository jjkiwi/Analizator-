import json
from datetime import datetime, timezone

import httpx
import pytest

from cfd import journal, sync
from cfd.db import connect
from cfd.fundamentals import save_bias
from cfd.models import Signal
from cfd.news import ChainClassifier, KeywordMapper, NewsItem, Provider, load_feeds
from cfd.notify import QuietNotifier, in_quiet_hours
from cfd.scanner import due_intervals


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_due_intervals():
    cfg = ["1d", "4h", "1h", "30m"]
    assert due_intervals(utc("2026-11-10T08:02"), cfg) == ["1d", "4h", "1h", "30m"]
    assert due_intervals(utc("2026-11-10T09:02"), cfg) == ["1h", "30m"]
    assert due_intervals(utc("2026-11-10T08:32"), cfg) == ["30m"]
    assert due_intervals(utc("2026-11-10T08:32"), ["1d", "4h"]) == []


def test_quiet_hours_warsaw_winter_and_summer():
    assert not in_quiet_hours(utc("2026-11-10T21:59"), 23, 8, "Europe/Warsaw")
    assert in_quiet_hours(utc("2026-11-10T22:00"), 23, 8, "Europe/Warsaw")
    assert in_quiet_hours(utc("2026-11-11T06:59"), 23, 8, "Europe/Warsaw")
    assert not in_quiet_hours(utc("2026-11-11T07:00"), 23, 8, "Europe/Warsaw")
    assert in_quiet_hours(utc("2026-07-10T21:00"), 23, 8, "Europe/Warsaw")
    assert not in_quiet_hours(utc("2026-07-10T12:00"), 0, 0, "UTC")


class Capture:
    def __init__(self, ok=True):
        self.sent, self.ok = [], ok

    def send(self, text):
        self.sent.append(text)
        return self.ok


def test_quiet_notifier_holds_then_sends_digest():
    conn, inner, clock = connect(":memory:"), Capture(), [utc("2026-11-10T23:30")]
    q = QuietNotifier(inner, conn, clock=lambda: clock[0])
    assert q.send("nocny 1") and q.send("nocny 2")
    assert inner.sent == [] and conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 2
    assert q.flush() == 0  # nadal cisza
    clock[0] = utc("2026-11-11T07:05")
    q.send("poranny")
    assert len(inner.sent) == 2 and inner.sent[0].startswith("🌙 Podsumowanie nocy: 2") and "nocny 2" in inner.sent[0]
    assert inner.sent[1] == "poranny" and conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0


def test_quiet_notifier_keeps_outbox_when_delivery_fails():
    conn, clock = connect(":memory:"), [utc("2026-11-10T23:30")]
    q = QuietNotifier(Capture(ok=False), conn, clock=lambda: clock[0])
    q.send("nocny")
    clock[0] = utc("2026-11-11T09:00")
    q.flush()
    assert conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1


def test_chain_classifier_skips_keyless_fails_over_and_cools_down(monkeypatch):
    monkeypatch.setenv("KEY_A", "1")
    monkeypatch.setenv("KEY_B", "2")
    monkeypatch.delenv("KEY_C", raising=False)
    calls = []

    def post(provider, prompt):
        calls.append(provider.name)
        if provider.name == "a":
            raise httpx.HTTPError("429")
        return 'Jasne: {"importance": 2, "directions": {"GOLD": -1}, "reason": "r"}'

    chain = ChainClassifier([Provider(n, "http://x", "m", f"KEY_{n.upper()}") for n in "abc"], post=post)
    assert [p.name for p in chain.providers] == ["a", "b"]
    m = KeywordMapper({"instruments": {"GOLD": ["gold"]}, "topics": {}, "high_impact": []})
    item = NewsItem("s", "Gold slips")
    cls = chain.classify(item, m.match(item.text))
    assert cls.classifier == "llm:b" and cls.directions == {"GOLD": -1} and calls == ["a", "b"]
    chain.classify(item, m.match(item.text))
    assert calls == ["a", "b", "b"]  # "a" odpoczywa po bledzie

    broken = ChainClassifier([Provider("a", "http://x", "m", "KEY_A")], post=lambda p, prompt: "to nie json")
    assert broken.classify(item, m.match(item.text)).classifier == "rules"


def test_feeds_config_has_unique_names_and_languages():
    feeds = load_feeds("config/feeds.yaml")
    names = [f.name for f in feeds]
    assert len(names) == len(set(names))
    assert {n.split("_")[1] for n in names if n.startswith("gnews_")} == {"en", "pl", "de", "fr", "es"}
    assert all(f.url.startswith("https://") for f in feeds)


def fake_supabase(store):
    def handler(request: httpx.Request) -> httpx.Response:
        table = request.url.path.rsplit("/", 1)[-1]
        assert request.headers["apikey"] == "svc"
        if request.method == "POST":
            store.setdefault(table, []).extend(json.loads(request.content))
            store.setdefault("_conflict", {})[table] = request.url.params["on_conflict"]
            return httpx.Response(201)
        return httpx.Response(200, json=store.get("_select", {}).get(table, []))

    return sync.SupabaseClient("https://p.supabase.co", "svc", transport=httpx.MockTransport(handler))


def test_sync_push_and_pull():
    conn, store = connect(":memory:"), {}
    sb = fake_supabase(store)
    sig = Signal("GOLD", "s", utc("2026-11-10T00:00"), 1, 100.0, 98.0, 104.0, "test")
    journal.record(conn, sig, "1d", 2.0, {"label": "mocny"})
    save_bias(conn, "GOLD", 1.2, [{"series": "X", "score": 1.2}])
    assert sync.push(conn, sb) == {"signals": 1, "fundamental_bias": 1, "source_health": 0}
    assert store["signals"][0]["context"] == {"label": "mocny"} and store["_conflict"]["signals"] == "symbol,strategy,interval,time"
    assert store["fundamental_bias"][0]["components"] == [{"series": "X", "score": 1.2}]

    fresh = connect(":memory:")  # np. po utracie cache w GitHub Actions
    store["_select"] = {
        "signals": [{**store["signals"][0], "status": "open"}],
        "news": [{"id": "n1", "source": "f", "title": "Gold up", "url": "u", "published": None, "norm_title": "gold up",
                  "symbols": "GOLD", "importance": 3, "direction": {"GOLD": 1}, "reason": "r", "classifier": "llm:x"}],
    }
    assert sync.pull_open_signals(fresh, sb) == 1 and sync.pull_open_signals(fresh, sb) == 0
    assert journal.record(fresh, sig, "1d") is False  # ten sam sygnal nie wywola drugiego alertu
    assert sync.pull_news_directions(fresh, sb) == 1
    from cfd.news.pipeline import recent_news_direction

    assert recent_news_direction(fresh, "GOLD") == 1


def test_sync_requires_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(RuntimeError):
        sync.SupabaseClient()
