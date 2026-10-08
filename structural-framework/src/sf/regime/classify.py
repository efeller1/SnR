"""§5 regime classifier: growth x inflation quadrant, plus FDI, real-rate and global-order modifiers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config, SignalDef
from ..metrics import Ctx, all_inputs, sample_metric
from .fdi import fdi_history

QUADRANTS = {("rising", "falling"): "goldilocks", ("rising", "rising"): "reflation",
             ("falling", "rising"): "stagflation", ("falling", "falling"): "deflationary_bust"}


def _signal(cfg: Config, ctx: Ctx, sig: SignalDef, dates: pd.DatetimeIndex) -> pd.Series:
    freq = ctx.panel.coarsest_freq(all_inputs(sig.formula, sig.steps))
    return sample_metric(sig.formula, sig.steps, ctx, dates, cfg.scoring.stale_after_days[freq])


def _direction(x: pd.Series) -> pd.Series:
    return x.map(lambda v: None if pd.isna(v) else ("rising" if v > 0 else "falling"))


def classify(cfg: Config, ctx: Ctx, dates: pd.DatetimeIndex, metric_scores: pd.DataFrame) -> pd.DataFrame:
    r = cfg.regimes
    g = _signal(cfg, ctx, r.growth["signal"], dates)
    if "fallback" in r.growth:
        g = g.fillna(_signal(cfg, ctx, r.growth["fallback"], dates))
    inf = _signal(cfg, ctx, r.inflation["signal"], dates)
    df = pd.DataFrame({"growth_signal": g, "growth": _direction(g),
                       "inflation_signal": inf, "inflation": _direction(inf)}, index=dates)
    df["quadrant"] = [QUADRANTS.get((a, b)) for a, b in zip(df["growth"], df["inflation"])]

    lvl = _signal(cfg, ctx, r.real_rate_level, dates)
    chg = _signal(cfg, ctx, r.real_rate_change, dates)
    rr = r.real_rates
    df["real_10y"], df["real_10y_change"] = lvl, chg
    df["real_rates"] = [
        None if pd.isna(a) else "Restrictive" if a > rr["restrictive_level"] and (b or 0) > 0
        else "Easy" if a < rr["easy_level"] else "Neutral" for a, b in zip(lvl, chg)]

    f = fdi_history(cfg, ctx, dates)
    df["fdi"], df["liquidity_driver"] = f["fdi"], f["liquidity_driver"]
    df = df.join(f.drop(columns=["fdi", "liquidity_driver"]))

    go = []
    for m in r.global_order_metrics:
        s = metric_scores[m.id] if m.id in metric_scores else pd.Series(np.nan, index=dates)
        go.append(6 - s if m.invert else s)
    go_df = pd.concat(go, axis=1)
    enough = go_df.notna().mean(axis=1) > 1 - cfg.scoring.aggregation.max_missing_share - 1e-12
    df["global_order_score"] = go_df.mean(axis=1).where(enough)
    df["global_order"] = df["global_order_score"].map(
        lambda v: None if pd.isna(v) else "Fragmenting" if v < r.global_order["fragmenting_below"] else "Unipolar")
    return df


def regime_fit(row: pd.Series, cfg: Config, assets: list[str]) -> dict[str, float]:
    """§5.3 REG score per asset: prior for the quadrant, plus modifiers, clipped to 1-5."""
    q = row.get("quadrant")
    out = {}
    for a in assets:
        prior = cfg.regimes.prior_matrix.get(q, {}).get(a) if q else None
        if prior is None:
            out[a] = np.nan
            continue
        s = prior
        mods = cfg.regimes.modifiers
        if row.get("liquidity_driver") == "Fiscal-led":
            s += mods.get("fiscal_led", {}).get(a, 0)
        if row.get("real_rates") == "Restrictive":
            s += mods.get("restrictive", {}).get(a, 0)
        if row.get("global_order") == "Fragmenting":
            s += mods.get("fragmenting", {}).get(a, 0)
        out[a] = float(np.clip(s, 1, 5))
    return out
