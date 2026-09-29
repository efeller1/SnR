"""CLI.

  python -m snr build-facts                 # download + reduce EDGAR bulk XBRL (once; ~1.3 GB download)
  python -m snr validate --start 2021 --end 2024
  python -m snr screen [--as-of YYYY-MM-DD]
"""
from __future__ import annotations

import argparse

import pandas as pd

from .attention import AttentionCollector
from .config import ScreenConfig
from .market import FACTOR_ETFS, SECTOR_ETFS, PriceStore
from .report import write_current, write_validation
from .screen import Screener
from .sec import SecClient, build_facts_table, load_facts
from .validate import BENCHMARK, quarter_ends, run_validation


def _screener(offline_attention: bool) -> Screener:
    cfg = ScreenConfig()
    sec = SecClient()
    prices = PriceStore()
    prices.prefetch([*FACTOR_ETFS, *SECTOR_ETFS, BENCHMARK])
    return Screener(load_facts(), sec.ticker_map(cfg.listed_exchanges), sec, prices,
                    AttentionCollector(use_network=not offline_attention))


def main() -> None:
    ap = argparse.ArgumentParser(prog="snr")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-facts")
    b.add_argument("--refresh", action="store_true")
    v = sub.add_parser("validate")
    v.add_argument("--start", type=int, default=2021)
    v.add_argument("--end", type=int, default=2024)
    v.add_argument("--track", default="NTRA")
    v.add_argument("--offline-attention", action="store_true", help="manual CSV + turnover only")
    s = sub.add_parser("screen")
    s.add_argument("--as-of", default=str(pd.Timestamp.now().normalize().date()))
    s.add_argument("--offline-attention", action="store_true")
    args = ap.parse_args()

    if args.cmd == "build-facts":
        print(build_facts_table(SecClient(), refresh=args.refresh))
    elif args.cmd == "validate":
        out = run_validation(_screener(args.offline_attention), quarter_ends(args.start, args.end),
                             track=args.track)
        print(write_validation(out))
        print(out["stats"])
    elif args.cmd == "screen":
        res = _screener(args.offline_attention).run(pd.Timestamp(args.as_of))
        print(write_current(res))


if __name__ == "__main__":
    main()
