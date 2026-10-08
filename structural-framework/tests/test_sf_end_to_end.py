import numpy as np
import pandas as pd

from sf.backtest.report import run_report
from sf.config import load_config
from sf.engine import run, scoring_calendar, what_changed
from sf.snapshot import build_snapshot
from sf.trends.load import load_trends
from sf_synthetic import synthetic_panel

CFG = load_config()


def test_full_run_on_synthetic_panel(tmp_path):
    panel = synthetic_panel(CFG)
    dates = scoring_calendar(CFG, "2005-01-31", "2026-09-30")
    res = run(CFG, panel, dates, load_trends())
    t = dates[-1]
    # Scored with FRED + price data only (manual sources missing): EQ still gets a composite.
    assert 1 <= res.composite.loc[t, "EQ"] <= 5
    assert res.regime.loc[t, "quadrant"] in CFG.regimes.prior_matrix
    assert res.allocation.loc[t].sum() == np.float64(1.0) or abs(res.allocation.loc[t].sum() - 1) < 1e-9
    # Components with fewer than half their metrics are NA (e.g. EQ CAP has no data at all).
    assert np.isnan(res.components["EQ"].loc[t, "CAP"])
    # BTC halving phase is a fixed score, not a percentile.
    assert res.metric_scores.loc[t, "btc_halving"] in (2.0, 4.0) or 2 <= res.metric_scores.loc[t, "btc_halving"] <= 4
    snap = build_snapshot(res, CFG, t, load_trends())
    assert snap["config_hash"] == CFG.hash and snap["assets"]["EQ"]["stance"] in ("Overweight", "Neutral", "Underweight")
    assert isinstance(what_changed(res, CFG, "EQ", t), list)
    out = run_report(res, CFG, panel, tmp_path)
    assert out.exists() and (tmp_path / "portfolio.csv").exists() and (tmp_path / "ablation.csv").exists()


def test_scores_at_t_ignore_data_after_t():
    """The whole stack, not just one metric: truncating the panel after t leaves scores at t unchanged."""
    panel = synthetic_panel(CFG)
    t = pd.Timestamp("2015-06-30")
    dates = scoring_calendar(CFG, "2008-01-31", t)
    full = run(CFG, panel, dates)
    from sf.pit import Panel
    cut = Panel({k: v[v["published"] <= t] for k, v in panel.series.items()}, panel.freqs)
    trunc = run(CFG, cut, dates)
    pd.testing.assert_frame_equal(full.composite, trunc.composite)
    pd.testing.assert_frame_equal(full.metric_scores, trunc.metric_scores)
