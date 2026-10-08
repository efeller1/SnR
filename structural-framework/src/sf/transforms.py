"""Construction steps for metrics (§4 'Construction' column).

Every operator takes a Series indexed by observation date and returns a Series. Look-backs are
calendar-based (months / weeks / days / years), so the same operator works on daily, weekly,
monthly, or quarterly data. Rolling windows return NaN until the window is fully covered.

Operators:
  pct_change          x_t / x_{t-n} - 1                          months | weeks | days | years
  annualized_pct_change  (x_t / x_{t-n}) ** (12 / months) - 1    months
  diff                x_t - x_{t-n}                              months | weeks | days | years
  cagr                (x_t / x_{t-n}) ** (1 / years) - 1         years
  rolling_mean        trailing mean                              years | months | days
  rolling_sum         trailing sum                               years | months | days
  mom_12_1            x_{t-1m} / x_{t-12m} - 1
  ma_ratio            x_t / trailing mean                        obs (observations) | days
  deviation_from_mean x_t / trailing mean - 1                    years
  seasonal_deviation  x_t - mean(x one, two, ... n years earlier)    years
  scale               x_t * factor                               factor
  minus_series        x_t - other_t (other = formula + steps)    formula, steps
  rolling_residual    z-score of the latest residual of y ~ a + b·x over a trailing window   x, years
  rolling_r2          R² of that same rolling regression          x, years
  halving_phase       §4.3 Bitcoin halving-phase score (uses the asset's `halving` config)
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd


def offset(params: dict[str, Any]) -> pd.DateOffset:
    for unit in ("years", "months", "weeks", "days"):
        if unit in params:
            return pd.DateOffset(**{unit: params[unit]})
    raise ValueError(f"need one of years/months/weeks/days in {params}")


def at_offset(s: pd.Series, off: pd.DateOffset, tolerance: pd.Timedelta | None = None) -> pd.Series:
    """Value of s as of (date - off), for every date in s.index."""
    prior = s.dropna()
    if prior.empty:
        return pd.Series(np.nan, index=s.index)
    target = (s.index - off).to_numpy(dtype="datetime64[ns]")
    pidx = prior.index.to_numpy(dtype="datetime64[ns]")
    i = np.searchsorted(pidx, target, side="right") - 1
    vals = np.where(i >= 0, prior.to_numpy()[np.clip(i, 0, None)], np.nan)
    if tolerance is not None:
        age = target - pidx[np.clip(i, 0, None)]
        vals = np.where(age <= tolerance.to_timedelta64(), vals, np.nan)
    return pd.Series(vals, index=s.index)


# A lagged lookup must land within ~a quarter of its target, so a gap in the data doesn't
# silently stretch "12 months ago" into "3 years ago".
LOOKBACK_TOLERANCE = pd.Timedelta(days=100)


def _full_window(s: pd.Series, out: pd.Series, off: pd.DateOffset) -> pd.Series:
    first = s.first_valid_index()
    if first is None:
        return out * np.nan
    return out.where(out.index >= first + off)


def _rolling(s: pd.Series, params: dict[str, Any], how: str) -> pd.Series:
    off = offset(params)
    days = (pd.Timestamp("2000-01-01") + off - pd.Timestamp("2000-01-01")).days
    r = s.dropna().rolling(f"{days}D")
    out = (r.mean() if how == "mean" else r.sum()).reindex(s.index)
    return _full_window(s, out, off)


def pct_change(s, p, ctx):
    off = offset(p)
    return s / at_offset(s, off, LOOKBACK_TOLERANCE) - 1


def annualized_pct_change(s, p, ctx):
    off = offset(p)
    return (s / at_offset(s, off, LOOKBACK_TOLERANCE)) ** (12 / p["months"]) - 1


def diff(s, p, ctx):
    off = offset(p)
    return s - at_offset(s, off, LOOKBACK_TOLERANCE)


def cagr(s, p, ctx):
    off = pd.DateOffset(years=p["years"])
    return (s / at_offset(s, off, LOOKBACK_TOLERANCE)) ** (1 / p["years"]) - 1


def rolling_mean(s, p, ctx):
    return _rolling(s, p, "mean")


def rolling_sum(s, p, ctx):
    return _rolling(s, p, "sum")


def mom_12_1(s, p, ctx):
    one, twelve = pd.DateOffset(months=1), pd.DateOffset(months=12)
    tol = pd.Timedelta(days=10)
    return at_offset(s, one, tol) / at_offset(s, twelve, tol) - 1


def ma_ratio(s, p, ctx):
    x = s.dropna()
    if "obs" in p:
        ma = x.rolling(int(p["obs"]), min_periods=int(p["obs"])).mean()
    else:
        ma = x.rolling(f"{int(p['days'])}D").mean()
        ma = _full_window(x, ma, pd.DateOffset(days=int(p["days"])))
    return (x / ma).reindex(s.index)


def deviation_from_mean(s, p, ctx):
    return s / _rolling(s, p, "mean") - 1


def seasonal_deviation(s, p, ctx):
    lags = [at_offset(s, pd.DateOffset(years=k), pd.Timedelta(days=10)) for k in range(1, int(p["years"]) + 1)]
    past = pd.concat(lags, axis=1)
    return (s - past.mean(axis=1)).where(past.notna().all(axis=1))


def scale(s, p, ctx):
    return s * float(p["factor"])


def minus_series(s, p, ctx):
    return s - p["_other"]


def _rolling_regression(y: pd.Series, x: pd.Series, years: float) -> pd.DataFrame:
    """Month-end OLS of y on x over a trailing window. Returns resid_z and r2 per month."""
    m = pd.concat({"y": y, "x": x}, axis=1).dropna().resample("ME").last().dropna()
    n = int(round(years * 12))
    out = pd.DataFrame(index=m.index, columns=["resid_z", "r2"], dtype=float)
    yv, xv = m["y"].to_numpy(), m["x"].to_numpy()
    for i in range(n - 1, len(m)):
        ys, xs = yv[i - n + 1: i + 1], xv[i - n + 1: i + 1]
        X = np.column_stack([np.ones(n), xs])
        beta, *_ = np.linalg.lstsq(X, ys, rcond=None)
        resid = ys - X @ beta
        sd = resid.std(ddof=2)
        ss_tot = ((ys - ys.mean()) ** 2).sum()
        out.iloc[i] = [resid[-1] / sd if sd > 0 else np.nan, 1 - (resid ** 2).sum() / ss_tot if ss_tot > 0 else np.nan]
    return out


def rolling_residual(s, p, ctx):
    return _rolling_regression(s, p["_other"], p["years"])["resid_z"]


def rolling_r2(s, p, ctx):
    return _rolling_regression(s, p["_other"], p["years"])["r2"]


def halving_phase_score(days: float, phases: list[list[float]]) -> float:
    for start, end, s0, s1 in phases:
        if start <= days <= end:
            return s0 if end == start else s0 + (s1 - s0) * (days - start) / (end - start)
    # Gaps between integer day bands (e.g. 365.5) fall to the nearest band start.
    return np.nan


def halving_phase(s, p, ctx):
    cfg = ctx.halving
    if not cfg:
        raise ValueError("halving_phase needs a `halving` block on the asset")
    dates = np.array(pd.to_datetime(cfg["dates"]), dtype="datetime64[ns]")
    idx = s.index.to_numpy(dtype="datetime64[ns]")
    i = np.searchsorted(dates, idx, side="right") - 1
    days = (idx - dates[np.clip(i, 0, None)]) / np.timedelta64(1, "D")
    vals = [halving_phase_score(np.floor(d), cfg["phases"]) if k >= 0 else np.nan for d, k in zip(days, i)]
    return pd.Series(vals, index=s.index).where(s.notna())


OPS: dict[str, Callable[[pd.Series, dict, Any], pd.Series]] = {
    f.__name__: f for f in (pct_change, annualized_pct_change, diff, cagr, rolling_mean, rolling_sum, mom_12_1,
                            ma_ratio, deviation_from_mean, seasonal_deviation, scale, minus_series,
                            rolling_residual, rolling_r2, halving_phase)
}
# Steps whose parameters reference another series, evaluated by sf.metrics before the call.
NEEDS_OTHER = {"minus_series", "rolling_residual", "rolling_r2"}
