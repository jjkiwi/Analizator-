"""Regresja logistyczna z kara L2 (numpy, Newton-Raphson). Standaryzacja liczona wylacznie na danych treningowych."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .features import FEATURES

C_GRID = (0.01, 0.1, 1.0, 10.0)
CLIP = 5.0                       # cechy po standaryzacji przycinane do +-5 odchylen (krypto ma skrajne stopy)
EPS = 1e-6


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


@dataclass
class Model:
    """Model z parametrami standaryzacji z treningu. Wspolczynniki w skali standaryzowanej (porownywalne miedzy oknami)."""
    horizon: int
    C: float
    features: list[str]
    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray
    intercept: float
    n_train: int = 0
    meta: dict = field(default_factory=dict)

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        x = df[self.features].to_numpy(dtype=float)
        return np.clip((x - self.mean) / self.scale, -CLIP, CLIP)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        return _sigmoid(self.transform(df) @ self.coef + self.intercept)

    def to_dict(self) -> dict:
        return {"horizon": self.horizon, "C": self.C, "features": self.features, "mean": self.mean.tolist(),
                "scale": self.scale.tolist(), "coef": self.coef.tolist(), "intercept": self.intercept,
                "n_train": self.n_train, "meta": self.meta}

    @classmethod
    def from_dict(cls, d: dict) -> Model:
        return cls(d["horizon"], d["C"], list(d["features"]), np.asarray(d["mean"]), np.asarray(d["scale"]),
                   np.asarray(d["coef"]), float(d["intercept"]), d.get("n_train", 0), d.get("meta", {}))


def fit_logistic(X: np.ndarray, y: np.ndarray, C: float, max_iter: int = 50, tol: float = 1e-8) -> tuple[np.ndarray, float]:
    """Minimalizuje C * sum(log loss) + 0.5 * |w|^2 (jak scikit-learn); wyraz wolny bez kary."""
    n, k = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    w = np.zeros(k + 1)
    reg = np.ones(k + 1)
    reg[-1] = 0.0
    for _ in range(max_iter):
        p = _sigmoid(Xb @ w)
        grad = C * Xb.T @ (p - y) + reg * w
        H = C * (Xb * (p * (1 - p))[:, None]).T @ Xb + np.diag(reg + 1e-9)
        step = np.linalg.solve(H, grad)
        w -= step
        if np.max(np.abs(step)) < tol:
            break
    return w[:-1], float(w[-1])


def train(df: pd.DataFrame, horizon: int, C: float, features: list[str] | None = None, y: np.ndarray | None = None) -> Model:
    """Uczy model na wierszach df (cel y_h). Srednia i odchylenie liczone tylko z df (danych treningowych)."""
    features = list(features or FEATURES)
    x = df[features].to_numpy(dtype=float)
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale = np.where(scale > EPS, scale, 1.0)
    X = np.clip((x - mean) / scale, -CLIP, CLIP)
    target = df[f"y_{horizon}"].to_numpy(dtype=float) if y is None else np.asarray(y, dtype=float)
    coef, b = fit_logistic(X, target, C)
    return Model(horizon, C, features, mean, scale, coef, b, n_train=len(df))


BASE_MIN_ROWS = 250              # krocej notowany instrument dostaje czestosc z calego zbioru treningowego


def base_rates(train_df: pd.DataFrame, horizon: int) -> dict[str, float]:
    """Poziom bazowy: czestosc wzrostow per instrument z danych treningowych (przy < 250 wierszach: czestosc ogolna).

    Bez tego progu instrument z kilkoma wierszami dostaje baze 0 albo 1 i log loss bazy eksploduje, co sztucznie
    poprawia wynik modelu (znalezione w oknie walk-forward 2018-2020 dla h=20)."""
    y = f"y_{horizon}"
    g = train_df.groupby("symbol")[y].agg(["mean", "size"])
    overall = float(train_df[y].mean())
    return {s: (float(r["mean"]) if r["size"] >= BASE_MIN_ROWS else overall) for s, r in g.iterrows()}


def base_proba(df: pd.DataFrame, rates: dict[str, float], fallback: float) -> np.ndarray:
    return df["symbol"].map(rates).fillna(fallback).to_numpy(dtype=float)
