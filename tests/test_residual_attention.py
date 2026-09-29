import numpy as np
import pandas as pd

from snr.attention import filter2, size_adjusted_percentile
from snr.config import ScreenConfig
from snr.residual import factor_regression, filter3


def _factors(n=600, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2021-01-01", periods=n)
    return pd.DataFrame(rng.normal(0, 0.01, (n, 6)), index=idx,
                        columns=["mkt", "sector", "size", "value", "momentum", "quality"])


def test_regression_finds_new_idiosyncratic_trend():
    f = _factors()
    rng = np.random.default_rng(2)
    r = 0.3 * f["mkt"] + rng.normal(0, 0.012, len(f))
    r.iloc[-126:] += 0.004   # ~+50% of unexplained return in the last six months
    stats = factor_regression(r, f, f.index[-1], ScreenConfig())
    assert stats["r2"] < 0.35
    assert stats["resid_6m"] > 0.2
    assert stats["resid_prior"] < 0.15


def test_regression_ignores_data_after_as_of():
    f = _factors()
    r = pd.Series(np.random.default_rng(3).normal(0, 0.02, len(f)), index=f.index)
    as_of = f.index[450]
    a = factor_regression(r, f, as_of, ScreenConfig())
    r2 = r.copy()
    r2.iloc[451:] = 0.5
    b = factor_regression(r2, f, as_of, ScreenConfig())
    assert a["resid_6m"] == b["resid_6m"] and a["r2"] == b["r2"]


def test_filter3_rules():
    s = pd.DataFrame({
        "r2":          [0.10, 0.10, 0.50, 0.10, 0.10, 0.10, 0.10],
        "resid_3m":    [0.20, 0.10, 0.30, 0.25, -0.1, 0.01, 0.02],
        "resid_6m":    [0.40, 0.35, 0.50, 0.45, 0.30, 0.01, 0.02],
        "resid_prior": [-0.10, 0.00, 0.00, 0.40, 0.00, 0.00, 0.00],
    }, index=list("ABCDEFG"))
    out = filter3(s, ScreenConfig())
    assert out.loc["C", "f3_reason"].startswith("R2")
    assert out.loc["D", "f3_reason"].startswith("trend not new")
    assert out.loc["E", "f3_reason"] == "recent residual not positive"
    assert out.loc["F", "f3_reason"].startswith("residual not top")
    assert out.loc["A", "f3_pass"]


def test_attention_is_relative_to_market_cap():
    mcap = pd.Series([2e9, 4e9, 8e9, 16e9, 32e9], index=list("ABCDE"))
    analysts = pd.Series([3, 6, 9, 12, 2], index=mcap.index)   # E: huge but barely covered
    pct = size_adjusted_percentile(analysts, mcap)
    assert pct.idxmin() == "E"
    t = filter2(pd.DataFrame({"mcap": mcap, "analysts": analysts, "news_90d": analysts * 10,
                              "turnover": 0.01}), ScreenConfig())
    assert t.loc["E", "f2_pass"] and "turnover" not in t["attention_measures"].iloc[0]
