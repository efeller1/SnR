"""§14 control-asset test: the framework should score what the thesis says should lose below the premier assets."""
from __future__ import annotations

import pandas as pd


def controls_test(composite: pd.DataFrame, groups: dict[str, str], prices: pd.DataFrame, cpi: pd.Series | None,
                  forward_years: int, min_share: float, window: pd.DatetimeIndex | None = None) -> dict:
    premier = [a for a, g in groups.items() if g == "premier" and a in composite]
    controls = [a for a, g in groups.items() if g == "control" and a in composite]
    c = composite if window is None else composite.loc[composite.index.intersection(window)]
    p, k = c[premier].mean(axis=1), c[controls].mean(axis=1)
    both = p.notna() & k.notna()
    share = float((k[both] < p[both]).mean()) if both.any() else float("nan")

    h = forward_years * 12
    fwd = prices.shift(-h) / prices - 1
    if cpi is not None:
        infl = cpi.shift(-h) / cpi - 1
        fwd = (1 + fwd).div(1 + infl, axis=0) - 1
    fwd = fwd if window is None else fwd.loc[fwd.index.intersection(window)]
    mean_fwd = fwd.mean()
    ranked = mean_fwd.dropna().sort_values(ascending=False)
    worst_premier = ranked[[a for a in premier if a in ranked]].min() if any(a in ranked for a in premier) else None
    best_control = ranked[[a for a in controls if a in ranked]].max() if any(a in ranked for a in controls) else None
    return {
        "share_months_controls_below": share,
        "passes_score_test": bool(share >= min_share) if both.any() else None,
        "forward_real_returns": ranked.to_dict(),
        "passes_return_test": (bool(best_control < worst_premier)
                               if worst_premier is not None and best_control is not None else None),
    }
