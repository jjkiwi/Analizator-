import json
from datetime import date
from pathlib import Path

import pytest

from cfd.data import DataSourceError
from cfd.db import connect
from cfd.fundamentals import stocks

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "yahoo_stock_CDR.WA.json").read_text(encoding="utf-8"))


def test_shape_snapshot_on_real_sample():
    snap = stocks.shape_snapshot(SAMPLE["info"], SAMPLE["calendar"], SAMPLE["quarterly"])
    assert snap["currency"] == "PLN" and snap["currentPrice"] > 0
    assert snap["earnings_date"] == "2026-11-24"
    assert snap["quarter"] == "2026-06-30" and snap["quarter_revenue"] == 244201000.0
    # ten sam kwartal rok wczesniej: 2025-06-30 (216,7 mln) -> +12,7%
    assert snap["quarter_revenue_yoy"] == pytest.approx(244201000 / 216734000 - 1)


def test_shape_snapshot_rejects_empty_and_handles_missing_parts():
    with pytest.raises(DataSourceError):
        stocks.shape_snapshot({}, None, None)
    snap = stocks.shape_snapshot({"currentPrice": 10, "currency": "USD", "trailingPE": float("nan")}, {"Earnings Date": []}, {})
    assert snap["earnings_date"] is None and snap["trailingPE"] is None and snap["quarter_revenue_yoy"] is None


def test_assess_pillars_verdicts_and_report_date():
    snap = stocks.shape_snapshot(SAMPLE["info"], SAMPLE["calendar"], SAMPLE["quarterly"])
    a = stocks.assess(snap, price_above_sma200=True, today=date(2026, 11, 12))
    by = {p["name"]: p["score"] for p in a["pillars"]}
    assert by["Wzrost przychodów"] == 1 and by["Zyskowność"] == 1 and by["Zadłużenie"] == 1 and by["Trend kursu"] == 1
    assert by["Wycena"] == -1          # C/Z prognozowane ok. 173
    assert by["Konsensus analityków"] == -1   # cena docelowa ponizej kursu
    assert a["total"] == 2 and a["class"] == "neutral"
    assert a["earnings_in_days"] == 12 and a["report_soon"]
    weak = {"currentPrice": 10, "revenueGrowth": -0.2, "profitMargins": -0.1, "trailingEps": -1, "debtToEquity": 300}
    assert stocks.assess(weak, False)["class"] == "bad"
    assert stocks.assess({"currentPrice": 10}, None)["class"] == "unknown"


def test_save_and_read(tmp_path):
    conn = connect(":memory:")
    stocks.save(conn, "CDR.PL", {"currentPrice": 1.0})
    stocks.save(conn, "CDR.PL", {"currentPrice": 2.0})
    assert stocks.read_all(conn)["CDR.PL"]["currentPrice"] == 2.0
