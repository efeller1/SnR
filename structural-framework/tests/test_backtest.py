import numpy as np
import pandas as pd
import pytest

from sf.backtest.conditional import conditional_returns, empirical_matrix
from sf.backtest.ic import forward_returns, ic_stats, newey_west_t, passes
from sf.backtest.portfolio import backtest, static_weights, summary
from sf.backtest.walkforward import expanding_folds, holdout_split, in_out_split
from sf.config import PassBar

M = pd.date_range("2000-01-31", periods=240, freq="ME")


def test_ic_detects_a_real_signal():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.01, 0.04, 240), index=M)
    prices = (1 + r).cumprod()
    fwd = forward_returns(prices, 1)
    score = 3 + fwd.fillna(0) * 20 + rng.normal(scale=0.05, size=240)   # peeks ahead on purpose
    s = ic_stats(score, fwd, 1)
    assert s["ic"] > 0.8 and s["t_nw"] > 5 and s["quintile_spread"] > 0 and s["hit_rate"] > 0.7
    noise = ic_stats(pd.Series(rng.normal(3, 1, 240), index=M), fwd, 1)
    assert abs(noise["ic"]) < 0.2


def test_newey_west_equals_ols_like_at_lag0():
    rng = np.random.default_rng(1)
    x = rng.normal(size=500)
    y = 0.3 * x + rng.normal(size=500)
    t0, t6 = newey_west_t(y, x, 0), newey_west_t(y, x, 6)
    assert 5 < t0 < 9 and abs(t6 - t0) / t0 < 0.3


def test_pass_bar():
    bar = PassBar()
    assert passes({"ic": 0.06, "t_nw": 2.1}, {"ic": 0.01}, bar)
    assert not passes({"ic": 0.06, "t_nw": 2.1}, {"ic": -0.01}, bar)
    assert not passes({"ic": 0.04, "t_nw": 3}, {"ic": 0.05}, bar)


def test_backtest_costs_and_stats():
    idx = M[:12]
    rets = pd.DataFrame({"A": 0.01, "B": 0.0}, index=idx)
    w = static_weights(idx, {"A": 0.5, "B": 0.5})
    b = backtest(w, rets, 10)
    assert b["turnover"].iloc[0] == 1.0                     # initial purchase
    assert b["return"].iloc[0] == pytest.approx(0.005 - 0.001)
    assert b["turnover"].iloc[1] > 0                         # rebalancing back from drift
    s = summary(b["return"], turnover=b["turnover"])
    assert s["max_drawdown"] == 0 and s["cagr"] > 0


def test_regime_conditional_and_ranks():
    labels = pd.Series(["goldilocks", "stagflation"] * 60, index=M[:120])
    rets = pd.DataFrame({"EQ": np.where(labels == "goldilocks", 0.02, -0.01),
                         "AU": np.where(labels == "goldilocks", -0.01, 0.02)}, index=M[:120])
    c = conditional_returns(rets, labels)
    emp = empirical_matrix(c, ["goldilocks", "reflation", "stagflation", "deflationary_bust"])
    assert emp.loc["goldilocks", "EQ"] == 5 and emp.loc["stagflation", "EQ"] == 1
    assert emp.loc["stagflation", "AU"] == 5 and np.isnan(emp.loc["reflation", "AU"])


def test_walkforward_splits():
    dev, hold = holdout_split(M, 5)
    assert len(hold) == 60 and dev[-1] < hold[0]
    i, o = in_out_split(dev, 0.33)
    assert len(i) + len(o) == len(dev) and i[-1] < o[0]
    folds = list(expanding_folds(dev, 10))
    assert all(tr[-1] < te[0] for tr, te in folds) and len(folds[-1][0]) > len(folds[0][0])
