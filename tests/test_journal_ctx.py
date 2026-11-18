import json

import numpy as np
import pandas as pd

from cfd.validation.journal_ctx import cluster_diff, h15, load_journal


def _csv(rows):
    df = pd.DataFrame(rows)
    return df.to_csv(index=False)


def test_cluster_diff_matches_mean_difference():
    rng = np.random.default_rng(0)
    y = pd.Series(rng.normal(0, 1, 400))
    a = pd.Series(np.arange(400) % 2 == 0)
    y[a] += 0.5
    c = pd.Series(np.arange(400) // 4)
    r = cluster_diff(y, a, c)
    assert abs(r["diff"] - (y[a].mean() - y[~a].mean())) < 1e-9
    assert r["t"] > 2 and r["clusters"] == 100


def test_clustering_widens_error_for_duplicated_signals():
    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, 50)
    y = pd.Series(np.repeat(base, 10))           # 10 identycznych sygnalow na skupisko
    a = pd.Series(np.repeat(np.arange(50) % 2 == 0, 10))
    naive = cluster_diff(y, a, pd.Series(range(500)))
    clus = cluster_diff(y, a, pd.Series(np.repeat(range(50), 10)))
    assert abs(clus["t"]) < abs(naive["t"]) / 2


def test_load_journal_demeans_within_strategy():
    rows = []
    for i in range(8):
        news = "zgodny" if i % 2 else "przeciwny"
        rows.append({"symbol": "X", "strategy": "s1" if i < 4 else "s2", "interval": "1h",
                     "time": f"2026-11-1{i}T10:00:00+00:00", "side": 1, "r_result": (5.0 if i < 4 else -5.0),
                     "created_at": "2026-11-18 10:00:00", "context": json.dumps({"news": news, "macro_next_h": 1.0})})
    df = load_journal(_csv(rows))
    assert np.allclose(df["r_adj"], 0)
    assert abs(h15(df)["diff"]) < 1e-12
