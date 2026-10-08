"""§3.2 composite = weighted mean of component scores (§3.3 weights, per-asset overrides)."""
from __future__ import annotations

import pandas as pd

from .components import weighted_mean_renormalized


def composite_score(components: pd.DataFrame, weights: dict[str, float], max_missing_weight: float) -> pd.Series:
    return weighted_mean_renormalized(components, weights, max_missing_weight, by_count=False)
