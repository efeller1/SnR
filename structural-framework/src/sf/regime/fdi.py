"""§5.2 fiscal dominance index: equal-weighted mean of input percentiles (0-1)."""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..metrics import Ctx, all_inputs, sample_metric
from ..scoring.normalize import rolling_percentile


def fdi_history(cfg: Config, ctx: Ctx, dates: pd.DatetimeIndex) -> pd.DataFrame:
    n = cfg.scoring.normalization
    cols = {}
    for sig in cfg.regimes.fdi_inputs:
        freq = ctx.panel.coarsest_freq(all_inputs(sig.formula, sig.steps))
        x = sample_metric(sig.formula, sig.steps, ctx, dates, cfg.scoring.stale_after_days[freq])
        p = rolling_percentile(x, n.window_years, n.min_years)
        cols[sig.id] = p if sig.direction == 1 else 1 - p
    df = pd.DataFrame(cols, index=dates)
    enough = df.notna().mean(axis=1) > 1 - cfg.scoring.aggregation.max_missing_share - 1e-12
    df["fdi"] = df.mean(axis=1).where(enough)
    hi, lo = cfg.regimes.fdi["fiscal_led_above"], cfg.regimes.fdi["monetary_led_below"]
    df["liquidity_driver"] = df["fdi"].map(
        lambda v: None if pd.isna(v) else "Fiscal-led" if v > hi else "Monetary-led" if v < lo else "Balanced")
    return df
