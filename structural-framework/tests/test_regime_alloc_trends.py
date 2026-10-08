import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sf.allocation.tilt import tilt_weights
from sf.config import AllocationConfig, load_config
from sf.regime.classify import regime_fit
from sf.snapshot import SnapshotExists, write_snapshot
from sf.trends.load import Trend, load_trends
from sf.trends.score import (cycle_score, durability_score, opportunity, opportunity_as_of, score_trend,
                             trend_history)
from sf.universe import Admission, load_admissions, max_rolling_corr, tier_from_tests

CFG = load_config()


def test_config_loads_and_hash_is_stable():
    assert CFG.hash == load_config().hash
    assert CFG.component_weights("EN")["CAP"] == 0.25 and CFG.component_weights("EN")["STR"] == 0.10
    assert sum(CFG.component_weights("EQ").values()) == pytest.approx(1.0)
    assert CFG.window("BTC") == (4, 2) and CFG.window("EQ") == (10, 5)


def test_regime_fit_priors_and_modifiers():
    row = pd.Series({"quadrant": "stagflation", "liquidity_driver": "Fiscal-led", "real_rates": "Restrictive",
                     "global_order": "Fragmenting"})
    reg = regime_fit(row, CFG, ["EQ", "AU", "BTC", "EN", "USD", "LTB"])
    assert reg["AU"] == 5            # 5 + 0.5 - 0.5 + 0.5 = 5.5, clipped to 5
    assert reg["EQ"] == 1            # 1 - 0.5 -> clipped to 1
    assert reg["BTC"] == 2           # 2 + 0.5 - 0.5
    assert reg["USD"] == 2.5         # 3 - 0.5
    assert reg["EN"] == 4
    assert np.isnan(reg["LTB"])      # controls have no prior row
    assert all(np.isnan(v) for v in regime_fit(pd.Series({"quadrant": None}), CFG, ["EQ"]).values())


def test_tilt_formula_and_bounds():
    a = AllocationConfig(base_weights={"EQ": 0.4, "AU": 0.15, "BTC": 0.05, "EN": 0.1, "USD": 0.3})
    neutral = tilt_weights({k: 3.0 for k in a.base_weights}, a)
    assert neutral == pytest.approx(a.base_weights)
    w = tilt_weights({"EQ": 5.0, "AU": 1.0, "BTC": np.nan, "EN": 3.0, "USD": 3.0}, a)
    assert sum(w.values()) == pytest.approx(1.0)
    for k, b in a.base_weights.items():
        assert 0.5 * b - 1e-9 <= w[k] <= 1.5 * b + 1e-9
    assert w["EQ"] > 0.4 and w["AU"] < 0.15


SPEC_TREND = dict(id="ai", name="AI", driver="technology", thesis="t", linked_premier_assets=["EQ", "EN"],
                  durability={"horizon_years": 10, "reversibility": 2, "commitment": 5},
                  capital_cycle_stage="expansion", priced_in=4,
                  history=[{"date": "2026-10-08", "note": "Initial score.",
                            "scores": {"durability": 4.5, "cycle": 3, "priced_in": 4}}])


def test_trend_scoring_matches_spec():
    t = Trend(**SPEC_TREND)
    s = score_trend(t)
    assert s["durability"] == pytest.approx((5 + 4 + 5) / 3)
    assert s["cycle"] == 3
    assert s["opportunity"] == pytest.approx(0.4 * 14 / 3 + 0.35 * 3 + 0.25 * 2)
    assert cycle_score("bust") == 2 and cycle_score("bust", True) == 4
    assert durability_score(t.durability) == s["durability"]
    assert opportunity(5, 5, 1) == 5


def test_trend_history_is_point_in_time():
    t = Trend(**{**SPEC_TREND, "history": [
        {"date": "2020-01-01", "note": "a", "scores": {"durability": 4, "cycle": 5, "priced_in": 1}},
        {"date": "2022-01-01", "note": "b", "capital_cycle_stage": "overbuild", "priced_in": 5}]})
    h = trend_history(t)
    assert h.loc["2022-01-01", "durability"] == 4                  # carried forward
    assert opportunity_as_of(t, "2021-06-30") == pytest.approx(0.4 * 4 + 0.35 * 5 + 0.25 * 5)
    assert opportunity_as_of(t, "2023-01-01") == pytest.approx(0.4 * 4 + 0.35 * 1 + 0.25 * 1)
    assert np.isnan(opportunity_as_of(t, "2019-01-01"))


def test_repo_trend_and_universe_files_validate():
    trends = load_trends()
    assert "ai_infrastructure" in trends
    import yaml
    tmpl = Path(__file__).parents[1] / "config" / "trends" / "historical" / "TEMPLATE.yaml.example"
    assert Trend(**yaml.safe_load(tmpl.read_text())).id == "fiber_internet"
    adm = load_admissions()
    assert tier_from_tests(adm["CU"]) == "premier" or adm["CU"].decision == "satellite"


def test_admission_tiers():
    base = dict(id="X", name="x", mechanism="m", breaks_if=["b"])
    ok = {"A1": "pass", "A2": "pass", "A3": {"years_of_data": 40, "result": "pass"}, "A4": "pass"}
    assert tier_from_tests(Admission(**base, tests=ok)) == "premier"
    dup = {**ok, "max_corr_vs_premier": {"asset": "AU", "value": 0.85}}
    assert tier_from_tests(Admission(**base, tests=dup)) == "satellite"
    short = {**ok, "A3": {"years_of_data": 12, "result": "pass"}}
    assert tier_from_tests(Admission(**base, tests=short)) == "satellite"
    assert tier_from_tests(Admission(**base, digital=True, tests=short)) == "premier"
    assert tier_from_tests(Admission(**base, tests={**ok, "A2": "fail"})) == "watchlist"


def test_max_rolling_corr():
    rng = np.random.default_rng(0)
    a = pd.Series(rng.normal(size=240))
    others = pd.DataFrame({"same": a + rng.normal(scale=0.1, size=240), "noise": rng.normal(size=240)})
    name, c = max_rolling_corr(a, others)
    assert name == "same" and c > 0.9


def test_snapshots_are_append_only(tmp_path):
    p = write_snapshot({"date": "2026-10-08", "x": 1}, tmp_path)
    assert json.loads(p.read_text())["x"] == 1
    with pytest.raises(SnapshotExists):
        write_snapshot({"date": "2026-10-08", "x": 2}, tmp_path)
    assert json.loads(p.read_text())["x"] == 1
