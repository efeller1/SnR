"""Robert Shiller's monthly US stock market data (CAPE, real earnings), 1871-present."""
from __future__ import annotations

import io

import pandas as pd
import requests

from ..config import SeriesDef
from .base import finalize

_cache: dict[str, pd.DataFrame] = {}


def load_table(sources: dict) -> pd.DataFrame:
    cfg = sources["shiller"]
    if cfg["url"] not in _cache:
        r = requests.get(cfg["url"], timeout=120)
        r.raise_for_status()
        raw = pd.read_excel(io.BytesIO(r.content), sheet_name=cfg["sheet"], header=None,
                            skiprows=cfg["header_row"] + 1)
        cols = cfg["columns"]
        t = pd.DataFrame({name: raw[i] for name, i in cols.items()})
        t = t[pd.to_numeric(t["date"], errors="coerce").notna()].copy()
        # Shiller dates are YYYY.MM floats; 1871.1 means October.
        ym = t["date"].astype(float).map(lambda v: f"{int(v)}-{round((v - int(v)) * 100):02d}-01")
        t["date"] = pd.to_datetime(ym)
        _cache[cfg["url"]] = t
    return _cache[cfg["url"]]


def fetch(s: SeriesDef, lag: tuple[int, int], sources: dict) -> pd.DataFrame:
    t = load_table(sources)
    lag_months = sources["shiller"]["lag_months"].get(s.id, lag[0])
    return finalize(t[["date", s.id]].rename(columns={s.id: "value"}), s.freq, lag_months, lag[1])
