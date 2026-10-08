"""Daily prices. A CSV in data/manual/prices/<id>.csv (date,value) wins over the download.

Adjusted closes (dividends reinvested) stand in for total return. Market data has no publication lag.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import ROOT, SeriesDef
from .base import finalize


def _safe_name(ticker: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in ticker)


def manual_path(ticker: str, sources: dict) -> Path:
    return ROOT / sources["prices"]["manual_dir"] / f"{_safe_name(ticker)}.csv"


def download(ticker: str, start: str) -> pd.DataFrame:
    import yfinance as yf  # optional dependency

    px = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if px.empty:
        raise RuntimeError(f"no price data for {ticker}")
    close = px["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return pd.DataFrame({"date": close.index.tz_localize(None) if close.index.tz else close.index,
                         "value": close.values})


def fetch(s: SeriesDef, lag: tuple[int, int], sources: dict) -> pd.DataFrame:
    path = manual_path(s.id, sources)
    df = pd.read_csv(path) if path.exists() else download(s.id, sources["prices"]["start"])
    return finalize(df, s.freq, *lag)
