import json
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from cfd.charts import candle_svg, chart_panel
from cfd.features.patterns import detect_patterns, support_resistance, swing_points
from conftest import make_candles


def frame_from_path(knots, seed=0, noise=0.15, wick=0.4, freq="1D"):
    """Swiece wokol odcinkowo liniowej sciezki [(liczba swiec, cena docelowa), ...]."""
    rng = np.random.default_rng(seed)
    pts = [knots[0][1]]
    for length, target in knots[1:]:
        pts.extend(np.linspace(pts[-1], target, length + 1)[1:])
    mid = np.array(pts, float)
    close = mid + rng.normal(0, noise, len(mid))
    open_ = np.concatenate([[close[0]], close[:-1]])
    w = np.abs(rng.normal(wick, wick / 3, len(mid)))
    return pd.DataFrame(
        {"open": open_, "high": np.maximum(open_, close) + w, "low": np.minimum(open_, close) - w,
         "close": close, "volume": 1.0},
        index=pd.date_range("2024-01-01", periods=len(mid), freq=freq, tz="UTC", name="time"),
    )


def types(pats):
    return [p["type"] for p in pats]


def test_swing_points_simple():
    df = frame_from_path([(0, 100), (10, 110), (10, 100), (10, 112), (10, 101)], noise=0.0, wick=0.2)
    sw = swing_points(df)
    highs = sw[sw.kind == "high"]
    assert len(highs) >= 2
    assert highs.price.max() == pytest.approx(df.high.max())
    # ostatnie `right` swiec nie moga byc punktem zwrotnym
    assert sw.pos.max() <= len(df) - 1 - 3


def test_swing_points_causal():
    df = make_candles(400, seed=3)
    full = swing_points(df)
    for n in (100, 217, 333):
        part = swing_points(df.iloc[:n])
        expected = full[full.pos <= n - 1 - 3]
        pd.testing.assert_frame_equal(part, expected)


def test_double_top_detected_and_confirmed():
    df = frame_from_path([(0, 90), (25, 110), (12, 100), (12, 110), (10, 97)], seed=1)
    pats = detect_patterns(df)
    dt = [p for p in pats if p["type"] == "double_top"]
    assert dt, types(pats)
    p = dt[0]
    assert p["direction"] == -1 and p["status"] == "potwierdzona" and p["label"] == "Podwójny szczyt"
    neck = [lv for lv in p["levels"] if lv["role"] == "szyja"][0]["price"]
    assert 98 < neck < 102
    assert any(ln["role"] == "szyja" for ln in p["lines"])


def test_double_top_in_progress_before_break():
    df = frame_from_path([(0, 90), (25, 110), (12, 100), (12, 110), (6, 104)], seed=1)
    dt = [p for p in detect_patterns(df) if p["type"] == "double_top"]
    assert dt and dt[0]["status"] == "w budowie"


def test_double_bottom_detected():
    df = frame_from_path([(0, 120), (25, 100), (12, 110), (12, 100), (10, 113)], seed=2)
    db = [p for p in detect_patterns(df) if p["type"] == "double_bottom"]
    assert db and db[0]["direction"] == 1 and db[0]["status"] == "potwierdzona"


def test_triangle_detected():
    # zbiezne wahania: szczyty coraz nizsze, dolki coraz wyzsze
    df = frame_from_path([(0, 100), (8, 120), (8, 102), (8, 117), (8, 105), (8, 114), (8, 108), (4, 111)],
                         seed=4, noise=0.1, wick=0.3)
    tri = [p for p in detect_patterns(df) if p["type"].startswith("triangle")]
    assert tri, types(detect_patterns(df))
    assert tri[0]["type"] == "triangle_sym" and len(tri[0]["lines"]) == 2


def test_ascending_triangle_detected():
    df = frame_from_path([(0, 100), (8, 120), (8, 104), (8, 120), (8, 109), (8, 120), (8, 114), (4, 117)],
                         seed=5, noise=0.1, wick=0.3)
    tri = [p for p in detect_patterns(df) if p["type"].startswith("triangle")]
    assert tri and tri[0]["type"] == "triangle_asc" and tri[0]["direction"] == 1


def test_consolidation_and_breakout():
    base = [(0, 80), (30, 100)] + [(3, 101 if i % 2 else 99) for i in range(10)]
    cons = frame_from_path(base, seed=6, noise=0.1, wick=0.3)
    pats = detect_patterns(cons)
    assert "consolidation" in types(pats), types(pats)
    brk = frame_from_path(base + [(3, 106)], seed=6, noise=0.1, wick=0.3)
    b = [p for p in detect_patterns(brk) if p["type"] == "breakout"]
    assert b and b[0]["direction"] == 1 and b[0]["status"] == "potwierdzona"
    assert b[0]["label"] == "Wybicie z konsolidacji w górę"


def test_uptrend_detected():
    knots = [(0, 100)]
    for i in range(6):
        knots += [(6, 100 + 6 * (i + 1)), (4, 97 + 6 * (i + 1))]
    knots += [(3, 140)]
    pats = detect_patterns(frame_from_path(knots, seed=7, noise=0.1, wick=0.3))
    tr = [p for p in pats if p["type"] in ("trend", "channel")]
    assert tr and tr[0]["direction"] == 1, types(pats)


def test_support_resistance_levels():
    knots = [(0, 100)] + [(6, 110 if i % 2 == 0 else 100) for i in range(12)] + [(3, 105)]
    df = frame_from_path(knots, seed=8, noise=0.1, wick=0.2)
    lv = support_resistance(df)
    roles = {x["role"] for x in lv}
    assert roles == {"opór", "wsparcie"}
    res = [x for x in lv if x["role"] == "opór"][-1]
    sup = [x for x in lv if x["role"] == "wsparcie"][0]
    assert abs(res["price"] - 110) < 1.5 and res["touches"] >= 3
    assert abs(sup["price"] - 100) < 1.5 and sup["touches"] >= 3
    assert [x["price"] for x in lv] == sorted([x["price"] for x in lv], reverse=True)


@pytest.mark.parametrize("seed", range(12))
def test_random_series_do_not_explode(seed):
    df = make_candles(500, seed=seed, vol=0.005 + 0.003 * (seed % 4))
    pats = detect_patterns(df)
    assert len(pats) <= 3
    for p in pats:
        assert p["direction"] in (-1, 0, 1) and p["status"] in ("w budowie", "potwierdzona")
        assert p["start"] <= p["end"] <= df.index[-1]
        for ln in p["lines"]:
            assert set(ln) == {"t0", "p0", "t1", "p1", "role"} and np.isfinite([ln["p0"], ln["p1"]]).all()
    assert len(support_resistance(df)) <= 4


def test_short_and_flat_inputs():
    assert detect_patterns(make_candles(10)) == []
    flat = make_candles(100)
    flat[["open", "high", "low", "close"]] = 50.0
    detect_patterns(flat)
    support_resistance(flat)
    ET.fromstring(candle_svg(flat))
    ET.fromstring(candle_svg(flat.iloc[:0]))


def test_detect_patterns_causal():
    df = make_candles(600, seed=11)
    for n in (200, 350, 480):
        base = detect_patterns(df.iloc[:n])
        changed = df.copy()
        rng = np.random.default_rng(n)
        changed.iloc[n:, :4] = changed.iloc[n:, :4].to_numpy() * rng.uniform(0.7, 1.3, (len(df) - n, 1))
        assert detect_patterns(changed.iloc[:n]) == base
        assert support_resistance(changed.iloc[:n]) == support_resistance(df.iloc[:n])


def test_patterns_end_not_after_last_candle_look_ahead():
    df = frame_from_path([(0, 90), (25, 110), (12, 100), (12, 110), (10, 97)], seed=1)
    for n in range(40, len(df) + 1, 3):
        for p in detect_patterns(df.iloc[:n]):
            assert p["end"] <= df.index[n - 1]
            for ln in p["lines"]:
                assert ln["t1"] <= df.index[n - 1]


def test_candle_svg_is_valid_xml_with_candles():
    df = frame_from_path([(0, 90), (25, 110), (12, 100), (12, 110), (10, 97)], seed=1)
    pats = detect_patterns(df)
    svg = candle_svg(df, pats, support_resistance(df), title="TEST & <1d>", bars=60)
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    g = root.find(f"{ns}g")
    assert g is not None and g.get("data-n") == "60"
    assert root.get("viewBox") == "0 0 640 260" and root.get("width") == "100%"
    assert len(g.findall(f"{ns}path")) >= 1
    assert "var(--up" in svg and "var(--down" in svg and "<script" not in svg
    assert any("Podwójny szczyt" in (t.text or "") for t in root.iter(f"{ns}text"))


def test_candle_svg_size_limit():
    df = make_candles(300, seed=2)
    svg = candle_svg(df, detect_patterns(df), support_resistance(df), bars=90)
    assert len(svg.encode()) < 25_000


def test_chart_panel_json():
    df = make_candles(300, seed=4, freq="4h")
    panel = chart_panel("GOLD", df.iloc[:-1], "4h")
    assert panel["symbol"] == "GOLD" and panel["interval"] == "4h"
    ET.fromstring(panel["svg"])
    json.dumps({k: v for k, v in panel.items() if k != "svg"})
