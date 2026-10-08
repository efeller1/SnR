"""§3.2 aggregation of metric scores into component scores."""
from __future__ import annotations

import numpy as np
import pandas as pd


def weighted_mean_renormalized(scores: pd.DataFrame, weights: dict[str, float] | pd.DataFrame,
                               max_missing_share: float, by_count: bool = True) -> pd.Series:
    """Weighted mean across columns, dropping missing values and renormalizing the rest.

    `weights` is a dict (fixed) or a frame shaped like `scores` (time-varying, e.g. gated metrics).
    Returns NaN where more than `max_missing_share` of the inputs are missing (by count when
    `by_count`, else by weight). Inputs with zero weight are ignored entirely, not counted missing.
    """
    if isinstance(weights, dict):
        w = pd.DataFrame({c: float(weights.get(c, 0)) for c in scores.columns}, index=scores.index)
    else:
        w = weights.reindex(index=scores.index, columns=scores.columns).fillna(0.0)
    active = w > 0
    present = scores.notna() & active
    wsum = w.where(present, 0).sum(axis=1)
    out = scores.where(present, 0).mul(w).sum(axis=1) / wsum.replace(0, np.nan)
    n_active = active.sum(axis=1)
    if by_count:
        missing = 1 - present.sum(axis=1) / n_active.replace(0, np.nan)
    else:
        missing = 1 - wsum / w.where(active, 0).sum(axis=1).replace(0, np.nan)
    return out.where(missing <= max_missing_share + 1e-12)


def component_scores(metric_scores: pd.DataFrame, metric_component: dict[str, str],
                     metric_weight: pd.DataFrame | dict[str, float], max_missing_share: float) -> pd.DataFrame:
    """metric_scores: dates x metric ids. metric_weight: static dict, or dates x metric frame (gates)."""
    out = {}
    for comp in sorted(set(metric_component.values())):
        ids = [m for m, c in metric_component.items() if c == comp and m in metric_scores]
        w = metric_weight if isinstance(metric_weight, dict) else metric_weight[ids]
        out[comp] = weighted_mean_renormalized(metric_scores[ids], w, max_missing_share)
    return pd.DataFrame(out, index=metric_scores.index)
