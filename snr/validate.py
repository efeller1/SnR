"""Walk-forward validation: run the screen at each quarter-end and score forward 12-month returns."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ScreenConfig
from .screen import Screener

BENCHMARK = "SPY"  # S&P 500 total return proxy


def quarter_ends(start_year: int, end_year: int) -> list[pd.Timestamp]:
    return list(pd.date_range(f"{start_year}-01-01", f"{end_year}-12-31", freq="QE"))


def run_validation(screener: Screener, dates: list[pd.Timestamp], cfg: ScreenConfig = ScreenConfig(),
                   track: str = "NTRA") -> dict:
    picks, summary, tracked = [], [], []
    for d in dates:
        print(f"screening {d.date()} ...")
        res = screener.run(d, cfg)
        spy = screener.prices.forward_return(BENCHMARK, d)
        for _, r in res.final.iterrows():
            fwd = screener.prices.forward_return(r["ticker"], d)
            picks.append({"date": d.date(), "ticker": r["ticker"], "name": r["name"], "sector": r["sector"],
                          "mcap_bn": r["mcap"] / 1e9, "rev_growth": r["rev_growth"],
                          "attention_pct": r["attention_pct"], "resid_6m": r["resid_6m"], "r2": r["r2"],
                          "fwd_12m": fwd, "spy_12m": spy, "excess": fwd - spy if pd.notna(fwd) else np.nan})
        t = res.trace[res.trace["ticker"] == track] if not res.trace.empty else res.trace
        tracked.append({"date": d.date(), "passed": bool(len(t) and (t["stage"] == "final").any()),
                        "stage": t["stage"].iloc[-1] if len(t) else "not reached (no data / not listed)",
                        "reason": t["reason"].iloc[-1] if len(t) else ""})
        summary.append({"date": d.date(), **res.counts, "tightened": res.tightened,
                        "untightened_count": res.untightened_count, "spy_12m": spy})
    picks_df = pd.DataFrame(picks)
    scored = picks_df.dropna(subset=["excess"]) if len(picks_df) else picks_df
    stats = {
        "n_picks": len(picks_df),
        "n_scored": len(scored),
        "hit_rate": float((scored["excess"] > 0).mean()) if len(scored) else np.nan,
        "mean_excess": float(scored["excess"].mean()) if len(scored) else np.nan,
        "median_excess": float(scored["excess"].median()) if len(scored) else np.nan,
    }
    return {"picks": picks_df, "summary": pd.DataFrame(summary), "tracked": pd.DataFrame(tracked),
            "stats": stats, "track": track}
