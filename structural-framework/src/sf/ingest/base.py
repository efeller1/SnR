"""The canonical shape every ingest function returns.

A series is a DataFrame with columns:
  date       observation date (FRED convention: period start for monthly/quarterly/annual)
  value      float
  published  first date the value could have been known (from a vintage, or date + publication lag)
  pit        how `published` was set: "vintage" (real release date) or "lagged" (date + configured lag)
"""
from __future__ import annotations

import pandas as pd

COLUMNS = ["date", "value", "published", "pit"]

_PERIOD_END = {
    "daily": lambda d: d,
    "weekly": lambda d: d,
    "monthly": lambda d: d + pd.offsets.MonthEnd(0),
    "quarterly": lambda d: d + pd.offsets.QuarterEnd(0),
    "annual": lambda d: d + pd.offsets.YearEnd(0),
}


def lagged_publication(dates: pd.Series, freq: str, lag_months: int, lag_days: int = 0) -> pd.Series:
    """Estimated publication date = end of the observation period + lag."""
    d = pd.to_datetime(dates)
    end = _PERIOD_END[freq](d)
    out = end + pd.DateOffset(months=lag_months) if lag_months else end
    return out + pd.Timedelta(days=lag_days)


def finalize(df: pd.DataFrame, freq: str, lag_months: int, lag_days: int = 0) -> pd.DataFrame:
    """Fill in missing publication dates with the lag rule and return the canonical columns."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    if "published" not in df or df["published"].isna().all():
        df["published"] = lagged_publication(df["date"], freq, lag_months, lag_days)
        df["pit"] = "lagged"
    else:
        df["published"] = pd.to_datetime(df["published"])
        missing = df["published"].isna()
        df.loc[missing, "published"] = lagged_publication(df.loc[missing, "date"], freq, lag_months, lag_days)
        df["pit"] = df.get("pit", "vintage")
        df.loc[missing, "pit"] = "lagged"
    # A value can never be known before its observation date.
    df["published"] = df[["published", "date"]].max(axis=1)
    return df.sort_values("date").drop_duplicates("date", keep="last")[COLUMNS].reset_index(drop=True)
