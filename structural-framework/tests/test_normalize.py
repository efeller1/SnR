import numpy as np
import pandas as pd

from sf.scoring.normalize import (percentile_to_score, rolling_percentile, rolling_zscore, score_metric,
                                  threshold_score, zscore_to_score)

M = pd.date_range("2000-01-31", periods=200, freq="ME")


def test_rising_series_scores_top_of_range():
    x = pd.Series(np.arange(200, dtype=float), index=M)
    p = rolling_percentile(x, 10, 5)
    assert p.iloc[:60].isna().all()          # no score before 5 years of history
    assert p.iloc[60:].eq(1.0).all()
    assert percentile_to_score(p, 1).iloc[-1] == 5.0
    assert percentile_to_score(p, -1).iloc[-1] == 1.0


def test_percentile_window_is_trailing_only():
    x = pd.Series(np.arange(200, dtype=float), index=M)
    x2 = x.copy()
    x2.iloc[150:] = -1000                    # changing the future...
    p, p2 = rolling_percentile(x, 10, 5), rolling_percentile(x2, 10, 5)
    pd.testing.assert_series_equal(p.iloc[:150], p2.iloc[:150])   # ...doesn't change the past


def test_percentile_midrank_and_bounds():
    x = pd.Series([1.0] * 70, index=M[:70])
    p = rolling_percentile(x, 10, 5)
    assert p.dropna().eq(0.5).all()          # all ties -> middle


def test_zscore_clip_maps_to_1_5():
    z = pd.Series([-5, -2, 0, 2, 5], dtype=float)
    s = zscore_to_score(z, 1, 2.0)
    assert s.tolist() == [1, 1, 3, 5, 5]
    assert zscore_to_score(z, -1, 2.0).tolist() == [5, 5, 3, 1, 1]


def test_threshold_and_raw():
    x = pd.Series([0.0, 1.0, 2.5, np.nan])
    s = threshold_score(x, [(1.0, 3), (2.0, 5)])
    assert s.iloc[:3].tolist() == [1, 3, 5] and np.isnan(s.iloc[3])
    _, raw = score_metric(pd.Series([0.0, 3.0, 9.0]), "raw", 1, 10, 5)
    assert raw.tolist() == [1, 3, 5]


def test_zscore_needs_history():
    x = pd.Series(np.random.default_rng(0).normal(size=200), index=M)
    z = rolling_zscore(x, 10, 5)
    assert z.iloc[:60].isna().all() and z.iloc[60:].notna().all()
