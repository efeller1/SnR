"""Persist a scored history (all dates) for the dashboard and backtests."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .engine import Results


def save_history(res: Results, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    res.metric_values.to_parquet(directory / "metric_values.parquet")
    res.metric_pct.to_parquet(directory / "metric_pct.parquet")
    res.metric_scores.to_parquet(directory / "metric_scores.parquet")
    res.metric_weights.to_parquet(directory / "metric_weights.parquet")
    res.composite.to_parquet(directory / "composite.parquet")
    res.allocation.to_parquet(directory / "allocation.parquet")
    res.prices.to_parquet(directory / "prices.parquet")
    res.regime.astype({c: "object" for c in res.regime.select_dtypes("object")}).to_parquet(directory / "regime.parquet")
    pd.concat(res.components, names=["asset", "date"]).to_parquet(directory / "components.parquet")
    pd.concat(res.stance, names=["asset", "date"]).to_parquet(directory / "stance.parquet")
    return directory


def load_history(directory: Path) -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_parquet(p) for p in directory.glob("*.parquet")}
