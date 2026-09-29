"""Filter 2: attention gap.

Four measures from the spec, each ranked *relative to market cap* (residual of
log(1 + measure) on log(market cap) across the names being ranked), averaged
into a composite percentile where 0 = least attention.

Historical (point-in-time) coverage of these measures is only available from
paid vendors (I/B/E/S analyst counts, OptionMetrics volume, archived social
data). Sources, in priority order:

  1. data/manual/attention.csv  (ticker,date,measure,value) — drop vendor
     exports here; the latest row dated on or before the screening date and no
     more than 120 days older than it is used.
  2. Free sources that are point-in-time: GDELT article counts (news), and the
     X full-archive counts endpoint if X_BEARER_TOKEN is set (social).
  3. Free sources that only describe *today*: Yahoo analyst count and option
     volume, Reddit search. Used only when the screening date is within 10 days
     of today, never in backtests.
  4. Share turnover (average shares traded / shares outstanding), a standard
     academic attention proxy that is always point-in-time. With
     use_turnover_proxy="auto" it is added whenever fewer than two of the four
     primary measures are available.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .config import CACHE_DIR, MANUAL_DIR, ScreenConfig

MEASURES = ("analysts", "news_90d", "social_90d", "options_ratio")
LIVE_WINDOW_DAYS = 10
_SUFFIX = re.compile(r"[,.]?\s+(inc|corp|corporation|co|company|holdings|group|ltd|plc|n\.?v|s\.?a|lp|llc)\.?$", re.I)


def clean_company_name(name: str) -> str:
    n = (name or "").strip()
    for _ in range(3):
        n = _SUFFIX.sub("", n).strip(" ,.")
    return n.replace("/DE", "").replace("/", " ").strip()


def _is_live(as_of: pd.Timestamp) -> bool:
    return abs((pd.Timestamp.now().normalize() - as_of).days) <= LIVE_WINDOW_DAYS


class ManualSource:
    def __init__(self, path: Path = MANUAL_DIR / "attention.csv"):
        self.df = pd.read_csv(path, parse_dates=["date"]) if path.exists() else pd.DataFrame(
            columns=["ticker", "date", "measure", "value"])

    def get(self, ticker: str, measure: str, as_of: pd.Timestamp) -> float:
        d = self.df[(self.df["ticker"] == ticker) & (self.df["measure"] == measure)
                    & (self.df["date"] <= as_of) & (self.df["date"] > as_of - pd.Timedelta(days=120))]
        return float(d.sort_values("date")["value"].iloc[-1]) if len(d) else np.nan


class _Cached:
    def __init__(self, name: str):
        self.path = CACHE_DIR / "attention" / f"{name}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = json.loads(self.path.read_text()) if self.path.exists() else {}

    def memo(self, key: str, fn):
        if key not in self.cache:
            try:
                self.cache[key] = fn()
            except Exception:
                return np.nan  # do not cache transient failures
            self.path.write_text(json.dumps(self.cache))
        v = self.cache[key]
        return np.nan if v is None else float(v)


class GdeltNews(_Cached):
    """Article count mentioning the company name in the 90 days to the screening date."""
    URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(self):
        super().__init__("gdelt")

    def get(self, name: str, as_of: pd.Timestamp) -> float:
        q = clean_company_name(name)
        if len(q) < 4:
            return np.nan
        start = as_of - pd.Timedelta(days=90)

        def fetch():
            params = {"query": f'"{q}" sourcelang:english', "mode": "timelinevolraw", "format": "json",
                      "startdatetime": start.strftime("%Y%m%d000000"),
                      "enddatetime": as_of.strftime("%Y%m%d235959")}
            time.sleep(1.0)
            r = requests.get(self.URL, params=params, timeout=60)
            r.raise_for_status()
            series = r.json().get("timeline", [{}])[0].get("data", [])
            return sum(pt.get("value", 0) for pt in series) if series else None
        return self.memo(f"{q}|{as_of.date()}", fetch)


class XCounts(_Cached):
    """Cashtag post count over 90 days via X full-archive counts (needs X_BEARER_TOKEN with archive access)."""
    URL = "https://api.x.com/2/tweets/counts/all"

    def __init__(self):
        super().__init__("x")
        self.token = os.environ.get("X_BEARER_TOKEN")

    def get(self, ticker: str, as_of: pd.Timestamp) -> float:
        if not self.token:
            return np.nan

        def fetch():
            params = {"query": f"${ticker}", "granularity": "day",
                      "start_time": (as_of - pd.Timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z"),
                      "end_time": as_of.strftime("%Y-%m-%dT23:59:59Z")}
            total, headers = 0, {"Authorization": f"Bearer {self.token}"}
            while True:
                r = requests.get(self.URL, params=params, headers=headers, timeout=60)
                r.raise_for_status()
                body = r.json()
                total += body.get("meta", {}).get("total_tweet_count", 0)
                nxt = body.get("meta", {}).get("next_token")
                if not nxt:
                    return total
                params["next_token"] = nxt
        return self.memo(f"{ticker}|{as_of.date()}", fetch)


class LiveSources:
    """Point-in-time only for today: Yahoo analysts/options, Reddit mentions."""

    def analysts(self, ticker: str) -> float:
        import yfinance as yf
        try:
            v = yf.Ticker(ticker).info.get("numberOfAnalystOpinions")
            return float(v) if v is not None else 0.0
        except Exception:
            return np.nan

    def options_ratio(self, ticker: str, stock_volume: float) -> float:
        import yfinance as yf
        try:
            t = yf.Ticker(ticker)
            vol = 0.0
            for exp in t.options:
                ch = t.option_chain(exp)
                vol += ch.calls["volume"].fillna(0).sum() + ch.puts["volume"].fillna(0).sum()
            return float(vol * 100 / stock_volume) if stock_volume else np.nan
        except Exception:
            return np.nan

    def reddit(self, ticker: str, name: str) -> float:
        cutoff = time.time() - 90 * 86400
        q = f'"${ticker}" OR "{clean_company_name(name)}"'
        count, after = 0, None
        try:
            for _ in range(10):
                params = {"q": q, "sort": "new", "limit": 100, "t": "year", **({"after": after} if after else {})}
                r = requests.get("https://www.reddit.com/search.json", params=params, timeout=30,
                                 headers={"User-Agent": "snr-screen/0.1"})
                r.raise_for_status()
                data = r.json()["data"]
                posts = [c["data"] for c in data["children"]]
                recent = [p for p in posts if p["created_utc"] >= cutoff]
                count += len(recent)
                after = data.get("after")
                if not after or len(recent) < len(posts):
                    break
                time.sleep(1.0)
            return float(count)
        except Exception:
            return np.nan


class AttentionCollector:
    def __init__(self, use_network: bool = True):
        self.manual = ManualSource()
        self.use_network = use_network
        if use_network:
            self.gdelt, self.x, self.live = GdeltNews(), XCounts(), LiveSources()

    def collect(self, ticker: str, name: str, as_of: pd.Timestamp, last_volume: float = np.nan) -> dict:
        m = {k: self.manual.get(ticker, k, as_of) for k in MEASURES}
        if not self.use_network:
            return m
        live = _is_live(as_of)
        if np.isnan(m["news_90d"]):
            m["news_90d"] = self.gdelt.get(name, as_of)
        if np.isnan(m["social_90d"]):
            m["social_90d"] = self.x.get(ticker, as_of)
            if np.isnan(m["social_90d"]) and live:
                m["social_90d"] = self.live.reddit(ticker, name)
        if live and np.isnan(m["analysts"]):
            m["analysts"] = self.live.analysts(ticker)
        if live and np.isnan(m["options_ratio"]):
            m["options_ratio"] = self.live.options_ratio(ticker, last_volume)
        return m


def size_adjusted_percentile(values: pd.Series, mcap: pd.Series) -> pd.Series:
    """Percentile (0..1) of attention relative to what a company of that size would get."""
    ok = values.notna() & mcap.notna() & (mcap > 0)
    out = pd.Series(np.nan, index=values.index)
    if ok.sum() < 3:
        return out
    y = np.log1p(values[ok].clip(lower=0))
    x = np.log(mcap[ok])
    if ok.sum() >= 5 and x.std() > 0.05:
        b = np.polyfit(x, y, 1)
        resid = y - np.polyval(b, x)
    else:
        resid = y - x
    out[ok] = resid.rank(pct=True, method="average")
    return out


def filter2(table: pd.DataFrame, cfg: ScreenConfig) -> pd.DataFrame:
    """table: index ticker; columns mcap, turnover and any of MEASURES. Adds percentiles and pass flag."""
    t = table.copy()
    used = [m for m in MEASURES if m in t and t[m].notna().sum() >= 3]
    if cfg.use_turnover_proxy == "always" or (cfg.use_turnover_proxy == "auto" and len(used) < 2):
        used.append("turnover")
    for m in used:
        t[f"{m}_pct"] = size_adjusted_percentile(t[m], t["mcap"])
    pct_cols = [f"{m}_pct" for m in used]
    t["attention_pct"] = t[pct_cols].mean(axis=1) if pct_cols else np.nan
    t["attention_measures"] = ",".join(used)
    t["f2_pass"] = t["attention_pct"] <= cfg.attention_max_pct
    t["f2_reason"] = np.where(t["attention_pct"].isna(), "no attention data",
                              np.where(t["f2_pass"], "pass", "attention too high"))
    return t
