"""§9.1 component tests: information coefficient, Newey-West t-stat, hit rate, quintile spread."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import PassBar


def forward_returns(prices: pd.Series, h: int) -> pd.Series:
    """Return from t to t+h periods on the scoring calendar (monthly by default)."""
    return prices.shift(-h) / prices - 1


def newey_west_t(y: np.ndarray, x: np.ndarray, lags: int) -> float:
    """t-stat of the slope in y = a + b x, with Newey-West (Bartlett) standard errors."""
    n = len(y)
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    u = y - X @ beta
    xu = X * u[:, None]
    S = xu.T @ xu
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = xu[L:].T @ xu[:-L]
        S += w * (G + G.T)
    XtX_inv = np.linalg.inv(X.T @ X)
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(V[1, 1])
    return float(beta[1] / se) if se > 0 else np.nan


def ic_stats(score: pd.Series, fwd: pd.Series, h: int, quintiles: int = 5) -> dict:
    """Spearman IC between score_t and the forward h-period return, with overlap-aware t-stat."""
    d = pd.concat({"s": score, "r": fwd}, axis=1).dropna()
    n = len(d)
    if n < max(24, 3 * h) or d["s"].nunique() < 3:
        return {"n": n, "ic": np.nan, "t_nw": np.nan, "hit_rate": np.nan, "quintile_spread": np.nan}
    rs, rr = d["s"].rank(), d["r"].rank()
    ic = float(np.corrcoef(rs, rr)[0, 1])
    zs, zr = (rs - rs.mean()) / rs.std(), (rr - rr.mean()) / rr.std()
    t = newey_west_t(zr.to_numpy(), zs.to_numpy(), lags=max(h - 1, 0))
    # Hit: a score above neutral (3) is followed by an above-median return, and vice versa.
    signal = np.sign(d["s"] - 3)
    outcome = np.sign(d["r"] - d["r"].median())
    hits = (signal * outcome)[signal != 0]
    q = pd.qcut(d["s"].rank(method="first"), quintiles, labels=False)
    spread = float(d["r"][q == quintiles - 1].mean() - d["r"][q == 0].mean())
    return {"n": n, "ic": ic, "t_nw": t, "hit_rate": float((hits > 0).mean()) if len(hits) else np.nan,
            "quintile_spread": spread}


def ic_table(scores: pd.DataFrame, prices: pd.Series, horizons: list[int], quintiles: int = 5) -> pd.DataFrame:
    """One row per (score column, horizon)."""
    rows = []
    for h in horizons:
        fwd = forward_returns(prices, h)
        for col in scores.columns:
            rows.append({"signal": col, "horizon": h, **ic_stats(scores[col], fwd, h, quintiles)})
    return pd.DataFrame(rows)


def passes(in_sample: dict, out_of_sample: dict, bar: PassBar) -> bool:
    """§9.1: IC >= 0.05 with t >= 2 in sample, and the same sign out of sample."""
    ic, t, oos = in_sample.get("ic"), in_sample.get("t_nw"), out_of_sample.get("ic")
    if any(v is None or np.isnan(v) for v in (ic, t, oos)):
        return False
    return ic >= bar.min_ic and t >= bar.min_t and np.sign(oos) == np.sign(ic)
