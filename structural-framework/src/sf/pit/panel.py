"""Point-in-time access to the long panel.

The rule everything else relies on: a computed value carries an `available` date, the latest
publication date of any input it used. `sample_at` only returns values whose `available` date is on
or before the scoring date, so no signal can see data that wasn't published yet (§1.3).
Ingested series use their `published` column as the available date.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FREQ_RANK = {"daily": 0, "weekly": 1, "monthly": 2, "quarterly": 3, "annual": 4}


class Panel:
    """Holds every input series in canonical form (date, value, published)."""

    def __init__(self, series: dict[str, pd.DataFrame], freqs: dict[str, str] | None = None):
        self.series = {k: v.sort_values("date").reset_index(drop=True) for k, v in series.items()}
        self.freqs = freqs or {}

    @classmethod
    def from_long(cls, df: pd.DataFrame, freqs: dict[str, str] | None = None) -> "Panel":
        return cls({sid: g.drop(columns="series") for sid, g in df.groupby("series")}, freqs)

    @classmethod
    def load(cls, path: Path, freqs: dict[str, str] | None = None) -> "Panel":
        return cls.from_long(pd.read_parquet(path), freqs)

    def has(self, sid: str) -> bool:
        return sid in self.series and len(self.series[sid]) > 0

    def get(self, sid: str) -> pd.DataFrame:
        return self.series[sid]

    def as_known(self, sid: str, t: pd.Timestamp) -> pd.DataFrame:
        """Rows of a series that were published on or before t."""
        df = self.series[sid]
        return df[df["published"] <= t]

    def coarsest_freq(self, sids: list[str]) -> str:
        fs = [self.freqs.get(s, "daily") for s in sids]
        return max(fs, key=lambda f: FREQ_RANK[f]) if fs else "daily"


def sample_at(values: pd.Series, available: pd.Series, dates: pd.DatetimeIndex,
              stale_after_days: int | None = None, oldest: pd.Series | None = None) -> pd.Series:
    """For each scoring date t, the latest value whose available date is <= t.

    `values`, `available` (and `oldest`) share an index. A value counts as missing once its oldest
    input publication (default: its available date) is more than `stale_after_days` before t.
    """
    oldest = available if oldest is None else oldest
    ok = values.notna() & available.notna()
    v, a = values[ok].to_numpy(), available[ok].to_numpy(dtype="datetime64[ns]")
    o = oldest[ok].to_numpy(dtype="datetime64[ns]")
    if len(v) == 0:
        return pd.Series(np.nan, index=dates)
    order = np.argsort(a, kind="stable")
    v, a, o = v[order], a[order], o[order]
    idx = np.searchsorted(a, dates.to_numpy(dtype="datetime64[ns]"), side="right") - 1
    j = np.clip(idx, 0, None)
    out = np.where(idx >= 0, v[j], np.nan)
    if stale_after_days is not None:
        age = dates.to_numpy(dtype="datetime64[ns]") - o[j]
        out = np.where((idx >= 0) & (age <= np.timedelta64(stale_after_days, "D")), out, np.nan)
    return pd.Series(out.astype(float), index=dates)
