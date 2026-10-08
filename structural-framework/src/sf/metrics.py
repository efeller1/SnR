"""Evaluate a metric (formula + steps) into a point-in-time series.

Inputs are aligned on *knowledge time*: each input value is placed at its publication date and
carried forward, so a formula like gold / M2 at date d uses the latest gold price and the latest M2
print that were both public on d. Steps then run on that calendar.

`evaluate` returns a DataFrame indexed by the date each value became computable, with:
  value   the metric
  oldest  the oldest publication date among the inputs behind the value (used for staleness)
`sample_metric` reads it on the scoring calendar with `sf.pit.sample_at`.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .pit import Panel, sample_at
from .transforms import NEEDS_OTHER, OPS

FUNCS = {"log": np.log, "exp": np.exp, "abs": np.abs, "sqrt": np.sqrt}


@dataclass
class Ctx:
    panel: Panel
    halving: dict[str, Any] | None = None


def formula_inputs(formula: str) -> list[str]:
    names = {n.id for n in ast.walk(ast.parse(formula, mode="eval")) if isinstance(n, ast.Name)}
    return sorted(names - set(FUNCS))


def step_inputs(steps: list[Any]) -> list[str]:
    out: list[str] = []
    for st in steps:
        p = _params(st)
        if "formula" in p:
            out += formula_inputs(p["formula"]) + step_inputs(p.get("steps", []))
        if "x" in p:
            out += formula_inputs(p["x"])
    return out


def all_inputs(formula: str, steps: list[Any]) -> list[str]:
    return sorted(set(formula_inputs(formula)) | set(step_inputs(steps)))


def _params(step: Any) -> dict[str, Any]:
    return step.model_dump() if hasattr(step, "model_dump") else dict(step)


def _empty() -> pd.DataFrame:
    return pd.DataFrame({"value": pd.Series(dtype=float), "oldest": pd.Series(dtype="datetime64[ns]")})


def _known(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """An input re-indexed by publication date (latest observation wins when several share a date)."""
    d = df.sort_values(["published", "date"]).drop_duplicates("published", keep="last").set_index("published")
    return d["value"].astype(float), pd.Series(d.index, index=d.index)


def evaluate(formula: str, steps: list[Any], ctx: Ctx) -> pd.DataFrame:
    names = formula_inputs(formula)
    if not names or not all(ctx.panel.has(n) for n in names):
        return _empty()
    vals, pubs = {}, {}
    for n in names:
        vals[n], pubs[n] = _known(ctx.panel.get(n))
    v = pd.DataFrame(vals).sort_index().ffill()
    p = pd.DataFrame(pubs).sort_index().ffill()
    ok = v.notna().all(axis=1)
    v, p = v[ok], p[ok]
    if v.empty:
        return _empty()
    value = eval(compile(ast.parse(formula, mode="eval"), "<formula>", "eval"),
                 {"__builtins__": {}, **FUNCS}, {c: v[c] for c in v.columns})
    value = pd.Series(value, index=v.index, dtype=float).replace([np.inf, -np.inf], np.nan)
    oldest = p.min(axis=1)

    for st in steps:
        params = _params(st)
        op = params.pop("op")
        if op in NEEDS_OTHER:
            sub = (evaluate(params["formula"], params.get("steps", []), ctx) if "formula" in params
                   else evaluate(params["x"], [], ctx))
            if sub.empty:
                return _empty()
            u = sub.index.union(value.index)
            other, other_old = sub["value"].reindex(u).ffill(), sub["oldest"].reindex(u).ffill()
            if op == "minus_series":
                value = value.reindex(u).ffill()
                oldest = oldest.reindex(u).ffill()
                params["_other"] = other
                ok = value.notna() & other.notna()
                value, oldest, other_old, params["_other"] = value[ok], oldest[ok], other_old[ok], other[ok]
            else:
                params["_other"] = other
            new = OPS[op](value, params, ctx)
            oldest = pd.concat([_asof(oldest, new.index), _asof(other_old, new.index)], axis=1).min(axis=1)
        else:
            new = OPS[op](value, params, ctx)
            oldest = _asof(oldest, new.index)
        value = new.astype(float).replace([np.inf, -np.inf], np.nan)
    return pd.DataFrame({"value": value, "oldest": oldest})


def _asof(s: pd.Series, index: pd.Index) -> pd.Series:
    """s carried forward onto a new index."""
    return s.reindex(s.index.union(index)).ffill().reindex(index)


def sample_metric(formula: str, steps: list[Any], ctx: Ctx, dates: pd.DatetimeIndex,
                  stale_after_days: int | None) -> pd.Series:
    ev = evaluate(formula, steps, ctx)
    if ev.empty:
        return pd.Series(np.nan, index=dates)
    return sample_at(ev["value"], ev.index.to_series(), dates, stale_after_days, oldest=ev["oldest"])
