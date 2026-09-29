"""Markdown/CSV output for validation runs and the current screen."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from .config import MANUAL_DIR, REPORTS_DIR
from .screen import ScreenResult


def _pct(x, digits=0):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{digits}%}"


def _money(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"${x / 1e9:.1f}B" if abs(x) >= 1e9 else f"${x / 1e6:.0f}M"


def _md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_none_\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def write_validation(v: dict, out_dir: Path = REPORTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    v["picks"].to_csv(out_dir / "validation_picks.csv", index=False)
    v["summary"].to_csv(out_dir / "validation_summary.csv", index=False)
    v["tracked"].to_csv(out_dir / f"validation_{v['track']}.csv", index=False)
    s = v["stats"]
    picks = v["picks"].copy()
    if len(picks):
        for c in ("rev_growth", "attention_pct", "resid_6m", "fwd_12m", "spy_12m", "excess"):
            picks[c] = picks[c].map(_pct)
        picks["mcap_bn"] = picks["mcap_bn"].map(lambda x: f"{x:.1f}")
        picks["r2"] = picks["r2"].map(lambda x: f"{x:.2f}")
    summ = v["summary"].copy()
    summ["spy_12m"] = summ["spy_12m"].map(_pct)
    passed = v["tracked"][v["tracked"]["passed"]]["date"].astype(str).tolist()
    md = [
        "# Validation: quarterly screens\n",
        f"**{v['track']} passed on:** {', '.join(passed) if passed else 'no dates'}\n",
        f"**Flagged:** {s['n_picks']} picks ({s['n_scored']} with a full forward-return record)  \n"
        f"**Share beating the S&P 500 (SPY) over the next 12 months:** {_pct(s['hit_rate'])}  \n"
        f"**Mean / median excess return:** {_pct(s['mean_excess'], 1)} / {_pct(s['median_excess'], 1)}\n",
        f"## {v['track']} by date\n", _md_table(v["tracked"]),
        "## Funnel by date\n", _md_table(summ),
        "## All flagged stocks\n", _md_table(picks),
        "## Caveats\n",
        "- Ticker map is today's listings: names acquired or delisted since the screening date are missing "
        "(survivorship bias, which likely flatters the hit rate).\n"
        "- A pick delisted within its 12-month window is scored through its last available close.\n"
        "- Attention measures used in backtests are only those available point-in-time; see the "
        "`attention_measures` column in the CSV and snr/attention.py.\n",
    ]
    path = out_dir / "validation.md"
    path.write_text("\n".join(md))
    return path


def _notes() -> dict:
    """Optional analyst notes: data/manual/notes.md with '## TICKER' sections."""
    p = MANUAL_DIR / "notes.md"
    if not p.exists():
        return {}
    parts = re.split(r"^## +([A-Z.\-]+)\s*$", p.read_text(), flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def _description(ticker: str) -> str:
    try:
        import yfinance as yf
        text = yf.Ticker(ticker).info.get("longBusinessSummary") or ""
    except Exception:
        text = ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:3])


def _auto_risks(r: pd.Series) -> list[str]:
    risks = []
    if pd.notna(r.get("net_income_ttm")) and r["net_income_ttm"] < 0:
        risks.append(f"Unprofitable: trailing-12-month net loss of {_money(-r['net_income_ttm'])}.")
    ocf, cash = r.get("op_cash_flow_ttm"), r.get("cash")
    if pd.notna(ocf) and ocf < 0 and pd.notna(cash):
        risks.append(f"Burning cash: {_money(-ocf)} operating outflow vs {_money(cash)} cash "
                     f"(~{cash / -ocf:.1f} years of runway before financing).")
    if pd.notna(r.get("shares_yoy")) and r["shares_yoy"] > 0.05:
        risks.append(f"Dilution: share count up {_pct(r['shares_yoy'])} year over year.")
    if pd.notna(r.get("gm_change")) and r["gm_change"] < 0:
        risks.append("Gross margin slipped slightly over the last four quarters.")
    risks.append("Low R-squared means the stock moves mostly on company news, so single events "
                 "(earnings, reimbursement, litigation, trial data) dominate outcomes.")
    risks.append("Low coverage cuts both ways: less crowding, but also thin liquidity and slower price discovery.")
    return risks


def write_current(res: ScreenResult, out_dir: Path = REPORTS_DIR, with_descriptions: bool = True) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    date = res.as_of.date()
    res.final.to_csv(out_dir / f"screen_{date}.csv", index=False)
    res.trace.to_csv(out_dir / f"screen_{date}_trace.csv", index=False)
    notes = _notes()
    md = [f"# Screen as of {date}\n",
          f"Funnel: {res.counts}" + (f" — Filter 1 tightened (untightened list had {res.untightened_count})"
                                     if res.tightened else "") + "\n"]
    if res.final.empty:
        md.append("_No stocks passed all three filters._\n")
    for rank, (_, r) in enumerate(res.final.iterrows(), 1):
        md += [
            f"## {rank}. {r['ticker']} — {r['name']}\n",
            f"- **Sector:** {r['sector']} (SIC {r['sic']}: {r['sic_description']})  ",
            f"- **Market cap:** {_money(r['mcap'])}  ",
            f"- **Revenue growth:** {_pct(r['rev_growth'])} YoY in quarter ended {pd.Timestamp(r['latest_quarter']).date()} "
            f"(filed {pd.Timestamp(r['latest_filed']).date()}); trend (oldest→latest) "
            f"{', '.join(_pct(g) for g in r['growth_trend'])}; accelerating {r['accel_streak']} qtr(s)  ",
            f"- **Gross margin:** {' → '.join(_pct(g, 1) for g in r['gm_trend'])}  ",
            f"- **Attention percentile:** {_pct(r['attention_pct'])} (measures: {r['attention_measures']})  ",
            f"- **Residual return:** 3m {_pct(r['resid_3m'], 1)}, 6m {_pct(r['resid_6m'], 1)}; "
            f"prior 12m {_pct(r['resid_prior'], 1)}; R² {r['r2']:.2f}\n",
        ]
        note = notes.get(r["ticker"])
        desc = _description(r["ticker"]) if with_descriptions and not note else ""
        md.append("**Business and growth driver:** " + (note or desc or "_add to data/manual/notes.md_") + "\n")
        md.append("**Key risks:**\n" + "\n".join(f"- {x}" for x in _auto_risks(r)) + "\n")
    path = out_dir / f"screen_{date}.md"
    path.write_text("\n".join(md))
    return path
