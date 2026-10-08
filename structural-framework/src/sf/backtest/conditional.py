"""§9.2 regime tests: returns conditional on the regime known at the start of each period."""
from __future__ import annotations

import numpy as np
import pandas as pd


def conditional_returns(returns: pd.DataFrame, labels: pd.Series, periods_per_year: int = 12) -> pd.DataFrame:
    """returns: period returns from t to t+1, indexed by t. labels: regime known at t."""
    rows = []
    for lab, idx in labels.dropna().groupby(labels.dropna()).groups.items():
        r = returns.loc[returns.index.intersection(idx)]
        for a in returns.columns:
            x = r[a].dropna()
            if x.empty:
                continue
            rows.append({"regime": lab, "asset": a, "months": len(x),
                         "ann_return": float((1 + x).prod() ** (periods_per_year / len(x)) - 1),
                         "ann_vol": float(x.std() * np.sqrt(periods_per_year)) if len(x) > 1 else np.nan,
                         "hit_rate": float((x > 0).mean())})
    return pd.DataFrame(rows)


def empirical_matrix(cond: pd.DataFrame, quadrants: list[str]) -> pd.DataFrame:
    """Rank each asset's annualized return across quadrants and map ranks to 1-5.

    Ranking within an asset (down the column) matches how the prior matrix reads: where does this
    asset do best? Quadrants with no data stay NaN.
    """
    m = cond.pivot(index="regime", columns="asset", values="ann_return").reindex(quadrants)
    ranks = m.rank(axis=0)
    n = m.notna().sum(axis=0)
    return 1 + 4 * (ranks - 1) / (n - 1).replace(0, np.nan)
