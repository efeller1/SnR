"""§3.1 normalization: raw metric -> percentile (0-1) -> score (1-5)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _windows(x: pd.Series, window_years: float, min_years: float):
    """Yield (t, trailing window values incl. x_t) for dates with enough history."""
    valid = x.dropna()
    if valid.empty:
        return
    first = valid.index[0]
    win = pd.DateOffset(months=int(round(window_years * 12)))
    need = first + pd.DateOffset(months=int(round(min_years * 12)))
    for t, v in valid.items():
        if t < need:
            continue
        yield t, v, valid[(valid.index > t - win) & (valid.index <= t)].to_numpy()


def rolling_percentile(x: pd.Series, window_years: float, min_years: float) -> pd.Series:
    """Percentile rank of x_t within its trailing window, 0 = lowest, 1 = highest (ties averaged)."""
    out = pd.Series(np.nan, index=x.index)
    for t, v, w in _windows(x, window_years, min_years):
        n = len(w)
        if n < 2:
            continue
        below, equal = (w < v).sum(), (w == v).sum()
        out[t] = (below + (equal - 1) / 2) / (n - 1)
    return out


def rolling_zscore(x: pd.Series, window_years: float, min_years: float) -> pd.Series:
    out = pd.Series(np.nan, index=x.index)
    for t, v, w in _windows(x, window_years, min_years):
        sd = w.std(ddof=1) if len(w) > 2 else np.nan
        out[t] = (v - w.mean()) / sd if sd and sd > 0 else np.nan
    return out


def percentile_to_score(p: pd.Series, direction: int) -> pd.Series:
    p = p if direction == 1 else 1 - p
    return 1 + 4 * p


def zscore_to_score(z: pd.Series, direction: int, clip: float) -> pd.Series:
    z = (z * direction).clip(-clip, clip)
    return 1 + 4 * (z + clip) / (2 * clip)


def threshold_score(x: pd.Series, thresholds: list[tuple[float, float]]) -> pd.Series:
    """Fixed levels: [(lower_bound, score), ...]. Score of the highest bound <= x; below all -> 1."""
    bounds = sorted(thresholds)
    def f(v):
        if np.isnan(v):
            return np.nan
        s = 1.0
        for b, sc in bounds:
            if v >= b:
                s = sc
        return s
    return x.astype(float).map(f)


def score_metric(x: pd.Series, method: str, direction: int, window_years: float, min_years: float,
                 zclip: float = 2.0, thresholds=None) -> tuple[pd.Series, pd.Series]:
    """Return (percentile, score). `percentile` is NaN for methods that don't produce one."""
    nan = pd.Series(np.nan, index=x.index)
    if method == "percentile":
        p = rolling_percentile(x, window_years, min_years)
        return p, percentile_to_score(p, direction)
    if method == "zscore":
        z = rolling_zscore(x, window_years, min_years)
        return nan, zscore_to_score(z, direction, zclip)
    if method == "threshold":
        return nan, threshold_score(x, thresholds)
    if method == "raw":
        return nan, x.clip(1, 5)
    raise ValueError(method)
