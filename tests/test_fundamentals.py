"""Adaptery fundamentow (FRED, EIA, CFTC) na zapisanych probkach prawdziwych odpowiedzi; bez sieci."""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from cfd.data import DataSourceError
from cfd.fundamentals import (CotClient, EiaClient, FredClient, SeriesRouter, component_score, compute_bias,
                              load_components, positioning_percentile, positioning_score)
from cfd.fundamentals import _http, cot, eia, fred

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


@pytest.fixture
def fake_http(monkeypatch):
    """Podmienia httpx.get: `routes` to lista (fragment adresu, status, tresc). Zapisuje wykonane zapytania."""
    routes: list[tuple[str, int, str]] = []
    calls: list[tuple[str, dict]] = []

    def fake_get(url, params=None, **kwargs):
        calls.append((url, dict(params or {})))
        assert "Mozilla" not in kwargs["headers"]["User-Agent"]  # FRED zrywa polaczenie przy UA udajacym przegladarke
        for fragment, status, body in routes:
            if fragment in url:
                return httpx.Response(status, text=body, request=httpx.Request("GET", url))
        raise httpx.ConnectError("brak sieci w testach")

    monkeypatch.setattr(_http.httpx, "get", fake_get)
    monkeypatch.setattr(_http.time, "sleep", lambda s: None)
    return routes, calls


# ---------- FRED ----------

def test_fredgraph_csv_sample():
    s = fred.parse_fredgraph_csv(read("fred_fredgraph_BAMLH0A0HYM2.csv"), "BAMLH0A0HYM2")
    assert s.index[0] == pd.Timestamp("2023-11-10") and s.iloc[0] == 4.03
    assert s.index.is_monotonic_increasing and s.notna().all() and len(s) > 700
    assert s.index[-1] == pd.Timestamp("2026-11-06")


def test_fredgraph_csv_skips_missing_and_rejects_html():
    s = fred.parse_fredgraph_csv("observation_date,DGS10\n2026-01-01,\n2026-01-02,4.5\n", "DGS10")
    assert list(s.items()) == [(pd.Timestamp("2026-01-02"), 4.5)]
    with pytest.raises(DataSourceError):
        fred.parse_fredgraph_csv("<!DOCTYPE html><html>Not found</html>", "WCESTUS1")
    with pytest.raises(DataSourceError):
        fred.parse_fredgraph_csv("observation_date,DGS10\n2026-01-01,\n", "DGS10")


def test_fred_json_parser():
    s = fred.parse_fred_json({"observations": [{"date": "2026-01-02", "value": "."}, {"date": "2026-01-05", "value": "4.1"}]}, "X")
    assert list(s.items()) == [(pd.Timestamp("2026-01-05"), 4.1)]
    with pytest.raises(DataSourceError, match="Bad Request"):
        fred.parse_fred_json({"error_code": 400, "error_message": "Bad Request. The series does not exist."}, "X")


def test_fred_client_without_key_uses_csv(fake_http):
    routes, calls = fake_http
    routes.append(("fredgraph.csv", 200, read("fred_fredgraph_BAMLH0A0HYM2.csv")))
    client = FredClient(api_key="")
    s = client.series("BAMLH0A0HYM2")
    assert len(s) > 700 and client.series("BAMLH0A0HYM2") is s  # drugi raz z pamieci
    assert len(calls) == 1 and calls[0][1]["id"] == "BAMLH0A0HYM2" and "api_key" not in calls[0][1]


def test_fred_client_missing_series_is_clear_error(fake_http):
    routes, _ = fake_http
    routes.append(("fredgraph.csv", 404, "<html>Not Found</html>"))
    with pytest.raises(DataSourceError, match="nie istnieje"):
        FredClient(api_key="").series("WCESTUS1")


def test_fred_client_with_key_uses_api(fake_http):
    routes, calls = fake_http
    routes.append(("api.stlouisfed.org", 200, json.dumps({"observations": [{"date": "2026-01-05", "value": "4.1"}]})))
    assert FredClient(api_key="k").series("DGS10").iloc[-1] == 4.1
    assert calls[0][1]["api_key"] == "k"


def test_http_unreachable_is_data_source_error(fake_http):
    with pytest.raises(DataSourceError, match="brak odpowiedzi"):
        FredClient(api_key="").series("DGS10")


# ---------- EIA ----------

def test_eia_history_page_crude_sample():
    s = eia.parse_eia_history_page(read("eia_hist_WCESTUS1.html"), "PET.WCESTUS1.W")
    assert s.index[-1] == pd.Timestamp("2026-10-30") and s.iloc[-1] == 409760.0
    assert s[pd.Timestamp("2026-08-07")] == 424410.0
    assert s.index.is_monotonic_increasing and s.index.is_unique
    gaps = s.index.to_series().diff().dropna().dt.days
    assert (gaps == 7).all()  # tygodniowa, bez dziur i bez pomylonego roku
    assert s.between(300_000, 600_000).all()


def test_eia_history_page_natgas_sample():
    s = eia.parse_eia_history_page(read("eia_hist_nw2_epg0_swo_r48_bcfw.html"), "NG.NW2_EPG0_SWO_R48_BCF.W")
    assert s.index[-1] == pd.Timestamp("2026-10-30") and s.iloc[-1] == 3801.0
    assert s[pd.Timestamp("2026-10-02")] == 3500.0
    assert (s.index.to_series().diff().dropna().dt.days == 7).all()


def test_eia_history_page_rejects_other_html():
    with pytest.raises(DataSourceError):
        eia.parse_eia_history_page("<html><body>Object moved</body></html>", "PET.X.W")


def test_eia_history_urls():
    assert eia.history_page_url("PET.WCESTUS1.W") == ("https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx", {"n": "PET", "s": "WCESTUS1", "f": "W"})
    assert eia.history_page_url("NG.NW2_EPG0_SWO_R48_BCF.W") == ("https://www.eia.gov/dnav/ng/hist/nw2_epg0_swo_r48_bcfw.htm", None)
    with pytest.raises(DataSourceError):
        eia.history_page_url("WCESTUS1")


def test_eia_api_error_sample_and_data_shape():
    with pytest.raises(DataSourceError, match="API_KEY_MISSING"):
        eia.parse_eia_api(json.loads(read("eia_api_key_missing.json")), "PET.WCESTUS1.W")
    payload = {"response": {"data": [{"period": "2026-10-30", "value": 409760}, {"period": "2026-10-23", "value": "410625"}, {"period": "2026-10-16", "value": None}]}}
    s = eia.parse_eia_api(payload, "PET.WCESTUS1.W")
    assert list(s.items()) == [(pd.Timestamp("2026-10-23"), 410625.0), (pd.Timestamp("2026-10-30"), 409760.0)]


def test_eia_client_falls_back_to_public_page(fake_http):
    routes, calls = fake_http
    routes.append(("api.eia.gov", 403, read("eia_api_key_missing.json")))
    routes.append(("www.eia.gov/dnav/pet", 200, read("eia_hist_WCESTUS1.html")))
    assert EiaClient(api_key="zly-klucz").series("PET.WCESTUS1.W").iloc[-1] == 409760.0
    assert [("api.eia.gov" in u) for u, _ in calls] == [True, False]
    calls.clear()
    assert EiaClient(api_key="").series("PET.WCESTUS1.W").iloc[-1] == 409760.0
    assert len(calls) == 1 and "www.eia.gov" in calls[0][0]  # bez klucza od razu strona publiczna


# ---------- CFTC ----------

def test_cot_sample_net_positions():
    rows = json.loads(read("cftc_disaggregated_088691.json"))
    s = cot.parse_cot_rows(rows, "disaggregated", "088691")
    assert s.index[0] == pd.Timestamp("2021-11-09") and s.iloc[0] == 168133 - 42523
    assert s.index.is_monotonic_increasing and len(s) > 200
    assert positioning_percentile(s) is not None


def test_cot_errors():
    with pytest.raises(DataSourceError, match="no-such-column"):
        cot.parse_cot_rows(json.loads(read("cftc_error.json")), "disaggregated", "088691")
    with pytest.raises(DataSourceError, match="brak raportow"):
        cot.parse_cot_rows([], "legacy", "000000")
    with pytest.raises(DataSourceError):
        CotClient().query("088691", "nieznany")
    with pytest.raises(DataSourceError):
        CotClient().query("0' OR 1=1 --", "legacy")


def test_cot_client_query_and_router(fake_http):
    routes, calls = fake_http
    routes.append(("publicreporting.cftc.gov/resource/72hh-3qpy.json", 200, read("cftc_disaggregated_088691.json")))
    s = SeriesRouter().series("CFTC:disaggregated:088691")
    assert len(s) > 200
    params = calls[0][1]
    assert "cftc_contract_market_code='088691'" in params["$where"] and "m_money_positions_long_all" in params["$select"]
    with pytest.raises(DataSourceError):
        SeriesRouter().series("XYZ:cos")


# ---------- skladowe biasu ----------

def test_positioning_score_is_contrarian_at_extremes():
    up = pd.Series(np.arange(200.0))
    assert positioning_score(up) == -2.0  # rekordowo dluga pozycja spekulantow
    assert positioning_score(-up) == pytest.approx(1.94, abs=0.01)  # rekordowo krotka (percentyl 1/156)
    mid = pd.Series(np.r_[np.arange(199.0), 100.0])
    assert positioning_score(mid) == 0.0
    assert positioning_score(up, sign=-1) == 2.0
    assert positioning_score(up.iloc[:10]) is None
    edge = pd.Series(np.r_[np.arange(155.0), 139.5])  # percentyl ~90.4
    assert -1.2 < positioning_score(edge) <= -1.0


def test_compute_bias_positioning_and_staleness():
    idx = pd.date_range("2023-01-03", periods=200, freq="7D")
    crowded = pd.Series(np.arange(200.0), index=idx)
    now = idx[-1].to_pydatetime().replace(tzinfo=timezone.utc)
    comps = [{"type": "positioning", "series": "CFTC:x", "max_age": 45}]
    bias, details = compute_bias(comps, lambda sid: crowded, now=now)
    assert bias == -2.0 and details[0]["percentile"] == 100.0 and details[0]["type"] == "positioning"
    bias, details = compute_bias(comps, lambda sid: crowded, now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert bias is None and "nieaktualna" in details[0]["error"]
    assert compute_bias([{"type": "dziwny", "series": "x"}], lambda sid: crowded)[0] is None


def test_component_score_yoy_removes_seasonality():
    idx = pd.date_range("2018-01-05", periods=450, freq="7D")
    season = 500 * np.sin(2 * np.pi * np.arange(450) * 7 / 364)
    flat = pd.Series(3000 + season, index=idx)
    assert abs(component_score(flat, 28, sign=-1, transform="yoy")) < 0.2  # sama sezonowosc nie jest sygnalem
    assert abs(component_score(flat, 28, sign=-1)) > 0.5  # bez transformacji sezon udaje sygnal
    glut = flat.copy()
    glut.iloc[-4:] += np.linspace(100, 400, 4)
    assert component_score(glut, 28, sign=-1, transform="yoy") == -2.0
    with pytest.raises(ValueError):
        component_score(flat, 28, 1, transform="cos")


def test_config_components_resolve():
    comps = load_components(ROOT / "config" / "fundamentals.yaml")
    for symbol in ("OIL", "OIL.WTI", "GASOLINE", "NATGAS"):
        kinds = {c.get("type", "change") for c in comps[symbol]}
        assert kinds == {"change", "positioning"}
        assert any(c["series"].startswith("EIA:") for c in comps[symbol])
    gold_pos = [c for c in comps["GOLD"] if c.get("type") == "positioning"][0]
    assert gold_pos["series"] == "CFTC:disaggregated:088691" and gold_pos["max_age"] == 45
    assert not any(c["series"] == "WCESTUS1" for cs in comps.values() for c in cs)  # tej serii nie ma w FRED
    for cs in comps.values():
        for c in cs:
            if c["series"].startswith("CFTC:"):
                report, code = c["series"].split(":")[1:]
                assert report in cot.REPORTS and code


def test_config_positioning_without_contract_fails(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text("components:\n  XYZ:\n    - {type: positioning}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cot_contracts"):
        load_components(p)
