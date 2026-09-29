import numpy as np
import pandas as pd

from snr.config import ScreenConfig
from snr.fundamentals import accel_streak, filter1, gm_trend, point_in_time, quarterly, snapshot
from snr.sec import REVENUE_TAGS

from synthetic import accelerating_revenue, make_facts


def test_q4_derived_from_annual_minus_quarters():
    rev = [100, 110, 120, 130, 140, 150, 160, 170]
    facts = make_facts(1, rev)
    q = quarterly(point_in_time(facts, pd.Timestamp("2030-01-01")), REVENUE_TAGS)
    assert list(q["val"]) == rev
    # Q4 is only knowable when the 10-K is filed (60 days after year end)
    assert q.iloc[3]["filed"] == pd.Timestamp("2019-12-31") + pd.Timedelta(days=60)


def test_point_in_time_hides_unfiled_quarters():
    facts = make_facts(1, [100.0] * 8)
    q2_2020_end = pd.Timestamp("2020-06-30")
    before = snapshot(facts, q2_2020_end + pd.Timedelta(days=39))
    after = snapshot(facts, q2_2020_end + pd.Timedelta(days=40))
    assert before.latest_end == pd.Timestamp("2020-03-31")
    assert after.latest_end == q2_2020_end


def test_restatement_invisible_until_filed():
    facts = make_facts(1, [100.0] * 8)
    row = facts[(facts["tag"] == "Revenues") & (facts["end"] == "2020-03-31")].copy()
    row["val"] = 999.0
    row["filed"] = pd.Timestamp("2021-06-01")
    facts = pd.concat([facts, row], ignore_index=True)
    early = snapshot(facts, pd.Timestamp("2020-12-01")).revenue
    late = snapshot(facts, pd.Timestamp("2021-07-01")).revenue
    assert early[pd.Timestamp("2020-03-31")] == 100.0
    assert late[pd.Timestamp("2020-03-31")] == 999.0


def test_acceleration_streak():
    assert accel_streak([0.10, 0.12, 0.15, 0.20]) == 2
    assert accel_streak([0.30, 0.25, 0.20, 0.35]) == 1
    assert accel_streak([0.30, 0.25, 0.20]) == 0
    assert accel_streak([np.nan, 0.1, 0.2]) == 0


def test_gm_trend():
    slope, change = gm_trend(pd.Series([0.40, 0.41, 0.42, 0.43]))
    assert slope > 0 and abs(change - 0.03) < 1e-9


def test_filter1_pass_and_margin_failure():
    rev = accelerating_revenue()
    as_of = pd.Timestamp("2022-12-31") + pd.Timedelta(days=61)
    ok, why = filter1(snapshot(make_facts(1, rev), as_of), ScreenConfig())
    assert ok, why
    gm = [0.6] * 12 + [0.60, 0.57, 0.54, 0.50]
    ok, why = filter1(snapshot(make_facts(1, rev, gm=gm), as_of), ScreenConfig())
    assert not ok and "margin" in why


def test_filter1_tightened_needs_two_quarters_of_acceleration():
    rev = accelerating_revenue()
    as_of = pd.Timestamp("2023-03-01")
    f = snapshot(make_facts(1, rev), as_of)
    assert accel_streak(list(f.growth.values)) >= 2
    assert filter1(f, ScreenConfig().tightened())[0]
    flat = [100.0 * 1.035 ** i for i in range(16)]
    flat[-2] = flat[-6] * 1.10  # dip, then a single-quarter jump
    flat[-1] = flat[-5] * 1.35
    f2 = snapshot(make_facts(1, flat), as_of)
    ok, why = filter1(f2, ScreenConfig().tightened())
    assert not ok and "accelerating" in why


def test_price_driven_growth_rejected_when_units_supplied():
    f = snapshot(make_facts(1, accelerating_revenue()), pd.Timestamp("2023-03-01"))
    assert not filter1(f, ScreenConfig(), unit_growth=0.05)[0]
    assert filter1(f, ScreenConfig(), unit_growth=0.35)[0]
