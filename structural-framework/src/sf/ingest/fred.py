"""FRED / ALFRED ingestion.

With FRED_API_KEY set and `vintage: first_release`, values are first releases from ALFRED
(output_type=4) and `published` is the real first-release date. Otherwise the latest values are
used with the configured publication lag, and rows are marked pit="lagged" so reports can say so.
"""
from __future__ import annotations

import io
import os

import pandas as pd
import requests

from ..config import SeriesDef
from .base import finalize


def fetch_latest(series_id: str, url_template: str, timeout: int = 60) -> pd.DataFrame:
    r = requests.get(url_template.format(id=series_id), timeout=timeout)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"].replace(".", None), errors="coerce")
    return df


def fetch_first_release(series_id: str, api_url: str, api_key: str, timeout: int = 120) -> pd.DataFrame:
    params = {
        "series_id": series_id, "api_key": api_key, "file_type": "json",
        "output_type": 4,                       # initial release only
        "realtime_start": "1776-07-04", "realtime_end": "9999-12-31",
    }
    r = requests.get(api_url, params=params, timeout=timeout)
    r.raise_for_status()
    obs = pd.DataFrame(r.json()["observations"])
    obs["value"] = pd.to_numeric(obs["value"].replace(".", None), errors="coerce")
    return pd.DataFrame({"date": obs["date"], "value": obs["value"],
                         "published": pd.to_datetime(obs["realtime_start"]), "pit": "vintage"})


def fetch(s: SeriesDef, lag: tuple[int, int], sources: dict) -> pd.DataFrame:
    key = os.environ.get(sources["fred"]["api_key_env"])
    if s.vintage == "first_release" and key:
        df = fetch_first_release(s.id, sources["fred"]["api_observations"], key)
        # ALFRED's earliest vintages start in the 1990s; older observations fall back to the lag rule.
        early = df["published"] < pd.Timestamp("1991-01-01")
        df.loc[early, ["published", "pit"]] = [pd.NaT, None]
    else:
        df = fetch_latest(s.id, sources["fred"]["graph_csv"])
    return finalize(df, s.freq, *lag)
