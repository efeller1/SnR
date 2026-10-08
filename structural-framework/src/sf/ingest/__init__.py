"""Ingest every series in config/assets.yaml into data/raw and a long panel in data/processed."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import yaml

from ..config import CONFIG_DIR, DATA_DIR, Config
from . import fred, manual, prices, shiller
from .base import COLUMNS

log = logging.getLogger(__name__)
FETCHERS = {"fred": fred.fetch, "prices": prices.fetch, "manual": manual.fetch, "shiller": shiller.fetch}
PANEL_PATH = DATA_DIR / "processed" / "panel.parquet"


def load_sources() -> dict:
    with open(CONFIG_DIR / "sources.yaml") as f:
        return yaml.safe_load(f)


def ingest_all(cfg: Config, only: list[str] | None = None) -> pd.DataFrame:
    """Fetch every series, save raw copies with the retrieval time, and write the long panel."""
    sources = load_sources()
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    frames, report = [], []
    for sid, s in cfg.assets.series.items():
        if only and sid not in only:
            continue
        try:
            df = FETCHERS[s.source](s, cfg.lag(s), sources)
            status = "ok" if len(df) else "missing"
        except Exception as e:  # keep going; a missing series scores NA
            log.warning("ingest %s (%s:%s) failed: %s", sid, s.source, s.id, e)
            df, status = pd.DataFrame(columns=COLUMNS), f"error: {e}"
        if len(df):
            df.assign(retrieved=retrieved).to_parquet(raw_dir / f"{sid}.parquet", index=False)
            frames.append(df.assign(series=sid))
        report.append({"series": sid, "source": s.source, "id": s.id, "rows": len(df), "status": status,
                       "first": df["date"].min() if len(df) else None,
                       "last": df["date"].max() if len(df) else None,
                       "pit": ",".join(sorted(df["pit"].dropna().unique())) if len(df) else ""})
    panel = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS + ["series"])
    if only and PANEL_PATH.exists():
        old = pd.read_parquet(PANEL_PATH)
        panel = pd.concat([old[~old["series"].isin(only)], panel], ignore_index=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PANEL_PATH, index=False)
    pd.DataFrame(report).to_csv(DATA_DIR / "processed" / "ingest_report.csv", index=False)
    return pd.DataFrame(report)
