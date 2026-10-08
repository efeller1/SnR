"""§7.2 snapshots: snapshots/YYYY-MM-DD.json, immutable, the live track record."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from .config import SNAPSHOT_DIR, Config
from .engine import Results, what_changed
from .trends.load import Trend
from .trends.score import score_trend


class SnapshotExists(FileExistsError):
    pass


def _clean(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    if hasattr(v, "item"):          # numpy scalars
        return _clean(v.item())
    return v


def build_snapshot(res: Results, cfg: Config, t: pd.Timestamp, trends: dict[str, Trend] | None = None,
                   data_quality: dict | None = None) -> dict:
    t = pd.Timestamp(t)
    i = res.dates.get_loc(t)
    prev = res.dates[i - 1] if i > 0 else None
    metrics = {}
    for aid, a in cfg.assets.assets.items():
        for m in a.metrics:
            metrics[m.id] = {
                "asset": aid, "component": m.component, "role": m.role, "name": m.name,
                "value": res.metric_values.loc[t, m.id], "percentile": res.metric_pct.loc[t, m.id],
                "score": res.metric_scores.loc[t, m.id], "weight": res.metric_weights.loc[t, m.id],
            }
    assets = {}
    for aid, a in cfg.assets.assets.items():
        c = res.composite.loc[t, aid]
        st = res.stance[aid].loc[t]
        assets[aid] = {
            "name": a.name, "group": a.group,
            "components": res.components[aid].loc[t].to_dict(),
            "composite": c,
            "composite_change": (c - res.composite.loc[prev, aid]) if prev is not None else None,
            "stance": st["stance"], "stance_uncapped": st["raw"], "capped_by": st["capped_by"] or None,
            "what_changed": what_changed(res, cfg, aid, t),
        }
    reg = res.regime.loc[t]
    snap = {
        "date": t.date().isoformat(),
        "config_hash": cfg.hash,
        "assets": assets,
        "metrics": metrics,
        "regime": {k: reg[k] for k in ("quadrant", "growth", "growth_signal", "inflation", "inflation_signal",
                                        "real_rates", "real_10y", "real_10y_change", "fdi", "liquidity_driver",
                                        "global_order", "global_order_score")},
        "allocation": {"base": cfg.allocation.base_weights, "tilted": res.allocation.loc[t].to_dict()},
        "trends": {tid: score_trend(tr) for tid, tr in (trends or {}).items()},
        "data_quality": data_quality or {},
    }
    return _clean(snap)


def write_snapshot(snap: dict, directory: Path = SNAPSHOT_DIR) -> Path:
    """Append-only: refuses to overwrite an existing snapshot."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{snap['date']}.json"
    if path.exists():
        raise SnapshotExists(f"{path} already exists; snapshots are immutable")
    with open(path, "x") as f:
        json.dump(snap, f, indent=2, sort_keys=False)
    return path


def load_snapshots(directory: Path = SNAPSHOT_DIR) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))]
