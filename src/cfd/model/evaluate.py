"""Ewaluacja modelu H5 jak przy uczeniu modeli: podzial chronologiczny z zablokowanym testem, walk-forward z oczyszczaniem
i embargiem, metryki (Brier, log loss, AUC, trafnosc, kalibracja, Brier skill), bootstrap blokowy przyrostu nad baza,
wynik per kategoria, stabilnosc wspolczynnikow i test przecieku (model na przetasowanych celach)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURES, HORIZONS
from .train import C_GRID, Model, base_proba, base_rates, train

SPLIT = (0.65, 0.15, 0.20)       # trening / walidacja / test (najnowsze daty)
WF_FOLDS = 5
WF_MIN_TRAIN = 0.40              # walk-forward: pierwsze 40% dat przed testem tylko do treningu
N_BOOT = 2000
ALPHA = 0.05 / len(HORIZONS)     # Bonferroni na dwa horyzonty
LEAK_MAX_SKILL = 0.002
WEAK_P = 0.10                    # etykieta "słaby": wszystkie warunki poza istotnoscia, p < 0,10 (etykieta ekranu, nie kryterium H5)


# ---------- podzialy ----------

def embargo_days(h: int) -> int:
    """Embargo rowne horyzontowi h sesji, wyrazone w dniach kalendarzowych (z zapasem na weekendy i swieta)."""
    return int(math.ceil(h * 7 / 5)) + 3


def train_mask(dates: pd.Series, ends: pd.Series, boundary: pd.Timestamp, h: int, start: pd.Timestamp | None = None) -> np.ndarray:
    """Wiersze treningowe przed granica: cel w pelni znany przed granica minus embargo (oczyszczanie + embargo h)."""
    cut = boundary - pd.Timedelta(days=embargo_days(h))
    m = ends.notna().to_numpy() & (ends < cut).to_numpy()
    if start is not None:
        m &= (dates >= start).to_numpy()
    return m


def chronological_split(ds: pd.DataFrame, h: int, split=SPLIT) -> dict[str, np.ndarray]:
    """Maski train/val/test po datach. Test = najnowsze ~20% dat; miedzy zbiorami oczyszczanie i embargo h."""
    lab = ds[f"y_{h}"].notna().to_numpy()
    days = np.sort(ds.loc[lab, "date"].unique())
    v0 = pd.Timestamp(days[int(len(days) * split[0])])
    t0 = pd.Timestamp(days[int(len(days) * (split[0] + split[1]))])
    d, e = ds["date"], ds[f"end_{h}"]
    tr = train_mask(d, e, v0, h)
    va = lab & (d >= v0).to_numpy() & train_mask(d, e, t0, h)
    te = lab & (d >= t0).to_numpy()
    return {"train": tr, "val": va, "test": te, "pretest": train_mask(d, e, t0, h), "val_start": v0, "test_start": t0}


def walk_forward_splits(ds: pd.DataFrame, h: int, pretest: np.ndarray, folds: int = WF_FOLDS) -> list[tuple[np.ndarray, np.ndarray]]:
    """Okna rozszerzajace sie na danych sprzed testu. Trening okna: cel zakonczony przed poczatkiem okna testowego minus embargo."""
    days = np.sort(ds.loc[pretest, "date"].unique())
    first = int(len(days) * WF_MIN_TRAIN)
    edges = np.linspace(first, len(days), folds + 1).astype(int)
    d, e = ds["date"], ds[f"end_{h}"]
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        start = pd.Timestamp(days[a])
        stop = pd.Timestamp(days[b]) if b < len(days) else None
        te = pretest & (d >= start).to_numpy()
        if stop is not None:
            te &= (d < stop).to_numpy()
        out.append((train_mask(d, e, start, h), te))
    return out


# ---------- metryki ----------

def brier(p, y) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def logloss(p, y) -> float:
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(p, y) -> float:
    """AUC z rang (Mann-Whitney), remisy przez rangi srednie."""
    y = np.asarray(y).astype(bool)
    npos, nneg = int(y.sum()), int((~y).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    ranks = pd.Series(np.asarray(p)).rank(method="average").to_numpy()
    return float((ranks[y].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def reliability(p, y, bins: int = 10) -> list[dict]:
    """Kalibracja w przedzialach kwantylowych prognozy: srednia prognoza vs zaobserwowana czestosc."""
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    if len(p) == 0:
        return []
    q = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    idx = np.clip(np.searchsorted(q, p, side="right") - 1, 0, max(len(q) - 2, 0))
    rows = []
    for b in range(max(len(q) - 1, 1)):
        m = idx == b
        if m.any():
            rows.append({"p_mean": float(p[m].mean()), "freq": float(y[m].mean()), "n": int(m.sum())})
    return rows


def metrics(p, y, pb) -> dict:
    bm, bb = brier(p, y), brier(pb, y)
    return {"n": int(len(y)), "brier": bm, "brier_base": bb, "bss": 1 - bm / bb if bb > 0 else float("nan"),
            "logloss": logloss(p, y), "logloss_base": logloss(pb, y), "logloss_gain": logloss(pb, y) - logloss(p, y),
            "auc": auc(p, y), "auc_base": auc(pb, y), "accuracy": float(np.mean((np.asarray(p) > 0.5) == (np.asarray(y) > 0.5))),
            "up_rate": float(np.mean(y))}


def block_bootstrap_p(diff_by_date: np.ndarray, block: int, n_boot: int = N_BOOT, seed: int = 0) -> float:
    """Jednostronne p dla H0: sredni przyrost <= 0. Bootstrap ruchomych blokow na wycentrowanym szeregu dziennym."""
    x = np.asarray(diff_by_date, dtype=float)
    n = len(x)
    if n < 2 * block:
        return float("nan")
    obs = x.mean()
    xc = x - obs
    rng = np.random.default_rng(seed)
    k = int(math.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_boot, k))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :n]
    means = xc[idx].mean(axis=1)
    return float((1 + np.sum(means >= obs)) / (1 + n_boot))


def daily_gain(ds: pd.DataFrame, p, pb) -> pd.Series:
    """Przyrost Brier nad baza (strata bazy minus strata modelu), usredniony w obrebie dnia."""
    y = ds["y"].to_numpy()
    g = (np.asarray(pb) - y) ** 2 - (np.asarray(p) - y) ** 2
    return pd.Series(g, index=ds["date"].to_numpy()).groupby(level=0).mean().sort_index()


# ---------- ewaluacja ----------

def _fit_eval(ds: pd.DataFrame, h: int, tr: np.ndarray, te: np.ndarray, C: float, y_train=None) -> tuple[Model, np.ndarray, np.ndarray, np.ndarray]:
    dtr, dte = ds[tr], ds[te]
    model = train(dtr, h, C, y=y_train)
    rates = base_rates(dtr, h)
    fallback = float(dtr[f"y_{h}"].mean())
    return model, model.predict_proba(dte), base_proba(dte, rates, fallback), dte[f"y_{h}"].to_numpy()


def evaluate_horizon(ds: pd.DataFrame, h: int, seed: int = 0) -> dict:
    """Pelna ewaluacja dla jednego horyzontu. Test jest uzywany raz, po wyborze C na walidacji."""
    sp = chronological_split(ds, h)
    # 1) wybor sily kary L2 na zbiorze walidacyjnym (model uczony na treningu)
    grid = []
    for C in C_GRID:
        _, p, pb, y = _fit_eval(ds, h, sp["train"], sp["val"], C)
        grid.append({"C": C, **metrics(p, y, pb)})
    C = min(grid, key=lambda r: r["brier"])["C"]

    # 2) walk-forward na danych sprzed testu (oczyszczanie + embargo h)
    wf, coefs = [], []
    for k, (tr, te) in enumerate(walk_forward_splits(ds, h, sp["pretest"])):
        if tr.sum() < 1000 or te.sum() < 100:
            continue
        model, p, pb, y = _fit_eval(ds, h, tr, te, C)
        dte = ds[te]
        wf.append({"fold": k, "od": str(dte["date"].min().date()), "do": str(dte["date"].max().date()),
                   "n_train": int(tr.sum()), **metrics(p, y, pb)})
        coefs.append(model.coef)
    coefs = np.array(coefs)
    stability = []
    if len(coefs):
        mean = coefs.mean(axis=0)
        for j, f in enumerate(FEATURES):
            stability.append({"feature": f, "mean": float(mean[j]), "std": float(coefs[:, j].std()),
                              "same_sign_share": float(np.mean(np.sign(coefs[:, j]) == np.sign(mean[j])))})

    # 3) test zablokowany: model na train+val (sprzed testu, oczyszczone), ocena raz
    model, p, pb, y = _fit_eval(ds, h, sp["pretest"], sp["test"], C)
    dte = ds[sp["test"]].assign(y=y)
    test = metrics(p, y, pb)
    gains = daily_gain(dte, p, pb)
    block = max(2 * h, 20)
    p_boot = block_bootstrap_p(gains.to_numpy(), block, seed=seed)
    ll_gain = (pd.Series(-(y * np.log(np.clip(pb, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - pb, 1e-12, 1)))
                         + (y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1))),
                         index=dte["date"].to_numpy()).groupby(level=0).mean())
    p_boot_ll = block_bootstrap_p(ll_gain.to_numpy(), block, seed=seed + 1)
    per_cat = []
    for cat, g in dte.assign(p=p, pb=pb).groupby("category"):
        per_cat.append({"category": cat, **metrics(g["p"].to_numpy(), g["y"].to_numpy(), g["pb"].to_numpy())})

    # 4) test przecieku: te same dane, cele przetasowane losowo w treningu -> skill na tescie ma byc ~0
    rng = np.random.default_rng(seed + 7)
    y_shuf = rng.permutation(ds.loc[sp["pretest"], f"y_{h}"].to_numpy())
    _, p_l, pb_l, y_l = _fit_eval(ds, h, sp["pretest"], sp["test"], C, y_train=y_shuf)
    leak = metrics(p_l, y_l, pb_l)

    wf_bss = float(np.mean([r["bss"] for r in wf])) if wf else float("nan")
    passed = bool(test["brier"] < test["brier_base"] and p_boot < ALPHA and test["logloss_gain"] > 0
                  and wf_bss > 0 and leak["bss"] <= LEAK_MAX_SKILL)
    if passed:
        skill = "jest"
    elif (test["bss"] > 0 and test["logloss_gain"] > 0 and wf_bss > 0 and leak["bss"] <= LEAK_MAX_SKILL
          and p_boot < WEAK_P):
        skill = "słaby"
    else:
        skill = "brak"
    return {
        "horizon": h, "C": C, "C_grid": grid,
        "split": {"train_do": str(sp["val_start"].date()), "val_od": str(sp["val_start"].date()),
                  "test_od": str(sp["test_start"].date()), "test_do": str(dte["date"].max().date()),
                  "embargo_dni": embargo_days(h), "n_train": int(sp["train"].sum()), "n_val": int(sp["val"].sum()),
                  "n_pretest": int(sp["pretest"].sum()), "n_test": int(sp["test"].sum())},
        "walk_forward": wf, "walk_forward_mean_bss": wf_bss,
        "test": test, "bootstrap": {"block": block, "n_boot": N_BOOT, "p_brier": p_boot, "p_logloss": p_boot_ll,
                                    "mean_daily_gain": float(gains.mean()), "alpha": ALPHA},
        "calibration": reliability(p, y), "calibration_base": reliability(pb, y),
        "per_category": per_cat, "coef_stability": stability,
        "coef_test_model": dict(zip(FEATURES, map(float, model.coef))), "intercept_test_model": model.intercept,
        "leak_test": {"bss": leak["bss"], "auc": leak["auc"], "max_allowed": LEAK_MAX_SKILL, "ok": leak["bss"] <= LEAK_MAX_SKILL},
        "passed": passed, "skill": skill,
    }


def final_model(ds: pd.DataFrame, h: int, C: float) -> tuple[Model, dict[str, float]]:
    """Model do prognoz: wszystkie wiersze z rozliczonym celem, C wybrane na walidacji. Baza: czestosc z tych samych danych."""
    lab = ds[ds[f"y_{h}"].notna()]
    m = train(lab, h, C)
    m.meta = {"data_do": str(lab["date"].max().date())}
    return m, base_rates(lab, h)


def run(ds: pd.DataFrame, horizons=HORIZONS, with_final: bool = True) -> dict:
    out = {"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "hypothesis": "H5",
           "features": FEATURES, "n_rows": int(len(ds)), "n_symbols": int(ds["symbol"].nunique()),
           "data_od": str(ds["date"].min().date()), "data_do": str(ds["date"].max().date()), "horizons": {}}
    for h in horizons:
        res = evaluate_horizon(ds, h)
        if with_final:
            m, rates = final_model(ds, h, res["C"])
            res["final_model"] = m.to_dict()
            res["base_rates"] = rates
        out["horizons"][str(h)] = res
    return out


# ---------- raport ----------

def _f(x, nd=4) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def to_markdown(res: dict) -> str:
    L = [f"# Model przewidywań (H5): raport walidacji", "",
         f"Przeliczono: {res['generated']}. Dane: {res['data_od']} – {res['data_do']}, {res['n_symbols']} instrumentów, "
         f"{res['n_rows']} wierszy (dzień × instrument).", "",
         "Regresja logistyczna z karą L2, cechy przyczynowe na zamknięciu dnia, cel: czy cena za h sesji będzie wyższa. "
         "Poziom bazowy: częstość wzrostów instrumentu w danych treningowych. Brier skill (BSS) > 0 oznacza lepiej niż baza.", "",
         f"Kryterium (zapisane przed testem): na teście Brier < bazy z p < {ALPHA:.3f} (bootstrap blokowy), dodatni przyrost log loss, "
         f"średni BSS walk-forward > 0, model na przetasowanych celach BSS ≤ {LEAK_MAX_SKILL}.", ""]
    for h, r in res["horizons"].items():
        t, s, b = r["test"], r["split"], r["bootstrap"]
        L += [f"## Horyzont {h} sesji: {'PRZESZEDŁ' if r['passed'] else 'NIE PRZESZEDŁ'} (jakość: {r['skill']})", "",
              f"Podział: trening do {s['train_do']} ({s['n_train']} wierszy), walidacja od {s['val_od']} ({s['n_val']}), "
              f"test {s['test_od']} – {s['test_do']} ({s['n_test']}); embargo {s['embargo_dni']} dni. Wybrane C = {r['C']}.", "",
              "| Zbiór | n | Brier | Brier bazy | BSS | log loss | log loss bazy | AUC | trafność | wzrosty |",
              "|---|---|---|---|---|---|---|---|---|---|",
              f"| test | {t['n']} | {_f(t['brier'])} | {_f(t['brier_base'])} | {_f(t['bss'])} | {_f(t['logloss'])} | "
              f"{_f(t['logloss_base'])} | {_f(t['auc'], 3)} | {_f(t['accuracy'], 3)} | {_f(t['up_rate'], 3)} |"]
        for w in r["walk_forward"]:
            L.append(f"| WF {w['od']}–{w['do']} | {w['n']} | {_f(w['brier'])} | {_f(w['brier_base'])} | {_f(w['bss'])} | "
                     f"{_f(w['logloss'])} | {_f(w['logloss_base'])} | {_f(w['auc'], 3)} | {_f(w['accuracy'], 3)} | {_f(w['up_rate'], 3)} |")
        L += ["", f"Bootstrap blokowy (blok {b['block']} dni, {b['n_boot']} losowań): p (Brier) = {_f(b['p_brier'], 3)}, "
              f"p (log loss) = {_f(b['p_logloss'], 3)}. Średni BSS walk-forward: {_f(r['walk_forward_mean_bss'])}. "
              f"Test przecieku (przetasowane cele): BSS = {_f(r['leak_test']['bss'])} ({'OK' if r['leak_test']['ok'] else 'NIE'}).", "",
              "Wynik per kategoria (test):", "", "| Kategoria | n | BSS | AUC | trafność |", "|---|---|---|---|---|"]
        L += [f"| {c['category']} | {c['n']} | {_f(c['bss'])} | {_f(c['auc'], 3)} | {_f(c['accuracy'], 3)} |" for c in r["per_category"]]
        L += ["", "Kalibracja (test, przedziały kwantylowe prognozy):", "", "| średnia prognoza | zaobserwowana częstość | n |", "|---|---|---|"]
        L += [f"| {_f(c['p_mean'], 3)} | {_f(c['freq'], 3)} | {c['n']} |" for c in r["calibration"]]
        top = sorted(r["coef_stability"], key=lambda c: -abs(c["mean"]))[:8]
        L += ["", "Najsilniejsze współczynniki (skala standaryzowana, średnia z okien walk-forward):", "",
              "| cecha | średnia | odch. std | zgodność znaku |", "|---|---|---|---|"]
        L += [f"| {c['feature']} | {_f(c['mean'], 3)} | {_f(c['std'], 3)} | {c['same_sign_share']:.0%} |" for c in top]
        L.append("")
    L += ["Prognozy modelu to prawdopodobieństwa, nie rekomendacje. Jakość „brak” oznacza, że model nie jest lepszy od samej "
          "częstości wzrostów i jego prognozy nie niosą informacji."]
    return "\n".join(L) + "\n"


def write_reports(res: dict, out_dir: Path | str = "walidacja") -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pj, pm = out / "model.json", out / "model.md"
    pj.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    pm.write_text(to_markdown(res), encoding="utf-8")
    return pj, pm
