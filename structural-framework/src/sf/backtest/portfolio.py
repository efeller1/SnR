"""§9.3 portfolio tests: monthly rebalancing with transaction costs, benchmarks, summary stats."""
from __future__ import annotations

import numpy as np
import pandas as pd


def backtest(weights: pd.DataFrame, returns: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """weights[t] is set at t and earns returns[t] (the return from t to t+1).

    Turnover is measured against the drifted weights from the previous period, and costs
    (cost_bps per unit of turnover) are subtracted from that period's return.
    """
    cols = list(weights.columns)
    r = returns.reindex(index=weights.index, columns=cols)
    rows, drifted = [], None
    for t in weights.index:
        w = weights.loc[t].fillna(0)
        rt = r.loc[t]
        if rt.isna().all():
            break
        # An asset with no return yet (e.g. BTC before 2014) holds its weight in cash (zero return).
        rt = rt.fillna(0)
        turnover = float((w - drifted).abs().sum()) if drifted is not None else float(w.abs().sum())
        gross = float((w * rt).sum())
        net = gross - turnover * cost_bps / 1e4
        grown = w * (1 + rt)
        drifted = grown / grown.sum() if grown.sum() else w
        rows.append({"date": t, "return": net, "gross": gross, "turnover": turnover})
    return pd.DataFrame(rows).set_index("date")


def summary(ret: pd.Series, cash: pd.Series | None = None, turnover: pd.Series | None = None,
            periods_per_year: int = 12) -> dict:
    ret = ret.dropna()
    if ret.empty:
        return {}
    wealth = (1 + ret).cumprod()
    years = len(ret) / periods_per_year
    excess = ret - (cash.reindex(ret.index).fillna(0) if cash is not None else 0)
    vol = ret.std() * np.sqrt(periods_per_year)
    return {
        "start": ret.index[0].date().isoformat(), "end": ret.index[-1].date().isoformat(),
        "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
        "vol": float(vol),
        "sharpe": float(excess.mean() * periods_per_year / vol) if vol > 0 else np.nan,
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
        "turnover": float(turnover.mean() * periods_per_year) if turnover is not None else np.nan,
    }


def static_weights(index: pd.DatetimeIndex, w: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame([w] * len(index), index=index)


def returns_by_regime(ret: pd.Series, labels: pd.Series, periods_per_year: int = 12) -> pd.DataFrame:
    d = pd.concat({"r": ret, "regime": labels}, axis=1).dropna()
    g = d.groupby("regime")["r"]
    return pd.DataFrame({"months": g.size(), "ann_return": g.mean() * periods_per_year,
                         "ann_vol": g.std() * np.sqrt(periods_per_year)})
