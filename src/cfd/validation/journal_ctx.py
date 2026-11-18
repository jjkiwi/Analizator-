"""Hipotezy H15/H16: wynik sygnalow z dziennika wedlug kontekstu (newsy, makro), bledy po skupiskach."""
from __future__ import annotations

import io
import json
import math

import numpy as np
import pandas as pd


def load_journal(csv_text: str) -> pd.DataFrame:
    """Rozliczone sygnaly z eksportu `sygnaly.csv` z rozpakowanym kontekstem."""
    df = pd.read_csv(io.StringIO(csv_text))
    df = df[df["r_result"].notna()].copy()
    ctx = df["context"].fillna("{}").map(json.loads)
    for key in ("news", "macro_next_h"):
        df[key] = ctx.map(lambda c, k=key: c.get(k))
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["cluster"] = df["interval"] + "|" + df["time"].astype(str).str[:13]
    df["r_adj"] = df["r_result"] - df.groupby(["strategy", "interval"])["r_result"].transform("mean")
    return df


def cluster_diff(y: pd.Series, in_a: pd.Series, cluster: pd.Series) -> dict:
    """Roznica srednich grupy A i B (OLS y ~ 1 + A) z bledem odpornym na skupiska (CR1)."""
    y, a, c = y.to_numpy(float), in_a.to_numpy(float), cluster.to_numpy()
    X = np.column_stack([np.ones_like(a), a])
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    e = y - X @ beta
    groups = pd.Series(range(len(y))).groupby(c).indices
    meat = np.zeros((2, 2))
    for idx in groups.values():
        s = X[idx].T @ e[idx]
        meat += np.outer(s, s)
    g, n = len(groups), len(y)
    corr = g / (g - 1) * (n - 1) / (n - 2) if g > 1 else float("nan")
    se = math.sqrt(corr * (xtx_inv @ meat @ xtx_inv)[1, 1])
    return {"diff": float(beta[1]), "t": float(beta[1] / se) if se > 0 else float("nan"),
            "n_a": int(a.sum()), "n_b": int(len(a) - a.sum()), "clusters": g}


def h15(df: pd.DataFrame) -> dict:
    d = df[df["news"].isin(["zgodny", "przeciwny"])]
    out = cluster_diff(d["r_adj"], d["news"] == "zgodny", d["cluster"])
    out["mean_raw_zgodny"] = float(d.loc[d["news"] == "zgodny", "r_result"].mean())
    out["mean_raw_przeciwny"] = float(d.loc[d["news"] == "przeciwny", "r_result"].mean())
    return out


def h16(df: pd.DataFrame, hours: float = 2.0) -> dict:
    d = df[df["macro_next_h"].notna()]
    rest = d["macro_next_h"] >= hours
    out = cluster_diff(d["r_adj"], rest, d["cluster"])
    out["mean_raw_przed"] = float(d.loc[~rest, "r_result"].mean())
    out["mean_raw_reszta"] = float(d.loc[rest, "r_result"].mean())
    return out
