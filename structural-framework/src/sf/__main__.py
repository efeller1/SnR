"""Command line: python -m sf {ingest,run,history,backtest,trends,universe}."""
from __future__ import annotations

import argparse
import json
import logging
import sys

import pandas as pd

from .config import DATA_DIR, REPORTS_DIR, SNAPSHOT_DIR, load_config


def _panel(cfg):
    from .ingest import PANEL_PATH
    from .pit import Panel

    if not PANEL_PATH.exists():
        sys.exit("No data/processed/panel.parquet yet. Run `python -m sf ingest` first.")
    return Panel.load(PANEL_PATH, {k: s.freq for k, s in cfg.assets.series.items()})


def _trends():
    from .trends.load import load_trends
    return load_trends()


def _data_quality(panel, cfg) -> dict:
    lagged = sorted(k for k, s in cfg.assets.series.items()
                    if s.vintage == "first_release" and panel.has(k) and (panel.get(k)["pit"] == "lagged").all())
    missing = sorted(k for k in cfg.assets.series if not panel.has(k))
    return {"missing_series": missing, "first_release_requested_but_latest_used": lagged}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="sf")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest", help="download every series into data/raw and data/processed/panel.parquet")
    p.add_argument("--only", nargs="*")
    p = sub.add_parser("run", help="score one date and write an immutable snapshot")
    p.add_argument("--date", default=pd.Timestamp.today().normalize().date().isoformat())
    p.add_argument("--no-snapshot", action="store_true")
    p = sub.add_parser("history", help="score the whole calendar and save it for the dashboard and backtests")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=pd.Timestamp.today().normalize().date().isoformat())
    p = sub.add_parser("backtest", help="§9 component, regime, portfolio and ablation tests")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=pd.Timestamp.today().normalize().date().isoformat())
    p.add_argument("--use-holdout", action="store_true", help="include the final holdout (log why you did)")
    sub.add_parser("trends", help="score every trend file")
    sub.add_parser("universe", help="check §13 admission files")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config()

    if args.cmd == "ingest":
        from .ingest import ingest_all
        print(ingest_all(cfg, args.only).to_string(index=False))

    elif args.cmd == "run":
        from .engine import run, scoring_calendar
        from .snapshot import build_snapshot, write_snapshot
        panel = _panel(cfg)
        t = pd.Timestamp(args.date)
        start = t - pd.DateOffset(years=20)
        trends = _trends()
        res = run(cfg, panel, scoring_calendar(cfg, start, t), trends)
        snap = build_snapshot(res, cfg, t, trends, _data_quality(panel, cfg))
        rows = [{"asset": a, **{k: v for k, v in d["components"].items()}, "composite": d["composite"],
                 "stance": d["stance"]} for a, d in snap["assets"].items()]
        print(pd.DataFrame(rows).set_index("asset").round(2).to_string())
        print(json.dumps(snap["regime"], indent=2, default=str))
        if not args.no_snapshot:
            print("wrote", write_snapshot(snap, SNAPSHOT_DIR))

    elif args.cmd in ("history", "backtest"):
        from .engine import run, scoring_calendar
        from .history import save_history
        from .ingest import load_sources
        start = args.start or load_sources()["history_start"]
        panel = _panel(cfg)
        res = run(cfg, panel, scoring_calendar(cfg, start, args.end), _trends())
        path = save_history(res, DATA_DIR / "processed" / "history")
        print("wrote", path)
        if args.cmd == "backtest":
            from .backtest.report import run_report
            out = run_report(res, cfg, panel, REPORTS_DIR / "backtest" / pd.Timestamp(args.end).date().isoformat(),
                             use_holdout=args.use_holdout)
            print("wrote", out)

    elif args.cmd == "trends":
        from .trends.score import score_trend
        rows = [{"trend": k, **score_trend(t), "stage": t.capital_cycle_stage, "bottlenecks": ", ".join(t.bottlenecks)}
                for k, t in _trends().items()]
        print(pd.DataFrame(rows).round(2).to_string(index=False))

    elif args.cmd == "universe":
        from .universe import load_admissions, tier_from_tests
        for k, a in load_admissions().items():
            implied = tier_from_tests(a)
            flag = "" if a.decision in (None, implied) else f"  <- recorded decision differs: {a.decision}"
            print(f"{k:6s} implied tier: {implied}{flag}")


if __name__ == "__main__":
    main()
