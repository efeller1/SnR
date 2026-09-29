import numpy as np
import pandas as pd

from snr.attention import AttentionCollector
from snr.config import ScreenConfig
from snr.report import write_current, write_validation
from snr.screen import Screener
from snr.validate import run_validation

from synthetic import FakePrices, accelerating_revenue, make_facts, market_frames, price_frame


class FakeSec:
    def submissions(self, cik):
        return {"sic": 6798 if cik == 99 else 8071, "sic_description": "Services-Medical Laboratories"}


def build(n=10):
    days = pd.bdate_range("2019-01-01", "2024-06-30")
    frames, mkt = market_frames(days)
    rng = np.random.default_rng(7)
    facts, tickers = [], []
    as_of = pd.Timestamp("2023-03-31")
    for i in range(n):
        cik, t = 100 + i, f"T{i}"
        facts.append(make_facts(cik, accelerating_revenue(), shares=100e6))
        r = pd.Series(0.2 * mkt.values + rng.normal(0, 0.008, len(days)), index=days)
        # T0 and T5 (the least-traded names) get a fresh idiosyncratic run-up in the last six months
        window = (days > as_of - pd.Timedelta(days=182)) & (days <= as_of)
        if i % 5 == 0:
            r[window] += 0.004
        pre = days[days <= as_of]
        frame = price_frame(r, 50.0, volume=2e6 + 1e6 * (i % 5))
        frame["close"] *= 50.0 / frame.loc[pre[-1], "close"]  # ~$5B market cap at as_of
        frames[t] = frame
        tickers.append({"cik": cik, "ticker": t, "name": f"Company {i} Inc", "exchange": "Nasdaq"})
    facts.append(make_facts(99, accelerating_revenue(), shares=100e6))  # REIT: excluded by SIC
    frames["REIT"] = frames["T0"]
    tickers.append({"cik": 99, "ticker": "REIT", "name": "Some REIT Inc", "exchange": "NYSE"})
    return Screener(pd.concat(facts, ignore_index=True), pd.DataFrame(tickers), FakeSec(),
                    FakePrices(frames), AttentionCollector(use_network=False))


def test_screen_end_to_end(tmp_path):
    s = build()
    res = s.run("2023-03-31", ScreenConfig())
    assert res.counts["filter1"] == 11
    assert res.counts["universe"] == 10          # REIT excluded
    assert 0 < res.counts["filter2"] <= 4        # bottom 40% by turnover
    trace = res.trace.set_index("ticker")
    assert "SIC" in trace.loc["REIT", "reason"]
    # T5 had a chance run-up in the prior year too, so its trend is not "just starting"
    assert list(res.final["ticker"]) == ["T0"]
    assert trace.loc["T5", "reason"].startswith("trend not new")
    assert res.final["resid_6m"].is_monotonic_decreasing
    assert (res.final["r2"] < 0.35).all()
    path = write_current(res, tmp_path, with_descriptions=False)
    text = path.read_text()
    assert "Screen as of 2023-03-31" in text and "T0" in text and "Key risks" in text


def test_validation_end_to_end(tmp_path):
    s = build()
    v = run_validation(s, [pd.Timestamp("2023-03-31")], track="T0")
    assert v["tracked"]["passed"].iloc[0]
    assert v["stats"]["n_scored"] == 1
    assert v["summary"]["spy_12m"].notna().all()
    assert "Validation" in write_validation(v, tmp_path).read_text()
