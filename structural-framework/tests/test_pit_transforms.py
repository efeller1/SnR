import numpy as np
import pandas as pd
import pytest

from sf.ingest.base import finalize, lagged_publication
from sf.metrics import Ctx, evaluate, sample_metric
from sf.pit import Panel, sample_at
from sf.transforms import halving_phase_score


def test_publication_lags_follow_spec():
    d = pd.Series(pd.to_datetime(["2024-01-01"]))
    assert lagged_publication(d, "monthly", 1)[0] == pd.Timestamp("2024-02-29")     # Jan data -> end of Feb
    assert lagged_publication(d, "quarterly", 2)[0] == pd.Timestamp("2024-05-31")   # Q1 -> end of May
    assert lagged_publication(d, "daily", 0)[0] == pd.Timestamp("2024-01-01")


def test_vintage_dates_kept_and_never_before_observation():
    df = finalize(pd.DataFrame({"date": ["2024-01-01", "2024-04-01"], "value": [1, 2],
                                "published": ["2024-04-25", "2023-01-01"]}), "quarterly", 2)
    assert df["published"].tolist() == [pd.Timestamp("2024-04-25"), pd.Timestamp("2024-04-01")]
    assert (df["pit"] == "vintage").all()


def _monthly_panel(values, start="2010-01-01"):
    dates = pd.date_range(start, periods=len(values), freq="MS")
    df = finalize(pd.DataFrame({"date": dates, "value": values}), "monthly", 1)
    return Panel({"x": df}, {"x": "monthly"})


def test_sample_at_never_sees_unpublished_values():
    panel = _monthly_panel(np.arange(1, 25, dtype=float))
    ev = evaluate("x", [], Ctx(panel))
    s = sample_at(ev["value"], ev.index.to_series(), pd.DatetimeIndex(["2010-02-27", "2010-02-28", "2010-03-31"]))
    # January (value 1) is published at the end of February.
    assert np.isnan(s.iloc[0]) and s.iloc[1] == 1 and s.iloc[2] == 2


def test_future_revisions_do_not_change_past_scores():
    a = np.arange(1, 121, dtype=float)
    b = a.copy()
    b[100:] = 999.0
    dates = pd.date_range("2012-01-31", periods=60, freq="ME")
    steps = [{"op": "pct_change", "months": 12}]
    sa = sample_metric("x", steps, Ctx(_monthly_panel(a)), dates, None)
    sb = sample_metric("x", steps, Ctx(_monthly_panel(b)), dates, None)
    known = dates < pd.Timestamp("2018-06-01")     # obs #100 (May 2018) is published end of June 2018
    pd.testing.assert_series_equal(sa[known], sb[known])


def test_mixed_inputs_use_latest_known_value_of_each():
    q = finalize(pd.DataFrame({"date": ["2019-10-01", "2020-01-01"], "value": [5.0, 10.0]}), "quarterly", 2)
    days = pd.date_range("2020-01-01", "2020-07-01")
    d = finalize(pd.DataFrame({"date": days, "value": np.arange(len(days), dtype=float) + 1}), "daily", 0)
    ctx = Ctx(Panel({"q": q, "d": d}, {"q": "quarterly", "d": "daily"}))
    s = sample_metric("q / d", [], ctx, pd.DatetimeIndex(["2020-05-30", "2020-05-31"]), None)
    # Q4 2019 (published 2020-02-29) on May 30; Q1 2020 from its publication on May 31, both with that day's price.
    assert s.iloc[0] == pytest.approx(5.0 / d.set_index("date").loc["2020-05-30", "value"])
    assert s.iloc[1] == pytest.approx(10.0 / d.set_index("date").loc["2020-05-31", "value"])


def test_stale_values_drop_out():
    panel = _monthly_panel([1.0, 2.0])
    ev = evaluate("x", [], Ctx(panel))
    s = sample_at(ev["value"], ev.index.to_series(), pd.DatetimeIndex(["2010-04-30", "2011-01-31"]), stale_after_days=70,
                  oldest=ev["oldest"])
    assert s.iloc[0] == 2 and np.isnan(s.iloc[1])


def test_transform_ops():
    dates = pd.date_range("2000-01-01", periods=36, freq="MS")
    df = finalize(pd.DataFrame({"date": dates, "value": 100 * 1.01 ** np.arange(36)}), "monthly", 0)
    ctx = Ctx(Panel({"x": df}, {"x": "monthly"}))
    yoy = evaluate("x", [{"op": "pct_change", "months": 12}], ctx)["value"]
    assert yoy.dropna().iloc[0] == pytest.approx(1.01 ** 12 - 1)
    m = evaluate("x", [{"op": "mom_12_1"}], ctx)["value"]
    assert m.dropna().iloc[0] == pytest.approx(1.01 ** 11 - 1)
    c = evaluate("x", [{"op": "cagr", "years": 2}], ctx)["value"]
    assert c.dropna().iloc[0] == pytest.approx(1.01 ** 12 - 1)
    rm = evaluate("x", [{"op": "rolling_mean", "years": 1}], ctx)["value"]
    assert rm.first_valid_index() == pd.Timestamp("2001-01-31")      # monthly lag 0: known at month end
    minus = evaluate("x", [{"op": "minus_series", "formula": "x"}], ctx)["value"]
    assert minus.abs().max() == 0


def test_seasonal_deviation():
    dates = pd.date_range("2000-01-01", periods=48, freq="MS")
    seasonal = np.tile(np.arange(12, dtype=float), 4)
    seasonal[-1] += 5
    ctx = Ctx(Panel({"x": finalize(pd.DataFrame({"date": dates, "value": seasonal}), "monthly", 0)}, {"x": "monthly"}))
    out = evaluate("x", [{"op": "seasonal_deviation", "years": 3}], ctx)["value"].dropna()
    assert out.iloc[-1] == pytest.approx(5) and out.iloc[:-1].abs().max() == 0


def test_rolling_residual_and_r2():
    rng = np.random.default_rng(0)
    dates = pd.date_range("2000-01-31", periods=180, freq="ME")
    x = rng.normal(size=180)
    y = 2 * x + rng.normal(scale=0.1, size=180)
    y[-1] += 3                                         # big positive residual at the end
    p = Panel({"y": finalize(pd.DataFrame({"date": dates, "value": y}), "daily", 0),
               "x": finalize(pd.DataFrame({"date": dates, "value": x}), "daily", 0)}, {})
    r2 = evaluate("y", [{"op": "rolling_r2", "x": "x", "years": 10}], Ctx(p))["value"].dropna()
    z = evaluate("y", [{"op": "rolling_residual", "x": "x", "years": 10}], Ctx(p))["value"].dropna()
    assert r2.iloc[0] > 0.95 and z.iloc[-1] > 3


def test_halving_phase_rule():
    phases = [[0, 365, 4, 4], [366, 550, 2, 2], [551, 900, 2, 4], [901, 100000, 4, 4]]
    assert halving_phase_score(100, phases) == 4
    assert halving_phase_score(400, phases) == 2
    assert halving_phase_score(551, phases) == 2
    assert halving_phase_score(900, phases) == 4
    assert halving_phase_score(725.5, phases) == pytest.approx(3)
    assert halving_phase_score(1000, phases) == 4
    dates = pd.date_range("2024-04-01", "2025-06-01", freq="D")
    btc = finalize(pd.DataFrame({"date": dates, "value": 1.0}), "daily", 0)
    cfg = {"dates": ["2020-05-11", "2024-04-20"], "phases": phases}
    out = evaluate("btc", [{"op": "halving_phase"}], Ctx(Panel({"btc": btc}, {}), halving=cfg))["value"]
    assert out[pd.Timestamp("2024-04-19")] == 4      # day 1439 after the 2020 halving: accumulation
    assert out[pd.Timestamp("2024-04-20")] == 4      # day 0: expansion
    assert out[pd.Timestamp("2025-05-01")] == 2      # day 376: late expansion / topping
