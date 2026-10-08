"""§6.2 trend scoring: durability, cycle, opportunity, and the optional STR overlay."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .load import Durability, Trend

CYCLE = {"early_scarcity": 5, "consolidation": 4, "expansion": 3, "bust": 2, "overbuild": 1}
BUST_WITH_EXITS = 4


def durability_score(d: Durability) -> float:
    return float(np.mean([min(d.horizon_years / 2, 5), 6 - d.reversibility, d.commitment]))


def cycle_score(stage: str, supply_exits_confirmed: bool = False) -> float:
    return float(BUST_WITH_EXITS if stage == "bust" and supply_exits_confirmed else CYCLE[stage])


def opportunity(durability: float, cycle: float, priced_in: float) -> float:
    return 0.4 * durability + 0.35 * cycle + 0.25 * (6 - priced_in)


def score_trend(t: Trend) -> dict[str, float]:
    d = durability_score(t.durability)
    c = cycle_score(t.capital_cycle_stage, t.supply_exits_confirmed)
    return {"durability": d, "cycle": c, "priced_in": float(t.priced_in), "opportunity": opportunity(d, c, t.priced_in)}


def trend_history(t: Trend) -> pd.DataFrame:
    """Score at each dated judgment. Values carry forward from the previous entry; an entry's
    `scores` dict updates them, and its explicit fields (durability, stage, priced_in) win."""
    rows, r = [], {}
    for h in sorted(t.history, key=lambda h: h.date):
        r = {**r, **{k: float(v) for k, v in h.scores.items() if k in ("durability", "cycle", "priced_in")}}
        if h.durability:
            r["durability"] = durability_score(h.durability)
        if h.capital_cycle_stage:
            r["cycle"] = cycle_score(h.capital_cycle_stage, bool(h.supply_exits_confirmed))
        if h.priced_in:
            r["priced_in"] = float(h.priced_in)
        if {"durability", "cycle", "priced_in"} <= r.keys():
            r["opportunity"] = opportunity(r["durability"], r["cycle"], r["priced_in"])
        rows.append({"date": pd.Timestamp(h.date), **r, "note": h.note})
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def opportunity_as_of(t: Trend, when: date | pd.Timestamp) -> float:
    """Opportunity from the latest judgment dated on or before `when` (point-in-time)."""
    h = trend_history(t)
    if h.empty or "opportunity" not in h:
        return np.nan
    h = h[h.index <= pd.Timestamp(when)]
    return float(h["opportunity"].iloc[-1]) if len(h) else np.nan


def str_overlay(trends: dict[str, Trend], asset: str, dates: pd.DatetimeIndex) -> pd.Series:
    """Mean opportunity of the trends linked to an asset, at each date."""
    linked = [t for t in trends.values() if asset in t.linked_premier_assets]
    if not linked:
        return pd.Series(np.nan, index=dates)
    vals = pd.DataFrame({t.id: [opportunity_as_of(t, d) for d in dates] for t in linked}, index=dates)
    return vals.mean(axis=1)
