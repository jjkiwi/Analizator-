from datetime import datetime, timedelta, timezone

import pandas as pd

from cfd import runner
from cfd.data import DataSourceError
from cfd.db import connect
from cfd.macro import MacroEvent, MacroRules, upsert_events
from cfd.models import Instrument
from cfd.news import FeedConfig, KeywordMapper, NewsItem, RuleClassifier
from cfd.report import build_rows, render_html
from cfd.settings import load_settings

from conftest import make_candles


class Capture:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return True


class FakeData:
    def __init__(self, frames):
        self.frames = frames

    def update(self, inst, interval):
        if inst.symbol not in self.frames:
            raise DataSourceError("brak")
        return self.frames[inst.symbol], "fake"

    get = lambda self, inst, interval, refresh=False: self.update(inst, interval)[0]


class Always:
    """Strategia testowa: sygnal long na kazdej swiecy."""
    name = "always"

    def generate(self, df):
        return pd.DataFrame({"side": 1, "sl_dist": 2.0, "tp_dist": 4.0, "rationale": "test"}, index=df.index)


def make_ctx(tmp_path, **kw):
    settings = load_settings(tmp_path / "brak.yaml")
    settings["scan"].update(strategies=["always"], alert_strategies=["always"], intervals=["1d"])
    insts = {s: Instrument(s, s, "indices", {"fake": s}) for s in ("US500", "GOLD")}
    return runner.Context(conn=connect(":memory:"), settings=settings, instruments=insts,
                          data=FakeData({"US500": make_candles(300)}), notifier=Capture(), **kw)


def test_scan_records_alerts_once_and_tracks_health(tmp_path, monkeypatch):
    monkeypatch.setitem(runner.REGISTRY, "always", Always)
    ctx = make_ctx(tmp_path)
    assert runner.job_scan(ctx) == 1
    assert len(ctx.notifier.sent) == 1 and "SYGNAŁ LONG US500" in ctx.notifier.sent[0]
    assert runner.job_scan(ctx) == 0 and len(ctx.notifier.sent) == 1  # ta sama swieca: bez powtorki
    health = {r["source"]: r["fail_streak"] for r in ctx.conn.execute("SELECT * FROM source_health")}
    assert health == {"candles:fake": 0, "candles:GOLD": 2}
    runner.job_scan(ctx)  # trzecia porazka z rzedu -> alert o zrodle
    assert any("Brak świeżych świec (1): GOLD (1d)" in t for t in ctx.notifier.sent)


def test_scan_without_alert_strategy_only_journals(tmp_path, monkeypatch):
    monkeypatch.setitem(runner.REGISTRY, "always", Always)
    ctx = make_ctx(tmp_path)
    ctx.settings["scan"]["alert_strategies"] = []
    assert runner.job_scan(ctx) == 1 and ctx.notifier.sent == []


def test_news_job_alerts_only_high_importance(tmp_path, monkeypatch):
    cfg = {"instruments": {"GOLD": ["gold"]}, "topics": {}, "high_impact": ["record high"]}
    ctx = make_ctx(tmp_path, feeds=[FeedConfig("f", "https://x", 300)], mapper=KeywordMapper(cfg), classifier=RuleClassifier())
    now = datetime.now(timezone.utc)
    batch = [NewsItem("f", "Gold hits record high", "u1", published=now), NewsItem("f", "Gold steady", "u2", published=now)]
    monkeypatch.setattr(runner, "fetch_feed", lambda feed: batch)
    assert runner.job_news(ctx) == 1 and "PILNE" in ctx.notifier.sent[0]
    assert runner.job_news(ctx) == 0  # feed nie jest jeszcze "due", a newsy sa juz znane

    def boom(feed):
        raise RuntimeError("503")

    ctx._last.clear()
    monkeypatch.setattr(runner, "fetch_feed", boom)
    assert runner.job_news(ctx) == 0
    assert ctx.conn.execute("SELECT fail_streak FROM source_health WHERE source='feed:f'").fetchone()[0] == 1


def test_macro_job_before_and_after(tmp_path):
    rules = MacroRules([{"name": "cpi", "country": "USD", "match": ["cpi"], "effects": {"US500": -1, "NIEMA": 1}}])
    ctx = make_ctx(tmp_path, macro_rules=rules)
    now = datetime(2026, 11, 10, 13, 5, tzinfo=timezone.utc)
    ev = MacroEvent(now + timedelta(minutes=25), "USD", "CPI m/m", 3, forecast=0.3)
    upsert_events(ctx.conn, [ev, MacroEvent(now + timedelta(minutes=10), "JPY", "Tankan", 3)])
    assert runner.job_macro(ctx, now) == 1
    assert "Za 25 min" in ctx.notifier.sent[0] and "US500" in ctx.notifier.sent[0] and "NIEMA" not in ctx.notifier.sent[0]
    assert runner.job_macro(ctx, now) == 0
    upsert_events(ctx.conn, [MacroEvent(ev.time, "USD", "CPI m/m", 3, actual=0.5, forecast=0.3)])
    assert runner.job_macro(ctx, now + timedelta(minutes=26)) == 1 and "US500↓" in ctx.notifier.sent[1]
    assert runner.job_macro(ctx, now + timedelta(minutes=27)) == 0


def test_run_once_survives_failing_job(tmp_path, monkeypatch):
    monkeypatch.setitem(runner.REGISTRY, "always", Always)
    ctx = make_ctx(tmp_path, fund_components={"US500": [{"series": "X"}]}, fund_series=lambda sid: (_ for _ in ()).throw(RuntimeError("x")))
    out = runner.run_once(ctx)
    assert out["scan"] == 1 and out["fundamentals"] == 0


def test_report_rows_and_html():
    insts = [Instrument("US500", "x", "indices", {"fake": "a"}), Instrument("ZINC", "x", "commodities", {"fake": "b"})]
    rows = build_rows(insts, FakeData({"US500": make_candles(1600, seed=5, drift=0.0006)}), "1d", ["trend_pullback"], 750, 250)
    assert rows[0]["verdict"] in {"pass", "weak", "fail"} and rows[0]["folds"] == 3 and "error" in rows[1]
    page = render_html(rows)
    assert "US500" in page and "brak danych" in page


def test_dashboard_renders_with_and_without_data(tmp_path, monkeypatch):
    from cfd.dashboard import render

    assert "Brak sygnałów" in render(connect(":memory:"))
    monkeypatch.setitem(runner.REGISTRY, "always", Always)
    ctx = make_ctx(tmp_path)
    runner.job_scan(ctx)
    page = render(ctx.conn)
    assert "US500" in page and "LONG" in page and "candles:GOLD" in page


def test_job_dashboard_writes_panel(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.settings["dashboard"] = {"refresh_minutes": 5, "path": str(tmp_path / "panel.html")}
    assert runner.job_dashboard(ctx).endswith("panel.html")
    assert "<html" in (tmp_path / "panel.html").read_text(encoding="utf-8").lower()
