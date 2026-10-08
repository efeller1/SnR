import numpy as np
import pandas as pd
import pytest

from sf.config import StanceConfig
from sf.scoring.components import component_scores, weighted_mean_renormalized
from sf.scoring.composite import composite_score
from sf.scoring.stance import N, OW, UW, apply_caps, raw_stance, stance_history


def test_missing_metric_renormalizes():
    s = pd.DataFrame({"a": [4.0], "b": [np.nan], "c": [2.0]})
    assert weighted_mean_renormalized(s, {"a": 1, "b": 1, "c": 1}, 0.5).iloc[0] == 3.0


def test_component_na_when_over_half_missing():
    s = pd.DataFrame({"a": [4.0], "b": [np.nan], "c": [np.nan]})
    assert np.isnan(weighted_mean_renormalized(s, {"a": 1, "b": 1, "c": 1}, 0.5).iloc[0])
    s = pd.DataFrame({"a": [4.0], "b": [np.nan]})        # exactly 50% missing is allowed
    assert weighted_mean_renormalized(s, {"a": 1, "b": 1}, 0.5).iloc[0] == 4.0


def test_gated_metric_is_excluded_not_missing():
    idx = pd.date_range("2020-01-31", periods=2, freq="ME")
    scores = pd.DataFrame({"x": [5.0, 5.0], "y": [1.0, 1.0]}, index=idx)
    w = pd.DataFrame({"x": [1.0, 0.0], "y": [1.0, 1.0]}, index=idx)
    out = component_scores(scores, {"x": "VAL", "y": "VAL"}, w, 0.5)
    assert out["VAL"].tolist() == [3.0, 1.0]


def test_composite_uses_weights():
    comps = pd.DataFrame({"STR": [5.0], "REG": [1.0], "CAP": [np.nan]})
    c = composite_score(comps, {"STR": 0.2, "REG": 0.2, "CAP": 0.15}, 0.5)
    assert c.iloc[0] == pytest.approx(3.0)


C = StanceConfig()


def test_plain_thresholds_without_history():
    assert raw_stance(3.6, None, C) == OW
    assert raw_stance(2.4, None, C) == UW
    assert raw_stance(3.0, None, C) == N


def test_hysteresis_band():
    assert raw_stance(3.65, N, C) == N       # crossed 3.6, but not by more than 0.1
    assert raw_stance(3.71, N, C) == OW
    assert raw_stance(3.55, OW, C) == OW     # dipped below 3.6 but within the band
    assert raw_stance(3.49, OW, C) == N
    assert raw_stance(2.35, N, C) == N
    assert raw_stance(2.29, N, C) == UW
    assert raw_stance(2.45, UW, C) == UW
    assert raw_stance(2.51, UW, C) == N
    assert raw_stance(float("nan"), OW, C) == OW


def test_structural_gate_and_veto():
    assert apply_caps(OW, 2.4, 3.0, C)[0] == N
    assert apply_caps(UW, 2.4, 3.0, C)[0] == UW              # the gate only caps upside
    assert apply_caps(OW, 3.0, 1.2, C)[0] == OW              # veto off by default
    assert apply_caps(OW, 3.0, 1.2, StanceConfig(momentum_veto=True))[0] == N


def test_stance_history_keeps_uncapped_state():
    idx = pd.date_range("2020-01-31", periods=4, freq="ME")
    comp = pd.Series([3.8, 3.8, 3.55, 3.55], index=idx)
    strs = pd.Series([3.0, 2.0, 3.0, 3.0], index=idx)
    h = stance_history(comp, strs, pd.Series(3.0, index=idx), C)
    assert h["stance"].tolist() == [OW, N, OW, OW]
    assert h["capped_by"].iloc[1].startswith("structural gate")
