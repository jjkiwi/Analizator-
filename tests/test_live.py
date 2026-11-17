import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from cfd.db import connect
from cfd.live import build_live, news_feed
from cfd.models import Instrument


class Data:
    def __init__(self, h, d):
        self.h, self.d = h, d

    def get(self, inst, interval, refresh=False):
        return self.h if interval == "1h" else self.d


def _frames(now):
    hi = pd.date_range(end=now.replace(minute=0, second=0, microsecond=0), periods=72, freq="h", tz="UTC")
    h = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 0}, index=hi)
    h.loc[h.index[-5:], ["open", "close"]] = 110.0
    di = pd.date_range(end=pd.Timestamp(now).normalize() - timedelta(days=1), periods=5, freq="D")
    d = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 0}, index=di)
    return h, d


def test_live_quotes_and_news_impact():
    now = datetime(2026, 11, 18, 10, 30, tzinfo=timezone.utc)
    h, d = _frames(now)
    insts = {"GOLD": Instrument("GOLD", "Zloto", "metals", {"fake": "g"})}
    conn = connect(":memory:")
    published = (now - timedelta(hours=10)).isoformat()
    conn.execute("INSERT INTO news (id, title, url, published, fetched, symbols, importance, direction) VALUES (?,?,?,?,?,?,?,?)",
                 ("a", "Gold jumps", "https://x", published, (now - timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S"),
                  "GOLD", 2, json.dumps({"GOLD": 1})))
    conn.execute("INSERT INTO news (id, title, fetched, symbols, importance) VALUES ('b', 'old', '2026-11-01 00:00:00', 'GOLD', 3)")
    snap = build_live(conn, insts, Data(h, d), ["GOLD", "NOPE"], refresh=False, now=now)
    q = snap["quotes"]["GOLD"]
    assert q["price"] == 110.0 and round(q["change_pct"], 6) == 10.0 and len(q["spark"]) == 48
    assert [n["title"] for n in snap["news"]] == ["Gold jumps"]                 # stary news poza oknem 24 h
    assert round(snap["news"][0]["moved"]["pct"], 6) == 10.0                    # od publikacji: 100 -> 110
    assert news_feed(conn, insts, Data(h, d), now=now, min_importance=3) == []
