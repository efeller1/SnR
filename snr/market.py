"""Prices (Yahoo Finance via yfinance, cached), market cap, liquidity, sectors and factor returns.

Factors are built from ETFs so they are available daily and up to the
screening date (Ken French data lags by a month or more):

  market   SPY
  sector   sector SPDR minus SPY
  size     IWM minus SPY
  value    IWD minus IWF
  momentum MTUM minus SPY
  quality  QUAL minus SPY
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE_DIR

FACTOR_ETFS = ("SPY", "IWM", "IWD", "IWF", "MTUM", "QUAL")
SECTOR_ETFS = ("XLK", "XLV", "XLF", "XLY", "XLP", "XLI", "XLE", "XLU", "XLB", "XLC", "XLRE")
SECTOR_NAMES = {
    "XLK": "Information Technology", "XLV": "Health Care", "XLF": "Financials",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLI": "Industrials",
    "XLE": "Energy", "XLU": "Utilities", "XLB": "Materials", "XLC": "Communication Services",
    "XLRE": "Real Estate",
}


def sic_to_sector_etf(sic: int | None) -> str:
    """Approximate SIC -> GICS-sector mapping (SIC has no official GICS crosswalk)."""
    if sic is None:
        return "XLI"
    s = int(sic)
    two = s // 100
    if 2830 <= s <= 2836 or 3841 <= s <= 3851 or two == 80 or s in (5047, 5122, 8731, 3826):
        return "XLV"
    if s in (3570, 3571, 3572, 3575, 3576, 3577, 3578, 3579) or 3661 <= s <= 3679 or 7370 <= s <= 7379 \
            or 3823 <= s <= 3829:
        return "XLK"
    if two == 48 or 7810 <= s <= 7841 or 2710 <= s <= 2741:
        return "XLC"
    if two in (13, 29, 12) or 4610 <= s <= 4619:
        return "XLE"
    if two == 49 and not 4950 <= s <= 4959:
        return "XLU"
    if s == 6798 or 6500 <= s <= 6553:
        return "XLRE"
    if 60 <= two <= 67:
        return "XLF"
    if two in (20, 21, 54) or 2840 <= s <= 2844 or 5140 <= s <= 5149:
        return "XLP"
    if two in (10, 14, 24, 26, 28, 32, 33):
        return "XLB"
    if two in (23, 25, 31, 58, 70, 79, 82) or 3711 <= s <= 3716 or s == 3751 or 52 <= two <= 59:
        return "XLY"
    return "XLI"


class PriceStore:
    """Daily OHLCV + split history per ticker, cached as parquet."""

    def __init__(self, cache_dir: Path = CACHE_DIR / "prices", start: str = "2018-06-01"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.start = start
        self._mem: dict[str, pd.DataFrame] = {}

    def _path(self, ticker: str) -> Path:
        return self.cache_dir / f"{ticker.replace('/', '_')}.parquet"

    def get(self, ticker: str) -> pd.DataFrame:
        """Columns: close (split-adjusted), adj_close (total return), volume, split_factor_after."""
        if ticker in self._mem:
            return self._mem[ticker]
        p = self._path(ticker)
        if p.exists() and (pd.Timestamp.now() - pd.Timestamp(p.stat().st_mtime, unit="s")).days < 1:
            df = pd.read_parquet(p)
        else:
            df = self._download(ticker)
            if not df.empty:
                df.to_parquet(p)
            elif p.exists():
                df = pd.read_parquet(p)
        self._mem[ticker] = df
        return df

    def prefetch(self, tickers: list[str]) -> None:
        for t in tickers:
            self.get(t)

    def _download(self, ticker: str) -> pd.DataFrame:
        import yfinance as yf
        try:
            h = yf.Ticker(ticker.replace(".", "-")).history(start=self.start, auto_adjust=False, actions=True)
        except Exception:
            return pd.DataFrame()
        if h is None or h.empty:
            return pd.DataFrame()
        h.index = pd.DatetimeIndex(h.index).tz_localize(None).normalize()
        splits = h.get("Stock Splits", pd.Series(0.0, index=h.index)).replace(0, 1.0)
        # product of splits strictly after each date: converts split-adjusted close back to as-traded
        after = splits[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
        return pd.DataFrame({
            "close": h["Close"], "adj_close": h["Adj Close"], "volume": h["Volume"],
            "split_factor_after": after,
        })

    # --- point-in-time helpers ------------------------------------------------

    def history(self, ticker: str, as_of: pd.Timestamp) -> pd.DataFrame:
        df = self.get(ticker)
        return df.loc[:as_of] if not df.empty else df

    def market_cap(self, ticker: str, as_of: pd.Timestamp, shares: float) -> float:
        h = self.history(ticker, as_of)
        if h.empty or not shares or np.isnan(shares) or (as_of - h.index[-1]).days > 7:
            return np.nan
        row = h.iloc[-1]
        as_traded = row["close"] * row["split_factor_after"]
        return float(as_traded * shares)

    def adv(self, ticker: str, as_of: pd.Timestamp, window: int) -> float:
        h = self.history(ticker, as_of).tail(window)
        if len(h) < window // 2:
            return np.nan
        return float((h["close"] * h["volume"]).mean())

    def turnover(self, ticker: str, as_of: pd.Timestamp, window: int, shares: float) -> float:
        h = self.history(ticker, as_of).tail(window)
        if h.empty or not shares or np.isnan(shares):
            return np.nan
        as_traded_volume = h["volume"] / h["split_factor_after"]
        return float(as_traded_volume.mean() / shares)

    def returns(self, ticker: str) -> pd.Series:
        df = self.get(ticker)
        return df["adj_close"].pct_change().dropna() if not df.empty else pd.Series(dtype=float)

    def forward_return(self, ticker: str, as_of: pd.Timestamp, days: int = 365) -> float:
        df = self.get(ticker)
        if df.empty:
            return np.nan
        start = df.loc[:as_of]
        end = df.loc[:as_of + pd.Timedelta(days=days)]
        if start.empty or end.empty or (as_of - start.index[-1]).days > 7:
            return np.nan
        # Delisted inside the window: return through the last available close.
        return float(end["adj_close"].iloc[-1] / start["adj_close"].iloc[-1] - 1)


def factor_returns(store: PriceStore, sector_etf: str) -> pd.DataFrame:
    r = {t: store.returns(t) for t in set(FACTOR_ETFS) | {sector_etf}}
    df = pd.DataFrame(r).dropna(subset=["SPY"])
    out = pd.DataFrame(index=df.index)
    out["mkt"] = df["SPY"]
    out["sector"] = df[sector_etf] - df["SPY"]
    out["size"] = df["IWM"] - df["SPY"]
    out["value"] = df["IWD"] - df["IWF"]
    out["momentum"] = df["MTUM"] - df["SPY"]
    out["quality"] = df["QUAL"] - df["SPY"]
    return out.dropna()
