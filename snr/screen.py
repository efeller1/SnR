"""The screen: universe -> Filter 1 -> Filter 2 -> Filter 3, all point-in-time.

The universe checks (listing, SIC exclusions, market cap, dollar volume) are
applied to Filter 1 survivors only, which gives the same result as applying
them first and avoids downloading prices for thousands of names.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .attention import AttentionCollector, filter2
from .config import MANUAL_DIR, ScreenConfig
from .fundamentals import Fundamentals, accel_streak, filter1, gm_trend, snapshot
from .market import SECTOR_NAMES, PriceStore, factor_returns, sic_to_sector_etf
from .residual import factor_regression, filter3

SPAC_NAME = ("acquisition corp", "acquisition co", "capital acquisition")


@dataclass
class ScreenResult:
    as_of: pd.Timestamp
    final: pd.DataFrame
    trace: pd.DataFrame                 # one row per name that reached each stage, with its fate
    tightened: bool = False
    untightened_count: int | None = None
    counts: dict = field(default_factory=dict)


class UnitVolumes:
    """Optional data/manual/unit_volumes.csv: ticker,period_end,available_date,units."""

    def __init__(self):
        p = MANUAL_DIR / "unit_volumes.csv"
        self.df = pd.read_csv(p, parse_dates=["period_end", "available_date"]) if p.exists() else None

    def yoy(self, ticker: str, as_of: pd.Timestamp) -> float | None:
        if self.df is None:
            return None
        d = self.df[(self.df["ticker"] == ticker) & (self.df["available_date"] <= as_of)].sort_values("period_end")
        if d.empty:
            return None
        last = d.iloc[-1]
        prev = d[(last["period_end"] - d["period_end"]).dt.days.between(350, 380)]
        return float(last["units"] / prev["units"].iloc[-1] - 1) if len(prev) else None


class Screener:
    def __init__(self, facts: pd.DataFrame, tickers: pd.DataFrame, sec, prices: PriceStore,
                 attention: AttentionCollector):
        self.facts_by_cik = {int(k): g for k, g in facts.groupby("cik")}
        self.tickers = tickers[tickers["cik"].isin(self.facts_by_cik.keys())].reset_index(drop=True)
        self.sec, self.prices, self.attention = sec, prices, attention
        self.units = UnitVolumes()
        self._snap: dict = {}
        self._sub: dict = {}
        self._factors: dict = {}

    # --- cached lookups --------------------------------------------------------

    def fundamentals(self, cik: int, as_of: pd.Timestamp, min_growth: float) -> Fundamentals:
        key = (cik, as_of)
        if key not in self._snap:
            self._snap[key] = snapshot(self.facts_by_cik[cik], as_of, min_growth=min_growth)
        return self._snap[key]

    def submission(self, cik: int) -> dict:
        if cik not in self._sub:
            try:
                self._sub[cik] = self.sec.submissions(cik)
            except Exception:
                self._sub[cik] = {"sic": None, "sic_description": None, "name": None}
        return self._sub[cik]

    def factors(self, etf: str) -> pd.DataFrame:
        if etf not in self._factors:
            self._factors[etf] = factor_returns(self.prices, etf)
        return self._factors[etf]

    # --- the screen ------------------------------------------------------------

    def run(self, as_of, cfg: ScreenConfig = ScreenConfig()) -> ScreenResult:
        as_of = pd.Timestamp(as_of)
        res = self._run_once(as_of, cfg, base_growth=cfg.min_rev_growth)
        if len(res.final) > cfg.max_names:
            n = len(res.final)
            res = self._run_once(as_of, cfg.tightened(), base_growth=cfg.min_rev_growth)
            res.tightened, res.untightened_count = True, n
        return res

    def _run_once(self, as_of: pd.Timestamp, cfg: ScreenConfig, base_growth: float) -> ScreenResult:
        trace = []

        # Filter 1 -------------------------------------------------------------
        f1_rows = []
        for row in self.tickers.itertuples(index=False):
            f = self.fundamentals(int(row.cik), as_of, base_growth)
            ok, why = filter1(f, cfg, self.units.yoy(row.ticker, as_of))
            rec = {"ticker": row.ticker, "cik": int(row.cik), "name": row.name, "stage": "filter1",
                   "reason": why}
            if ok:
                f1_rows.append((row, f))
            elif f.latest_end is not None:
                trace.append(rec)
        counts = {"filings_universe": len(self.tickers), "filter1": len(f1_rows)}

        # Universe -------------------------------------------------------------
        uni = []
        for row, f in f1_rows:
            rec = {"ticker": row.ticker, "cik": int(row.cik), "name": row.name}
            sub = self.submission(int(row.cik))
            sic = sub.get("sic")
            mcap = self.prices.market_cap(row.ticker, as_of, f.shares)
            adv = self.prices.adv(row.ticker, as_of, cfg.adv_window)
            why = None
            if sic in cfg.excluded_sic or any(s in (row.name or "").lower() for s in SPAC_NAME):
                why = f"excluded SIC {sic} (SPAC/REIT/fund)"
            elif np.isnan(mcap):
                why = "no price / share count"
            elif not cfg.min_mcap <= mcap <= cfg.max_mcap:
                why = f"market cap ${mcap / 1e9:.1f}B outside range"
            elif not adv > cfg.min_adv:
                why = f"ADV ${adv / 1e6:.1f}M too low"
            if why:
                trace.append({**rec, "stage": "universe", "reason": why})
                continue
            h = self.prices.history(row.ticker, as_of)
            etf = sic_to_sector_etf(sic)
            slope, change = gm_trend(f.gross_margin)
            uni.append({
                **rec, "sic": sic, "sic_description": sub.get("sic_description"), "sector_etf": etf,
                "sector": SECTOR_NAMES[etf], "mcap": mcap, "adv": adv,
                "turnover": self.prices.turnover(row.ticker, as_of, cfg.adv_window, f.shares),
                "last_volume": float(h["volume"].iloc[-1]) if len(h) else np.nan,
                "latest_quarter": f.latest_end, "latest_filed": f.latest_filed,
                "rev_growth": f.growth.iloc[-1], "growth_trend": [round(g, 3) for g in f.last_growth[-4:]],
                "accel_streak": accel_streak(list(f.growth.values)),
                "rev_ttm": float(f.revenue.tail(4).sum()) if len(f.revenue) >= 4 else np.nan,
                "gross_margin": f.gross_margin.iloc[-1] if len(f.gross_margin) else np.nan,
                "gm_trend": [round(g, 3) for g in f.gross_margin.values], "gm_change": change,
                "net_income_ttm": f.net_income_ttm, "op_cash_flow_ttm": f.op_cash_flow_ttm,
                "cash": f.cash, "shares_yoy": f.shares_yoy,
            })
        counts["universe"] = len(uni)
        if not uni:
            return ScreenResult(as_of, pd.DataFrame(), pd.DataFrame(trace), counts=counts)
        u = pd.DataFrame(uni).set_index("ticker")

        # Filter 2 -------------------------------------------------------------
        att = {t: self.attention.collect(t, r["name"], as_of, r["last_volume"]) for t, r in u.iterrows()}
        u = u.join(pd.DataFrame.from_dict(att, orient="index"))
        u = filter2(u, cfg)
        for t, r in u[~u["f2_pass"]].iterrows():
            trace.append({"ticker": t, "cik": r["cik"], "name": r["name"], "stage": "filter2",
                          "reason": f"{r['f2_reason']} (pct {r['attention_pct']:.0%})"
                          if pd.notna(r["attention_pct"]) else r["f2_reason"]})
        u2 = u[u["f2_pass"]].copy()
        counts["filter2"] = len(u2)

        # Filter 3 -------------------------------------------------------------
        stats = []
        for t, r in u2.iterrows():
            reg = factor_regression(self.prices.returns(t), self.factors(r["sector_etf"]), as_of, cfg)
            reg.pop("betas", None)
            stats.append({"ticker": t, **reg})
        if stats:
            s = filter3(pd.DataFrame(stats).set_index("ticker"), cfg)
            u2 = u2.join(s)
            for t, r in u2[~u2["f3_pass"]].iterrows():
                trace.append({"ticker": t, "cik": r["cik"], "name": r["name"], "stage": "filter3",
                              "reason": r["f3_reason"]})
            final = u2[u2["f3_pass"]].sort_values("resid_6m", ascending=False)
        else:
            final = u2.iloc[:0]
        for t, r in final.iterrows():
            trace.append({"ticker": t, "cik": r["cik"], "name": r["name"], "stage": "final", "reason": "pass"})
        counts["filter3"] = len(final)
        return ScreenResult(as_of, final.reset_index(), pd.DataFrame(trace), counts=counts)
