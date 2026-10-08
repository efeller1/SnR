"""Run §9.1-9.4 and §14 on a scored history and write CSVs plus a plain-English summary."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..config import Config
from ..engine import Results
from ..pit import Panel, sample_at
from .ablation import ablation_table
from .conditional import conditional_returns, empirical_matrix
from .controls import controls_test
from .ic import ic_table, passes
from .portfolio import backtest, returns_by_regime, static_weights, summary
from .walkforward import holdout_split, in_out_split


def _pit(panel: Panel, sid: str, dates: pd.DatetimeIndex) -> pd.Series:
    if not panel.has(sid):
        return pd.Series(np.nan, index=dates)
    df = panel.get(sid).set_index("date")
    return sample_at(df["value"], df["published"], dates)


def period_returns(res: Results, cfg: Config, panel: Panel) -> tuple[pd.DataFrame, pd.Series]:
    """Return from t to t+1 indexed by t, per asset; the USD sleeve earns T-bills (§3.5)."""
    rets = res.prices.pct_change().shift(-1)
    cash = _pit(panel, cfg.backtest.cash_series, res.dates) / 100 / 12
    if "USD" in cfg.allocation.base_weights:
        rets["USD"] = cash
    bond = _pit(panel, cfg.backtest.bond_series, res.dates)
    rets["BOND"] = bond.pct_change().shift(-1)
    return rets, cash


def run_report(res: Results, cfg: Config, panel: Panel, out_dir: Path, use_holdout: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    bt = cfg.backtest
    dev, holdout = holdout_split(res.dates, bt.holdout_years)
    if use_holdout:
        dev = res.dates            # explicit, logged opt-in: evaluates on everything
    is_d, oos_d = in_out_split(dev, bt.oos_fraction)
    lines = [f"# Backtest report", "",
             f"Development period {dev[0].date()} to {dev[-1].date()}; in-sample to {is_d[-1].date()}, "
             f"out-of-sample after. Holdout ({holdout[0].date() if len(holdout) else '-'} on) "
             f"{'INCLUDED (explicit opt-in)' if use_holdout else 'untouched'}.", ""]

    # §9.1 ICs
    ic_rows = []
    for aid in cfg.assets.assets:
        if aid not in res.prices or res.prices[aid].isna().all():
            continue
        ids = [m.id for m in cfg.assets.assets[aid].metrics if m.role == "score"]
        sigs = pd.concat([res.metric_scores[ids], res.components[aid].add_prefix("comp:"),
                          res.composite[[aid]].rename(columns={aid: "composite"})], axis=1)
        for name, window in (("in_sample", is_d), ("out_of_sample", oos_d)):
            t = ic_table(sigs.loc[window], res.prices[aid].loc[window], bt.horizons_months, bt.quintiles)
            ic_rows.append(t.assign(asset=aid, sample=name))
    ic = pd.concat(ic_rows, ignore_index=True) if ic_rows else pd.DataFrame()
    if len(ic):
        ic.to_csv(out_dir / "ic.csv", index=False)
        h = bt.pass_bar.horizon_months
        wide = ic[ic["horizon"] == h].pivot_table(index=["asset", "signal"], columns="sample",
                                                  values=["ic", "t_nw"], aggfunc="first")
        verdict = []
        for (aid, sig), row in wide.iterrows():
            ins = {"ic": row.get(("ic", "in_sample")), "t_nw": row.get(("t_nw", "in_sample"))}
            oos = {"ic": row.get(("ic", "out_of_sample"))}
            verdict.append({"asset": aid, "signal": sig, "ic_is": ins["ic"], "t_is": ins["t_nw"],
                            "ic_oos": oos["ic"], "passes": passes(ins, oos, bt.pass_bar)})
        v = pd.DataFrame(verdict)
        v.to_csv(out_dir / "ic_pass.csv", index=False)
        tested = v.dropna(subset=["ic_is"])
        lines += ["## Component tests (§9.1)", "",
                  f"{int(tested['passes'].sum())} of {len(tested)} signals with enough history pass the "
                  f"{h}-month bar (IC >= {bt.pass_bar.min_ic}, t >= {bt.pass_bar.min_t}, same sign out of sample). "
                  "Failing components stay on the dashboard but should get zero weight.", ""]
        if len(tested):
            lines += [tested.round(3).to_markdown(index=False), ""]

    # §9.2 regime-conditional returns
    rets, cash = period_returns(res, cfg, panel)
    premier = [a for a, d in cfg.assets.assets.items() if d.group == "premier" and a in rets]
    cond_frames = []
    for col in ("quadrant", "liquidity_driver", "real_rates", "global_order"):
        c = conditional_returns(rets.loc[dev, premier], res.regime.loc[dev, col])
        if len(c):
            cond_frames.append(c.assign(axis=col))
    if cond_frames:
        cond = pd.concat(cond_frames, ignore_index=True)
        cond.to_csv(out_dir / "regime_conditional.csv", index=False)
        quad = cond[cond["axis"] == "quadrant"]
        emp = empirical_matrix(quad, list(cfg.regimes.prior_matrix))
        emp.to_csv(out_dir / "regime_matrix_empirical.csv")
        prior = pd.DataFrame(cfg.regimes.prior_matrix).T
        lines += ["## Regime tests (§9.2)", "",
                  "Empirical regime-fit scores (rank of each asset's annualized return across quadrants, mapped "
                  "to 1-5) next to the priors. Few true regime changes exist, so treat this as directional.", "",
                  "Empirical:", "", emp.round(1).to_markdown(), "", "Prior:", "", prior.to_markdown(), ""]

    # §9.3 portfolio tests
    port = {"model": res.allocation.loc[dev]}
    base = cfg.allocation.base_weights
    port["equal_weight"] = static_weights(dev, {a: 1 / len(base) for a in base})
    port["base_weights"] = static_weights(dev, base)
    for name, w in bt.benchmarks.items():
        port[name] = static_weights(dev, w)
    stats, series = {}, {}
    for name, w in port.items():
        b = backtest(w, rets, cfg.allocation.transaction_cost_bps)
        series[name] = b["return"]
        stats[name] = summary(b["return"], cash, b["turnover"])
    st = pd.DataFrame(stats).T
    st.to_csv(out_dir / "portfolio.csv")
    pd.DataFrame(series).to_csv(out_dir / "portfolio_returns.csv")
    rbr = returns_by_regime(series["model"], res.regime["quadrant"])
    rbr.to_csv(out_dir / "portfolio_by_regime.csv")
    lines += ["## Portfolio tests (§9.3)", "", "Monthly rebalancing, "
              f"{cfg.allocation.transaction_cost_bps:g} bps per unit of turnover.", "",
              st.drop(columns=["start", "end"], errors="ignore").astype(float).round(3).to_markdown(), "",
              "Model returns by regime:", "", rbr.round(3).to_markdown(), ""]

    # §9.4 ablation, measured out of sample
    ab = ablation_table(res, cfg, rets, cash, window=oos_d)
    ab.to_csv(out_dir / "ablation.csv")
    lines += ["## Ablation (§9.4, out of sample)", "",
              "A component earns its place only if removing it lowers Sharpe or deepens the drawdown.", "",
              ab[["sharpe", "max_drawdown", "d_sharpe", "d_max_drawdown", "earns_place"]].round(3).to_markdown(), ""]

    # §14 controls
    groups = {a: d.group for a, d in cfg.assets.assets.items()}
    if any(g == "control" for g in groups.values()):
        cpi = _pit(panel, "cpi", res.dates)
        prices = res.prices.copy()
        if "CASH" in groups and panel.has(cfg.backtest.cash_series):
            prices["CASH"] = (1 + rets["USD"].shift(1).fillna(0)).cumprod() if "USD" in rets else np.nan
        ct = controls_test(res.composite, groups, prices, cpi if cpi.notna().any() else None,
                           bt.controls.forward_years, bt.controls.min_share_months_below, window=oos_d)
        pd.Series(ct, dtype=object).to_json(out_dir / "controls.json", indent=2)
        lines += ["## Control assets (§14, out of sample)", "",
                  f"Controls scored below the premier average in {ct['share_months_controls_below']:.0%} of months "
                  f"(bar: {bt.controls.min_share_months_below:.0%}). Score test passes: {ct['passes_score_test']}. "
                  f"Return test passes: {ct['passes_return_test']}.", ""]

    path = out_dir / "summary.md"
    path.write_text("\n".join(lines))
    return path
