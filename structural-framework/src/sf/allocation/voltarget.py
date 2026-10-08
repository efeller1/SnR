"""§3.5 optional portfolio volatility targeting with an EWMA estimate."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import VolTarget


def ewma_vol(daily_returns: pd.Series, span_days: int) -> pd.Series:
    """Annualized EWMA volatility of daily returns."""
    return np.sqrt(daily_returns.pow(2).ewm(span=span_days, min_periods=span_days).mean() * 252)


def exposure(daily_portfolio_returns: pd.Series, cfg: VolTarget) -> pd.Series:
    """Fraction of the portfolio held in risk assets (the rest in cash) to hit the vol target."""
    vol = ewma_vol(daily_portfolio_returns, cfg.ewma_span_days)
    return (cfg.annual_vol / vol).clip(upper=cfg.max_leverage).fillna(1.0)
