# Where the spec was silent: defaults chosen in the build

SPEC.md is the source of truth. These are the places it didn't say, and the default the code uses.
Every one is a config value (or a one-line code rule, as noted) and is open for Ethan's review.

| # | Topic | Default chosen | Where |
|---|---|---|---|
| 1 | Publication lag for annual data (e.g. `FYFSGDA188S`) | 6 months after year end | `scoring.yaml: publication_lag_months.annual` |
| 2 | Lags for weekly / non-standard sources | H.4.1 (`WALCL`, `WTREGEN`) and `RRPONTSYD` +1 day; CFTC COT +3 days; EIA crude stocks +5 days; EIA power and TIC +2 months; IMF COFER +3 months; Shiller earnings +6 months | `assets.yaml` (`lag_days`, `lag_months`), `sources.yaml` |
| 3 | Stale data | A value counts as missing once its oldest input was published more than N days ago: daily 10, weekly 21, monthly 70, quarterly 190, annual 550 | `scoring.yaml: stale_after_days` |
| 4 | Mixed-frequency formulas (e.g. gold / M2) | Inputs are aligned on the date each value was published and carried forward, so a formula uses the latest value of every input that was public on the scoring date | `src/sf/metrics.py` |
| 5 | Percentile details | Window includes x_t; ties take the mid-rank; the 5-year minimum counts from the metric's first valid value | `src/sf/scoring/normalize.py` |
| 6 | Composite with missing components | Renormalize over present components; NA if more than 50% of component weight is missing | `scoring.yaml: aggregation.composite_max_missing_weight` |
| 7 | Hysteresis | First stance uses the plain thresholds. After that, a change needs the composite to cross by **more than** 0.1. The band applies to leaving a stance too (Overweight holds until < 3.5). Caps (structural gate, momentum veto) don't reset the hysteresis state | `src/sf/scoring/stance.py` |
| 8 | Gold real-yield gate | While rolling R² < 0.2 the residual metric gets weight 0 and is excluded from the component (not counted as missing) | `assets.yaml: gate` |
| 9 | Real-rate "Easy" state | 10y TIPS below 0.5% | `regimes.yaml: real_rates.easy_level` |
| 10 | FDI between 0.4 and 0.6 | Labeled "Balanced" (no modifier) | `src/sf/regime/fdi.py` |
| 11 | Global order | Mean of the USD STR metric scores and (6 − central-bank gold-buying score); below 3.0 = Fragmenting | `regimes.yaml: global_order` |
| 12 | Regime-fit for control assets | No prior row, so REG is NA and the composite renormalizes | `regimes.yaml: prior_matrix` |
| 13 | Calendar | All layers score month-end. Setting `calendar: W-FRI` gives the weekly L5 cadence (all layers then score weekly) | `scoring.yaml: calendar` |
| 14 | Price proxies | Adjusted close = total return. Spot gold uses the COMEX front-month future (`GC=F`, from 2000) because LBMA left FRED in 2022 | `assets.yaml: series` |
| 15 | Fed net liquidity units | `WALCL − WTREGEN − RRPONTSYD × 1000` (RRP is in $bn; the others in $m) | `assets.yaml: eq_fed_net_liq` |
| 16 | US power demand | 12-month rolling sum before the 3-year CAGR, to remove seasonality | `assets.yaml: en_power` |
| 17 | Bitcoin windows | "20-day" ETF flows = 28 calendar days; 200-week MA = 1,400 calendar days | `assets.yaml` |
| 18 | 12-1 momentum | Price 1 month ago / price 12 months ago − 1, each looked up within 10 days | `src/sf/transforms.py` |
| 19 | Allocation clip | Clip and renormalize repeat until every weight is inside its band. Missing composite = no tilt. The USD sleeve earns 3-month T-bills | `src/sf/allocation/tilt.py`, `backtest.yaml` |
| 20 | Vol targeting | Never levers above 100%; the remainder sits in cash | `allocation.yaml: vol_target.max_leverage` |
| 21 | IC hit rate | Share of months where (score − 3) and (forward return − median forward return) have the same sign | `src/sf/backtest/ic.py` |
| 22 | In-sample / out-of-sample for §9.1 | Development period = everything before the 5-year holdout; its last 33% is out of sample | `backtest.yaml: oos_fraction` |
| 23 | Empirical regime matrix (§9.2) | Each asset's annualized return is ranked across the four quadrants (down the column, as the prior reads) and mapped to 1–5 | `src/sf/backtest/conditional.py` |
| 24 | Trend history | Each dated entry can carry the full judgment (durability inputs, stage, priced_in); missing fields carry forward. `supply_exits_confirmed: true` scores a bust as 4 | `src/sf/trends/` |
