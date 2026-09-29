"""Synthetic EDGAR facts and prices for offline tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from snr.market import FACTOR_ETFS, SECTOR_ETFS, PriceStore


def quarter_ends(first: str, n: int) -> list[pd.Timestamp]:
    return list(pd.date_range(first, periods=n, freq="QE"))


def make_facts(cik: int, revenues: list[float], first_q: str = "2019-03-31", gm: list[float] | None = None,
               shares: float = 100e6, lag_days: int = 40, q4_as_annual: bool = True) -> pd.DataFrame:
    """Calendar-year filer. Q1-Q3 in 10-Qs; Q4 only inside the 10-K annual total (like real filers)."""
    ends = quarter_ends(first_q, len(revenues))
    gm = gm or [0.6] * len(revenues)
    rows = []
    for i, (end, rev) in enumerate(zip(ends, revenues)):
        start = pd.Timestamp(end.year, end.month - 2, 1)
        filed = end + pd.Timedelta(days=lag_days)
        cost = rev * (1 - gm[i])
        if end.month == 12 and q4_as_annual:
            fy_start = pd.Timestamp(end.year, 1, 1)
            idx = [j for j, e in enumerate(ends) if e.year == end.year]
            if len(idx) == 4:
                filed = end + pd.Timedelta(days=60)
                rows.append((cik, "Revenues", fy_start, end, sum(revenues[j] for j in idx), "10-K", filed, f"k{i}"))
                rows.append((cik, "CostOfRevenue", fy_start, end,
                             sum(revenues[j] * (1 - gm[j]) for j in idx), "10-K", filed, f"k{i}"))
                rows.append((cik, "EntityCommonStockSharesOutstanding", None, filed - pd.Timedelta(days=5),
                             shares, "10-K", filed, f"k{i}"))
                continue
        rows.append((cik, "Revenues", start, end, rev, "10-Q", filed, f"q{i}"))
        rows.append((cik, "CostOfRevenue", start, end, cost, "10-Q", filed, f"q{i}"))
        rows.append((cik, "NetIncomeLoss", start, end, -0.1 * rev, "10-Q", filed, f"q{i}"))
        rows.append((cik, "EntityCommonStockSharesOutstanding", None, filed - pd.Timedelta(days=5),
                     shares, "10-Q", filed, f"q{i}"))
    df = pd.DataFrame(rows, columns=["cik", "tag", "start", "end", "val", "form", "filed", "accn"])
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c])
    df["tag"] = df["tag"].astype("category")
    df["form"] = df["form"].astype("category")
    return df


def accelerating_revenue(n: int = 16) -> list[float]:
    """Growth ~15% for three years, then accelerating to 25%, 32%, 40%."""
    rev = [100.0 * 1.035 ** i for i in range(n)]
    for k, g in zip(range(n - 3, n), (0.25, 0.32, 0.40)):
        rev[k] = rev[k - 4] * (1 + g)
    return rev


class FakePrices(PriceStore):
    """PriceStore backed by in-memory frames (no network)."""

    def __init__(self, frames: dict[str, pd.DataFrame]):
        self._mem = frames
        self.cache_dir = None

    def get(self, ticker: str) -> pd.DataFrame:
        return self._mem.get(ticker, pd.DataFrame())


def price_frame(returns: pd.Series, start_price: float = 50.0, volume: float = 1e6) -> pd.DataFrame:
    px = start_price * (1 + returns).cumprod()
    return pd.DataFrame({"close": px, "adj_close": px, "volume": volume, "split_factor_after": 1.0})


def market_frames(days: pd.DatetimeIndex, seed: int = 0) -> tuple[dict, pd.Series]:
    rng = np.random.default_rng(seed)
    mkt = pd.Series(rng.normal(0.0004, 0.01, len(days)), index=days)
    frames = {"SPY": price_frame(mkt, 400)}
    for t in sorted(set(FACTOR_ETFS + SECTOR_ETFS) - {"SPY"}):
        frames[t] = price_frame(mkt + pd.Series(rng.normal(0, 0.004, len(days)), index=days), 100)
    return frames, mkt
