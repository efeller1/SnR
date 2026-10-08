"""§9.4 ablation: drop one component (or one layer) at a time and re-run the portfolio test."""
from __future__ import annotations

import pandas as pd

from ..allocation.tilt import tilt_weights
from ..config import Config
from ..engine import Results
from ..scoring.composite import composite_score
from .portfolio import backtest, summary

LAYERS = {"L1": ["STR"], "L2": ["REG"], "L4": ["CAP", "VAL"], "L5": ["LIQ", "MOM"]}


def recomposite(res: Results, cfg: Config, drop: list[str]) -> pd.DataFrame:
    out = {}
    for aid, comps in res.components.items():
        w = {c: (0.0 if c in drop else v) for c, v in cfg.component_weights(aid).items()}
        out[aid] = composite_score(comps, w, cfg.scoring.aggregation.composite_max_missing_weight)
    return pd.DataFrame(out, index=res.dates)


def tilted(composite: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    assets = list(cfg.allocation.base_weights)
    return pd.DataFrame([tilt_weights(composite.loc[t, assets].to_dict(), cfg.allocation) for t in composite.index],
                        index=composite.index)


def ablation_table(res: Results, cfg: Config, returns: pd.DataFrame, cash: pd.Series | None,
                   window: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    """Sharpe and drawdown for the full model and each ablation, over `window` (e.g. the OOS period)."""
    cases = {"full": []}
    cases.update({f"-{c}": [c] for c in ("STR", "REG", "CAP", "VAL", "LIQ", "MOM")})
    cases.update({f"-{k}": v for k, v in LAYERS.items()})
    rows = []
    for name, drop in cases.items():
        w = tilted(recomposite(res, cfg, drop), cfg)
        if window is not None:
            w = w.loc[w.index.intersection(window)]
        bt = backtest(w, returns, cfg.allocation.transaction_cost_bps)
        rows.append({"case": name, **summary(bt["return"], cash, bt["turnover"])})
    df = pd.DataFrame(rows).set_index("case")
    full = df.loc["full"]
    df["d_sharpe"] = df["sharpe"] - full["sharpe"]
    df["d_max_drawdown"] = df["max_drawdown"] - full["max_drawdown"]
    # A component earns its place if removing it lowers Sharpe or deepens the drawdown.
    df["earns_place"] = ((df["d_sharpe"] < 0) | (df["d_max_drawdown"] < 0)).astype(object)
    df.loc["full", "earns_place"] = None
    return df
