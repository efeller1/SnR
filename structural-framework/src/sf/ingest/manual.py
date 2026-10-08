"""Manual / paid sources: data/manual/<id>.csv with columns date,value[,published].

Covers the sources the spec lists under wgc, eia, imf, tic, cftc and crypto until each gets an
automated downloader (M8). A missing file returns an empty series, so the metric scores NA and its
component renormalizes (§3.2).
"""
from __future__ import annotations

import pandas as pd

from ..config import DATA_DIR, SeriesDef
from .base import COLUMNS, finalize


def fetch(s: SeriesDef, lag: tuple[int, int], sources: dict) -> pd.DataFrame:
    path = DATA_DIR / "manual" / f"{s.id}.csv"
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return finalize(pd.read_csv(path), s.freq, *lag)
