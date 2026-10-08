"""Run the whole scoring stack over a calendar of dates, point-in-time.

metrics -> percentiles -> scores -> components (+ REG from the regime) -> composite -> stance -> allocation
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .allocation.tilt import tilt_weights
from .config import Config, MetricDef
from .metrics import Ctx, all_inputs, sample_metric
from .pit import Panel, sample_at
from .regime.classify import classify, regime_fit
from .scoring.components import component_scores, weighted_mean_renormalized
from .scoring.composite import composite_score
from .scoring.normalize import score_metric
from .scoring.stance import stance_history
from .trends.load import Trend
from .trends.score import str_overlay


@dataclass
class Results:
    dates: pd.DatetimeIndex
    metric_values: pd.DataFrame
    metric_pct: pd.DataFrame
    metric_scores: pd.DataFrame
    metric_weights: pd.DataFrame            # effective weight per date (0 when gated)
    metric_asset: dict[str, str]
    components: dict[str, pd.DataFrame]     # asset -> dates x component
    composite: pd.DataFrame                 # dates x asset
    stance: dict[str, pd.DataFrame]         # asset -> raw / stance / capped_by
    regime: pd.DataFrame
    allocation: pd.DataFrame                # dates x asset (tilted weights)
    prices: pd.DataFrame                    # dates x asset, point-in-time price level
    overlay: dict[str, pd.Series] = field(default_factory=dict)


def scoring_calendar(cfg: Config, start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DatetimeIndex:
    """Calendar dates from start to end, plus `end` itself if it isn't on the calendar."""
    end = pd.Timestamp(end)
    dates = pd.date_range(pd.Timestamp(start), end, freq=cfg.scoring.calendar)
    return dates if len(dates) and dates[-1] == end else dates.append(pd.DatetimeIndex([end]))


def _metric_series(cfg: Config, ctx: Ctx, m: MetricDef, dates: pd.DatetimeIndex) -> pd.Series:
    freq = ctx.panel.coarsest_freq(all_inputs(m.formula, m.steps))
    return sample_metric(m.formula, m.steps, ctx, dates, cfg.scoring.stale_after_days[freq])


def run(cfg: Config, panel: Panel, dates: pd.DatetimeIndex, trends: dict[str, Trend] | None = None,
        component_weight_overrides: dict[str, float] | None = None) -> Results:
    """Score every asset on every date. `component_weight_overrides` is used by ablation (§9.4)."""
    norm = cfg.scoring.normalization
    vals, pcts, scores, weights, owner = {}, {}, {}, {}, {}
    for aid, a in cfg.assets.assets.items():
        ctx = Ctx(panel=panel, halving=a.halving)
        win, minh = cfg.window(aid)
        for m in a.metrics:
            x = _metric_series(cfg, ctx, m, dates)
            p, s = score_metric(x, m.normalize or norm.method, m.direction, win, minh, norm.zscore_clip, m.thresholds)
            vals[m.id], pcts[m.id], scores[m.id], owner[m.id] = x, p, s, aid
            weights[m.id] = pd.Series(m.weight if m.role == "score" else 0.0, index=dates)
    metric_values, metric_pct = pd.DataFrame(vals, index=dates), pd.DataFrame(pcts, index=dates)
    metric_scores, metric_weights = pd.DataFrame(scores, index=dates), pd.DataFrame(weights, index=dates)

    # §4.2 gate: e.g. the real-yield residual gets zero weight while its rolling R² is below 0.2.
    for a in cfg.assets.assets.values():
        for m in a.metrics:
            if m.gate:
                g = metric_values[m.gate.metric]
                metric_weights.loc[g < m.gate.min, m.id] = 0.0

    regime = classify(cfg, Ctx(panel=panel), dates, metric_scores)
    reg = pd.DataFrame([regime_fit(regime.loc[t], cfg, list(cfg.assets.assets)) for t in dates], index=dates)

    trends = trends or {}
    overlay_cfg = cfg.scoring.trend_overlay
    components, composite, stance, overlay = {}, {}, {}, {}
    for aid, a in cfg.assets.assets.items():
        scored = {m.id: m.component for m in a.metrics if m.role == "score"}
        comps = component_scores(metric_scores[list(scored)], scored, metric_weights[list(scored)],
                                 cfg.scoring.aggregation.max_missing_share)
        comps["REG"] = reg[aid]
        if overlay_cfg.enabled and trends:
            ov = str_overlay(trends, aid, dates)
            overlay[aid] = ov
            w = overlay_cfg.weight_within_str
            if "STR" in comps:
                both = pd.DataFrame({"STR": comps["STR"], "OVERLAY": ov})
                comps["STR"] = weighted_mean_renormalized(both, {"STR": 1 - w, "OVERLAY": w},
                                                          cfg.scoring.aggregation.max_missing_share, by_count=False)
        comps = comps.reindex(columns=[c for c in ("STR", "REG", "CAP", "VAL", "LIQ", "MOM") if c in comps])
        cw = cfg.component_weights(aid)
        if component_weight_overrides:
            cw.update(component_weight_overrides)
        components[aid] = comps
        composite[aid] = composite_score(comps, cw, cfg.scoring.aggregation.composite_max_missing_weight)
        nan = pd.Series(np.nan, index=dates)
        stance[aid] = stance_history(composite[aid], comps.get("STR", nan), comps.get("MOM", nan), cfg.scoring.stance)
    composite_df = pd.DataFrame(composite, index=dates)

    alloc_assets = list(cfg.allocation.base_weights)
    allocation = pd.DataFrame([tilt_weights({a: composite_df.loc[t, a] for a in alloc_assets}, cfg.allocation)
                               for t in dates], index=dates)

    prices = {}
    for aid, a in cfg.assets.assets.items():
        if a.price and panel.has(a.price):
            df = panel.get(a.price)
            prices[aid] = sample_at(df.set_index("date")["value"], df.set_index("date")["published"], dates,
                                    cfg.scoring.stale_after_days[panel.freqs.get(a.price, "daily")])
    return Results(dates, metric_values, metric_pct, metric_scores, metric_weights, owner, components,
                   composite_df, stance, regime, allocation, pd.DataFrame(prices, index=dates), overlay)


def metric_contributions(res: Results, cfg: Config, asset: str, t: pd.Timestamp) -> pd.Series:
    """Each metric's contribution to the composite at t: score x effective weight.

    Effective weight = (component weight, renormalized over present components) x (metric weight,
    renormalized over present metrics in that component). REG is reported as its own line.
    """
    comps = res.components[asset].loc[t]
    cw = {c: w for c, w in cfg.component_weights(asset).items() if c in comps and not pd.isna(comps[c])}
    total = sum(cw.values())
    if not total or pd.isna(res.composite.loc[t, asset]):
        return pd.Series(dtype=float)
    out = {}
    a = cfg.assets.assets[asset]
    for comp, w in cw.items():
        if comp == "REG":
            out["REG"] = comps["REG"] * w / total
            continue
        ids = [m.id for m in a.metrics if m.role == "score" and m.component == comp]
        s, mw = res.metric_scores.loc[t, ids], res.metric_weights.loc[t, ids]
        present = s.notna() & (mw > 0)
        denom = mw[present].sum()
        for m in ids:
            out[m] = s[m] * mw[m] / denom * w / total if present[m] and denom else 0.0
    return pd.Series(out)


def what_changed(res: Results, cfg: Config, asset: str, t: pd.Timestamp, top: int = 3) -> list[dict]:
    """The metrics that moved the composite most since the previous calendar date."""
    i = res.dates.get_loc(t)
    if i == 0:
        return []
    now, before = metric_contributions(res, cfg, asset, t), metric_contributions(res, cfg, asset, res.dates[i - 1])
    delta = now.sub(before, fill_value=0).dropna()
    delta = delta[delta.abs() > 1e-9].reindex(delta.abs().sort_values(ascending=False).index)[:top]
    return [{"metric": k, "delta_contribution": round(float(v), 3)} for k, v in delta.items()]
