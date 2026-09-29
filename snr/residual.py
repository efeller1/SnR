"""Filter 3: factor regression and residual (idiosyncratic) returns.

Betas are estimated on the trailing ``reg_window`` days ending at the screening
date. The unexplained return is alpha + epsilon, i.e. r - X @ beta, summed
over each window:

  recent_3m   last ~63 days
  recent_6m   last ~126 days
  prior_12m   the ~252 days *before* the recent 6 months ("is the trend just starting?")

The prior window is scored with the same trailing betas, so nothing after the
screening date is ever used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ScreenConfig


def factor_regression(stock_ret: pd.Series, factors: pd.DataFrame, as_of: pd.Timestamp,
                      cfg: ScreenConfig) -> dict:
    df = pd.concat([stock_ret.rename("r"), factors], axis=1, join="inner").loc[:as_of].dropna()
    out = {"nobs": 0, "r2": np.nan, "resid_3m": np.nan, "resid_6m": np.nan, "resid_prior": np.nan}
    fit = df.tail(cfg.reg_window)
    out["nobs"] = len(fit)
    if len(fit) < cfg.min_obs:
        return out
    X = np.column_stack([np.ones(len(fit)), fit[factors.columns].to_numpy()])
    y = fit["r"].to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ beta
    ss_res = float(((y - fitted) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    out["r2"] = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    out["betas"] = dict(zip(["alpha", *factors.columns], beta))

    span = df.tail(cfg.recent_long + cfg.prior_window)
    unexplained = span["r"] - span[factors.columns].to_numpy() @ beta[1:]
    out["resid_3m"] = float(unexplained.tail(cfg.recent_short).sum())
    out["resid_6m"] = float(unexplained.tail(cfg.recent_long).sum())
    prior = unexplained.iloc[: -cfg.recent_long] if len(unexplained) > cfg.recent_long else unexplained.iloc[:0]
    if len(prior) >= cfg.min_prior_obs:
        out["resid_prior"] = float(prior.sum())
    return out


def filter3(stats: pd.DataFrame, cfg: ScreenConfig) -> pd.DataFrame:
    """stats: one row per ticker with r2, resid_3m, resid_6m, resid_prior. Adds pass/reason columns.

    "Top 30% of the remaining names" is measured on the 6-month residual among
    all names that reached Filter 3 with a valid regression.
    """
    s = stats.copy()
    valid = s["r2"].notna() & s["resid_6m"].notna()
    s["resid_pct"] = np.nan
    s.loc[valid, "resid_pct"] = s.loc[valid, "resid_6m"].rank(pct=True, method="average")
    reasons = []
    for _, row in s.iterrows():
        if not (pd.notna(row["r2"]) and pd.notna(row["resid_6m"])):
            reasons.append("insufficient price history")
        elif row["resid_3m"] <= 0 or row["resid_6m"] <= 0:
            reasons.append("recent residual not positive")
        elif row["resid_pct"] < 1 - cfg.resid_top_pct:
            reasons.append(f"residual not top {cfg.resid_top_pct:.0%}")
        elif row["r2"] >= cfg.max_r2:
            reasons.append(f"R2 {row['r2']:.2f} >= {cfg.max_r2}")
        elif pd.isna(row["resid_prior"]):
            reasons.append("no prior-year history" if cfg.require_prior_history else "pass")
        elif row["resid_prior"] > cfg.prior_resid_max:
            reasons.append(f"trend not new (prior residual {row['resid_prior']:+.0%})")
        else:
            reasons.append("pass")
    s["f3_reason"] = reasons
    s["f3_pass"] = s["f3_reason"] == "pass"
    return s
