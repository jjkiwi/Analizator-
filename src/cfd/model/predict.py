"""Prognozy na dzis z modelu H5, dziennik prognoz i ocena w przod (Brier na prognozach, ktorym minal horyzont)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .features import HORIZONS, NUMERIC
from .train import Model

LOG_COLUMNS = ["date", "symbol", "h", "p_up", "price", "base_rate"]
SKILLS = ("brak", "słaby", "jest")


def load_model_doc(path: Path | str = "walidacja/model.json") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Brak {p}: najpierw uruchom `cfd model train`.")
    return json.loads(p.read_text(encoding="utf-8"))


def predict_latest(ds: pd.DataFrame, doc: dict, horizons=HORIZONS) -> list[dict]:
    """Prognoza z ostatniego domknietego dnia kazdego instrumentu. skill pochodzi z wyniku testu, nie z prognozy."""
    last = ds.dropna(subset=NUMERIC).sort_values("date").groupby("symbol", sort=True).tail(1)
    out = []
    for h in horizons:
        res = doc["horizons"].get(str(h))
        if not res or "final_model" not in res:
            continue
        model = Model.from_dict(res["final_model"])
        p = model.predict_proba(last)
        rates = res.get("base_rates", {})
        skill = res.get("skill", "brak") if res.get("skill") in SKILLS else "brak"
        for (_, row), pu in zip(last.iterrows(), p):
            out.append({"symbol": row["symbol"], "horizon": int(h), "p_up": round(float(pu), 4),
                        "base_rate": round(float(rates.get(row["symbol"], np.nan)), 4) if row["symbol"] in rates else None,
                        "skill": skill, "date": str(pd.Timestamp(row["date"]).date()), "price": float(row["close"])})
    return out


def write_predictions(items: list[dict], doc: dict, path: Path | str = "reports/prognozy.json") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "model_generated": doc.get("generated"),
               "note": "Prawdopodobieństwo wzrostu ceny za h sesji. skill='brak': model nie jest lepszy od częstości wzrostów.",
               "items": items}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def append_log(items: list[dict], path: Path | str = "walidacja/prognozy_log.csv") -> int:
    """Dopisuje prognozy do dziennika; jeden wpis na (data swiecy, symbol, h) — ponowne uruchomienie nie dubluje. Zwraca liczbe nowych."""
    p = Path(path)
    new = pd.DataFrame([{"date": i["date"], "symbol": i["symbol"], "h": i["horizon"], "p_up": i["p_up"],
                         "price": i["price"], "base_rate": i.get("base_rate")} for i in items], columns=LOG_COLUMNS)
    old = pd.read_csv(p, dtype={"date": str, "symbol": str}) if p.exists() else pd.DataFrame(columns=LOG_COLUMNS)
    key = lambda d: d["date"].astype(str) + "|" + d["symbol"].astype(str) + "|" + d["h"].astype(int).astype(str)  # noqa: E731
    new = new[~key(new).isin(set(key(old)))] if len(old) else new
    if new.empty:
        return 0
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([old, new], ignore_index=True).to_csv(p, index=False)
    return len(new)


def score_log(log: pd.DataFrame, closes: dict[str, pd.Series]) -> dict:
    """Ocena w przod: dla wpisow, ktorym minelo h sesji, wynik y = cena(t+h) > cena(t). Brier modelu i bazy."""
    rows = []
    for _, r in log.iterrows():
        s = closes.get(r["symbol"])
        if s is None:
            continue
        d = pd.Timestamp(r["date"], tz="UTC")
        after = s[s.index > d]
        h = int(r["h"])
        if len(after) < h:
            continue
        y = float(after.iloc[h - 1] > float(r["price"]))
        base = r.get("base_rate")
        rows.append({"date": r["date"], "symbol": r["symbol"], "h": h, "p_up": float(r["p_up"]), "y": y,
                     "base_rate": float(base) if pd.notna(base) else np.nan})
    df = pd.DataFrame(rows)
    out = {"n_logged": int(len(log)), "n_scored": int(len(df)), "horizons": {}}
    for h, g in (df.groupby("h") if len(df) else []):
        bm = float(np.mean((g["p_up"] - g["y"]) ** 2))
        gb = g.dropna(subset=["base_rate"])
        bb = float(np.mean((gb["base_rate"] - gb["y"]) ** 2)) if len(gb) else float("nan")
        out["horizons"][str(int(h))] = {"n": int(len(g)), "brier": bm, "brier_base": bb,
                                        "bss": 1 - bm / bb if bb and not np.isnan(bb) and bb > 0 else float("nan"),
                                        "od": str(g["date"].min()), "do": str(g["date"].max())}
    return out
