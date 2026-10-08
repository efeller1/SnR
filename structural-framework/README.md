# Structural Framework

A scored, layered framework for investing alongside structural economic trends. `SPEC.md` (v0.2) is
the source of truth; `CLAUDE.md` has the working rules; `docs/spec_gaps.md` lists every default the
build had to choose where the spec was silent.

## Quick start

```bash
cd structural-framework
pip install -e ".[dev,dashboard]"
export FRED_API_KEY=...                  # optional: ALFRED first-release values (otherwise latest + lag rule)
python -m sf ingest                      # FRED, Yahoo, Shiller, manual CSVs -> data/processed/panel.parquet
python -m sf run --date 2026-10-08       # score one date, write snapshots/2026-10-08.json (immutable)
python -m sf history                     # monthly history 1990-today for the dashboard
python -m sf backtest                    # §9 reports -> reports/backtest/<date>/
python -m sf trends                      # score config/trends/*.yaml
python -m sf universe                    # check config/universe/*.yaml admission files
streamlit run src/sf/dashboard/app.py
python -m pytest -q                      # offline tests on synthetic data
```

## How a score is made

1. **Ingest** (`src/sf/ingest/`). Every series comes back as `date, value, published`. `published` is
   the ALFRED first-release date when available, otherwise the end of the period plus the lag in
   `config/scoring.yaml` (monthly +1m, quarterly +2m, market data +0).
2. **Metric** (`src/sf/metrics.py`, `src/sf/transforms.py`). A formula over series IDs, then steps such
   as `pct_change`, `cagr`, `mom_12_1`, `ma_ratio` or `rolling_residual`, all defined in
   `config/assets.yaml`. Inputs are aligned on the date each value was published, so the value on a
   scoring date uses only what was public then.
3. **Score** (`src/sf/scoring/`). Rolling percentile (10y window, 5y minimum; BTC 4y/2y), flipped for
   bearish metrics, mapped to 1–5. Z-score, fixed thresholds and raw scores are also supported.
4. **Components and composite.** Equal-weighted metrics per component (missing ones dropped; NA if more
   than half are missing), then the §3.3 component weights (EN: CAP 0.25, STR 0.10).
5. **Regime** (`src/sf/regime/`). Growth × inflation quadrant, FDI, real rates and global order set
   `REG` from the prior matrix and modifiers in `config/regimes.yaml`.
6. **Stance** with ±0.1 hysteresis, the STR < 2.5 gate, and an optional momentum veto (off).
7. **Allocation.** Base weights tilted by `k (C − 3) / 2`, clipped to 0.5–1.5× base.

`tests/test_sf_end_to_end.py::test_scores_at_t_ignore_data_after_t` runs the whole stack twice, once
with all data and once with everything published after *t* deleted, and checks the scores at *t* match.

## Build status by milestone

| Milestone | Status |
|---|---|
| M1 Data spine | Done for FRED (21 series), Yahoo prices (9), Shiller. 33 manual/paid series have loaders and documented CSV formats (`data/manual/README.md`) but no data yet |
| M2 Scoring engine | Done: normalization (percentile, z-score, threshold, raw), components, composite, stance, snapshots, what-changed |
| M3 Regime classifier | Done: FDI, quadrants, real rates, global order, modifiers, regime history |
| M4 Dashboard v1 | Done: all six §7.1 views in Streamlit |
| M5 Backtests | Done: ICs with Newey-West t, quintile spreads, regime-conditional returns, empirical matrix, portfolio vs. four benchmarks, ablation, walk-forward splits with an untouched 5-year holdout |
| M6 Trends | Loader, scoring, point-in-time history, overlay (off), trend cards. `ai_infrastructure` loaded from the spec example; replay template in `config/trends/historical/` |
| M7 Global liquidity | Waiting on the index definition (open decision #5); wired as `data/manual/global_liquidity.csv` |
| M8 Hardening | Not started |
| M9 Universe | Admission schema, tiering and distinctiveness check; `CU` from the spec. Controls `LTB` and `CASH` scored; the other four are listed in `config/controls.yaml` |
| M10–M11 | Folders and READMEs only |

## First real run (2026-10-08, free data only)

The first backtest is in `reports/backtest/2026-10-08/summary.md`. Treat it as a test of the
plumbing, not of the thesis: only FRED, Yahoo and Shiller data are loaded, and many components are
NA until the manual and paid sources arrive.

- **Regime today:** Goldilocks (CLI rising, core PCE momentum slightly falling), real rates
  Restrictive (10y TIPS 2.91%, up 0.93pp over 6 months), FDI 0.58 (Balanced, just under the 0.6
  Fiscal-led line it sat above for most of the past year), global order unknown (no COFER/SWIFT/TIC data yet).
- **§9.1:** 2 of 33 testable signals pass the 12-month bar (gold/M2 and the gold VAL component).
- **§9.3 (1990–2021, development period):** model Sharpe 0.70 vs. 0.69 for the untilted base weights
  and 0.59 for 60/40, so the tilt adds little so far.
- **§14:** controls scored below the premier average in 64% of out-of-sample months, under the 70% bar.
