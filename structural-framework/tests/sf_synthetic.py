"""Synthetic panels for offline tests. Values are made up; only the shapes matter."""
from __future__ import annotations

import numpy as np
import pandas as pd

from sf.config import Config
from sf.ingest.base import finalize
from sf.pit import Panel

FREQ_RULE = {"daily": "B", "weekly": "W-WED", "monthly": "MS", "quarterly": "QS", "annual": "YS"}


def make_series(freq: str, start="1995-01-01", end="2026-09-30", seed=0, drift=0.0002, vol=0.01,
                level=100.0, positive=True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq=FREQ_RULE[freq])
    steps = rng.normal(drift, vol, len(dates))
    vals = level * np.exp(np.cumsum(steps)) if positive else level + np.cumsum(steps)
    return pd.DataFrame({"date": dates, "value": vals})


def synthetic_panel(cfg: Config, skip_manual: bool = True, seed: int = 1) -> Panel:
    series = {}
    for i, (sid, s) in enumerate(cfg.assets.series.items()):
        if skip_manual and s.source == "manual":
            continue
        start = "2014-01-01" if sid == "btc" else "1990-01-01"
        positive = sid not in ("real_10y", "fed_surplus_gdp")
        raw = make_series(s.freq, start=start, seed=seed + i, positive=positive,
                          level=1.0 if not positive else 100.0, vol=0.01 if s.freq == "daily" else 0.03)
        series[sid] = finalize(raw, s.freq, *cfg.lag(s))
    return Panel(series, {k: s.freq for k, s in cfg.assets.series.items()})
