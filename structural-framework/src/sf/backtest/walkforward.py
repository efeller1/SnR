"""§9.5 walk-forward splits and the untouched holdout."""
from __future__ import annotations

import pandas as pd


def holdout_split(dates: pd.DatetimeIndex, holdout_years: float) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """(development, holdout). The holdout is the final `holdout_years`; never use it while developing."""
    cut = dates[-1] - pd.DateOffset(months=int(round(holdout_years * 12)))
    return dates[dates <= cut], dates[dates > cut]


def in_out_split(dev: pd.DatetimeIndex, oos_fraction: float) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    k = int(round(len(dev) * (1 - oos_fraction)))
    return dev[:k], dev[k:]


def expanding_folds(dates: pd.DatetimeIndex, first_train_years: int, step_months: int = 12):
    """Yield (train, test) with an expanding train window, re-estimated every `step_months`."""
    start = dates[0] + pd.DateOffset(years=first_train_years)
    edges = pd.date_range(start, dates[-1], freq=pd.DateOffset(months=step_months))
    for lo, hi in zip(edges, list(edges[1:]) + [dates[-1] + pd.Timedelta(days=1)]):
        train, test = dates[dates < lo], dates[(dates >= lo) & (dates < hi)]
        if len(test):
            yield train, test
