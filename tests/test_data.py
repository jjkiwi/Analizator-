from pathlib import Path

import pandas as pd
import pytest

from cfd.data import CandleStore, DataService, DataSourceError, normalize_candles
from cfd.instruments import load_instruments
from cfd.models import Instrument

CONFIG = Path(__file__).parents[1] / "config" / "instruments.yaml"


class Fake:
    intervals = ("1d",)

    def __init__(self, name, df=None):
        self.name, self.df, self.calls = name, df, 0

    def fetch(self, source_symbol, interval, start):
        self.calls += 1
        if self.df is None:
            raise DataSourceError("padlo")
        return self.df if start is None else self.df[self.df.index >= start]


def test_config_loads_with_costs():
    inst = load_instruments(CONFIG)
    assert {"US500", "GOLD", "OIL.WTI", "BITCOIN"} <= set(inst)
    assert inst["US500"].costs.spread_pct > 0
    assert {i.category for i in inst.values()} == {"indices", "commodities", "metals", "crypto"}


def test_normalize_drops_bad_rows(candles):
    raw = candles.rename(columns=str.title).copy()
    raw.iloc[3, raw.columns.get_loc("High")] = 0.0001  # high < low
    out = normalize_candles(pd.concat([raw, raw.iloc[-2:]]))
    assert len(out) == len(candles) - 1
    assert out.index.is_monotonic_increasing and str(out.index.tz) == "UTC"


def test_fallback_cache_and_incremental_update(tmp_path, candles):
    inst = Instrument("X", "x", "indices", {"yahoo": "a", "stooq": "b"})
    broken, good = Fake("yahoo"), Fake("stooq", candles.iloc[:1000])
    svc = DataService({"yahoo": broken, "stooq": good}, CandleStore(tmp_path))

    df, source = svc.update(inst, "1d")
    assert source == "stooq" and len(df) == 1000 and broken.calls == 1

    svc.get(inst, "1d")  # z cache, bez sieci
    assert good.calls == 1

    good.df = candles
    df, _ = svc.update(inst, "1d")
    assert len(df) == len(candles) and df.index.is_unique


def test_no_source_raises(tmp_path):
    svc = DataService({}, CandleStore(tmp_path))
    with pytest.raises(DataSourceError):
        svc.update(Instrument("ZINC", "Cynk", "commodities"), "1d")
