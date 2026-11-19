"""H19: prognoza zmiennosci na h sesji (HAR na zakresie dnia) i porownanie ze wzorcami (20 sesji, EWMA)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

EPS = 1e-8
WINDOWS = (1, 5, 22, 66)
H = 5
LAMBDA = 0.94
FEATURES = [f"lv_{w}" for w in WINDOWS] + ["lr_22"]


def instrument_vol_frame(df: pd.DataFrame, h: int = H) -> pd.DataFrame:
    """Cechy (znane na zamknieciu t) i cel: wariancja stop z sesji t+1..t+h. Wiersz t nie zna przyszlosci."""
    c = df["close"].astype(float)
    r = np.log(c).diff()
    r = r.where(r.abs() <= 0.25)
    r2 = r ** 2
    hl = np.log(df["high"].astype(float) / df["low"].astype(float))
    pk = (hl ** 2) / (4 * math.log(2))
    v = pk.where((hl > 0) & hl.notna(), r2)
    out = pd.DataFrame(index=df.index)
    for w in WINDOWS:
        out[f"lv_{w}"] = np.log(v.rolling(w, min_periods=w).mean() + EPS)
    out["lr_22"] = np.log(r2.rolling(22, min_periods=22).mean() + EPS)
    out["naive"] = h * r2.rolling(20, min_periods=20).mean()
    ew = r2.copy()
    vals, s = r2.to_numpy(), np.nan
    res = np.full(len(vals), np.nan)
    for i, x in enumerate(vals):
        if np.isnan(s):
            if i >= 19 and not np.isnan(vals[i - 19:i + 1]).any():
                s = np.nanmean(vals[i - 19:i + 1])
        elif not np.isnan(x):
            s = LAMBDA * s + (1 - LAMBDA) * x
        res[i] = s
    ew[:] = res
    out["ewma"] = h * ew
    fut = sum(r2.shift(-k) for k in range(1, h + 1))
    out["rv"] = fut
    out["ret_h"] = np.log(c.shift(-h) / c)
    # jakosc danych (jednakowo dla modelu i wzorcow): kurs stojacy tygodniami to brak notowan, nie zerowa zmiennosc
    moved = (r.abs() > 0).astype(float).where(r.notna())
    out["ok_past"] = moved.rolling(22, min_periods=22).sum() >= 15
    out["ok_future"] = sum(moved.shift(-k).fillna(0) for k in range(1, h + 1)) >= 3
    return out


def build(frames: dict[str, pd.DataFrame], h: int = H) -> pd.DataFrame:
    parts = []
    for sym, df in frames.items():
        f = instrument_vol_frame(df, h)
        f["symbol"] = sym
        idx = pd.DatetimeIndex(f.index)
        f["date"] = idx.tz_convert(None) if idx.tz is not None else idx  # daty bez strefy (UTC)
        parts.append(f)
    ds = pd.concat(parts, ignore_index=True)
    ds = ds[ds["ok_past"] & ds["ok_future"]]
    return ds.dropna(subset=FEATURES + ["naive", "ewma", "rv", "ret_h"]).reset_index(drop=True)


class HAR:
    def fit(self, d: pd.DataFrame, h: int = H) -> "HAR":
        X = np.column_stack([np.ones(len(d)), d[FEATURES].to_numpy()])
        y = np.log(d["rv"].to_numpy() / h + EPS)
        self.beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        self.h, self.k = h, 1.0
        self.k = float(np.mean(np.maximum(d["rv"].to_numpy(), EPS) / self.predict(d)))  # skala optymalna dla QLIKE
        return self

    def predict(self, d: pd.DataFrame) -> np.ndarray:
        X = np.column_stack([np.ones(len(d)), d[FEATURES].to_numpy()])
        return self.k * self.h * np.exp(X @ self.beta)


def qlike(rv: np.ndarray, f: np.ndarray) -> np.ndarray:
    x = np.maximum(rv, EPS) / np.maximum(f, EPS)
    return x - np.log(x) - 1


def boot_p(diff: pd.Series, block: int = 20, n: int = 2000, seed: int = 0) -> float:
    """Jednostronne p: odsetek losowan blokowych, w ktorych srednia (strata modelu - strata wzorca) >= 0."""
    a = diff.to_numpy()
    m = len(a)
    rng = np.random.default_rng(seed)
    worse = 0
    for _ in range(n):
        st = rng.integers(0, m - block, size=m // block + 1)
        idx = (st[:, None] + np.arange(block)[None, :]).ravel()[:m]
        worse += a[idx].mean() >= 0
    return worse / n


def compare(train: pd.DataFrame, test: pd.DataFrame, h: int = H) -> dict:
    m = HAR().fit(train, h)
    f = m.predict(test)
    rv = test["rv"].to_numpy()
    loss = pd.DataFrame({"date": test["date"].to_numpy(), "har": qlike(rv, f),
                         "naive": qlike(rv, test["naive"].to_numpy()), "ewma": qlike(rv, test["ewma"].to_numpy())})
    daily = loss.groupby("date").mean()
    best = "naive" if daily["naive"].mean() <= daily["ewma"].mean() else "ewma"
    ztr = train["ret_h"].to_numpy() / np.sqrt(m.predict(train))
    q10, q90 = np.quantile(ztr, [0.1, 0.9])
    zte = test["ret_h"].to_numpy() / np.sqrt(f)
    cover = float(((zte >= q10) & (zte <= q90)).mean())
    return {"n": len(test), "od": str(test["date"].min().date()), "do": str(test["date"].max().date()),
            "qlike_har": float(daily["har"].mean()), "qlike_naive": float(daily["naive"].mean()),
            "qlike_ewma": float(daily["ewma"].mean()), "best_benchmark": best,
            "gain_pct": float(1 - daily["har"].mean() / daily[best].mean()),
            "p": boot_p(daily["har"] - daily[best]), "coverage80": cover, "q10": float(q10), "q90": float(q90),
            "beta": [float(b) for b in m.beta], "k": m.k}


def h19(ds: pd.DataFrame, h: int = H) -> dict:
    embargo = pd.Timedelta(days=10)
    test_start = pd.Timestamp("2022-08-31")
    res = {"test": compare(ds[ds["date"] < pd.Timestamp("2022-08-21")], ds[ds["date"] >= test_start], h)}
    folds = []
    for y0 in (2010, 2013, 2016, 2019, 2022):
        lo, hi = pd.Timestamp(f"{y0}-01-01"), pd.Timestamp(f"{y0 + 3}-01-01")
        tr, te = ds[ds["date"] < lo - embargo], ds[(ds["date"] >= lo) & (ds["date"] < hi)]
        if len(tr) < 1000 or len(te) < 100:  # brak danych w oknie: okno przepada (kryterium wymaga 4 z 5)
            continue
        folds.append(compare(tr, te, h))
    res["folds"] = folds
    t = res["test"]
    wins = sum(f["qlike_har"] < min(f["qlike_naive"], f["qlike_ewma"]) for f in folds)
    res["wins"] = wins
    res["pass"] = bool(t["gain_pct"] > 0 and t["p"] < 0.05 and wins >= 4 and 0.77 <= t["coverage80"] <= 0.83)
    return res


def train_doc(frames: dict[str, pd.DataFrame], h: int = H) -> dict:
    """Ewaluacja H19 i model koncowy (trening na calej historii) do prognoz na ekranie."""
    ds = build(frames, h)
    res = h19(ds, h)
    final = HAR().fit(ds, h)
    z = ds["ret_h"].to_numpy() / np.sqrt(final.predict(ds))
    q10, q90 = np.quantile(z, [0.1, 0.9])
    return {"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "hypothesis": "H19", "h": h,
            "features": FEATURES, "n_rows": len(ds), "n_symbols": int(ds["symbol"].nunique()),
            "data_od": str(ds["date"].min().date()), "data_do": str(ds["date"].max().date()),
            "passed": res["pass"], "evaluation": res,
            "final_model": {"beta": [float(b) for b in final.beta], "k": final.k, "q10": float(q10), "q90": float(q90)}}


def to_markdown(doc: dict) -> str:
    ev, t = doc["evaluation"], doc["evaluation"]["test"]
    lines = [f"# Model zmienności (H19): raport walidacji", "",
             f"Przeliczono: {doc['generated']}. Dane: {doc['data_od']} – {doc['data_do']}, {doc['n_symbols']} instrumentów, "
             f"{doc['n_rows']} wierszy. Horyzont {doc['h']} sesji, strata QLIKE (niższa = lepsza).", "",
             f"## Wynik: {'PRZESZEDŁ' if doc['passed'] else 'NIE PRZESZEDŁ'}", "",
             "| Okres | HAR | 20 sesji | EWMA | zysk wobec lepszego wzorca | p | pokrycie 80% |", "|---|---|---|---|---|---|---|"]
    for name, f in [("test", t)] + [(f"WF {f['od']}–{f['do']}", f) for f in ev["folds"]]:
        lines.append(f"| {name} | {f['qlike_har']:.4f} | {f['qlike_naive']:.4f} | {f['qlike_ewma']:.4f} | {f['gain_pct']:+.1%} | "
                     f"{f['p']:.3f} | {f['coverage80']:.1%} |")
    lines += ["", f"Okna walk-forward wygrane: {ev['wins']} z 5.", ""]
    return "\n".join(lines)


def write(doc: dict, out_dir="walidacja") -> tuple:
    import json
    from pathlib import Path

    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    pj, pm = d / "zmiennosc.json", d / "zmiennosc.md"
    pj.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    pm.write_text(to_markdown(doc), encoding="utf-8")
    return pj, pm


def predict_ranges(frames: dict[str, pd.DataFrame], doc: dict) -> list[dict]:
    """Zakres 80% stopy na h sesji od ostatniego domknietego dnia; 'wzgledem_roku' = prognoza / mediana prognoz z 252 dni."""
    fm, h = doc["final_model"], int(doc["h"])
    m = HAR()
    m.beta, m.k, m.h = np.array(fm["beta"]), fm["k"], h
    out = []
    newest = max(pd.Timestamp(df.index[-1]) for df in frames.values()) if frames else None
    for sym, df in frames.items():
        f = instrument_vol_frame(df, h).dropna(subset=FEATURES)
        # tylko najnowszy dzien z zywymi notowaniami; stary albo stojacy kurs = brak prognozy (nie cicha stara data)
        if f.empty or not bool(f["ok_past"].iloc[-1]) or pd.Timestamp(f.index[-1]) < newest - pd.Timedelta(days=7):
            continue
        var = m.predict(f)
        last, s = f.iloc[-1], float(np.sqrt(var[-1]))
        price = float(df["close"].iloc[-1]) if df.index[-1] == f.index[-1] else float(df.loc[f.index[-1], "close"])
        typical = float(np.median(np.sqrt(var[-252:])))
        out.append({"symbol": sym, "date": str(pd.Timestamp(f.index[-1]).date()), "horizon": h, "price": price,
                    "sigma": round(s, 5), "lo": price * math.exp(fm["q10"] * s), "hi": price * math.exp(fm["q90"] * s),
                    "lo_pct": round(100 * (math.exp(fm["q10"] * s) - 1), 2), "hi_pct": round(100 * (math.exp(fm["q90"] * s) - 1), 2),
                    "vs_year": round(s / typical, 2) if typical > 0 else None, "passed": bool(doc.get("passed"))})
    return out


RANGE_LOG_COLUMNS = ["date", "symbol", "h", "price", "lo", "hi"]


def append_range_log(items: list[dict], path="walidacja/zakresy_log.csv") -> int:
    """Dopisuje zakresy do dziennika (jeden wpis na date swiecy i symbol). Zwraca liczbe nowych."""
    from pathlib import Path

    p = Path(path)
    new = pd.DataFrame([{"date": i["date"], "symbol": i["symbol"], "h": i["horizon"], "price": i["price"], "lo": i["lo"], "hi": i["hi"]}
                        for i in items], columns=RANGE_LOG_COLUMNS)
    old = pd.read_csv(p, dtype={"date": str, "symbol": str}) if p.exists() else pd.DataFrame(columns=RANGE_LOG_COLUMNS)
    key = lambda d: d["date"].astype(str) + "|" + d["symbol"].astype(str)  # noqa: E731
    if len(old):
        new = new[~key(new).isin(set(key(old)))]
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([old, new], ignore_index=True).to_csv(p, index=False)
    return len(new)


def score_range_log(log: pd.DataFrame, closes: dict[str, pd.Series]) -> dict:
    """Ocena w przod: odsetek zamkniec po h sesjach wewnatrz zakresu (cel ok. 80%)."""
    hits, n = 0, 0
    for _, r in log.iterrows():
        c = closes.get(r["symbol"])
        if c is None:
            continue
        idx = pd.DatetimeIndex(c.index)
        idx = idx.tz_convert(None) if idx.tz is not None else idx
        s = pd.Series(c.to_numpy(), index=idx.normalize())
        after = s[s.index > pd.Timestamp(r["date"])]
        if len(after) < int(r["h"]):
            continue
        x = after.iloc[int(r["h"]) - 1]
        n += 1
        hits += int(r["lo"] <= x <= r["hi"])
    return {"n": n, "coverage": hits / n if n else None}
