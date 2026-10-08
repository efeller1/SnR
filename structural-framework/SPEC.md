# Structural Framework — Technical Specification

Version 0.2 — October 2026. Owner: Ethan Feller.

v0.2 adds: an asset admission test and an expanded universe (§13), control assets (§14), cross-country and monetary-era tests (§15), a full historical replay library (§16), long-run data sources (§17), and the book mapping (§18).

This is the build spec for a scored, dashboard-driven framework for investing alongside structural economic trends. Hand it to Claude Code as the source of truth. Everything here is a default unless marked otherwise. Any default can be changed in config, and every change should be logged.

---

## 1. Purpose and design principles

1. **Layered, slowest to fastest.** Anchor assets rarely change. Regime shifts over quarters. Timing signals update weekly or monthly.
2. **Every score is a written rule.** Each score maps to a data series, a transform, and a direction. Judgment-based scores (structural themes) are allowed, but they must be logged with a date and a rationale.
3. **Point-in-time only.** No signal may use data that wasn't published on the date being scored.
4. **Testable by component.** Each piece must be testable on its own (see §9) before it is trusted in the composite.
5. **Simple first.** Equal weights and percentile scores come first. Optimize only after out-of-sample evidence supports it.

---

## 2. Architecture

| Layer | Name | Question it answers | Update cadence | Nature |
|---|---|---|---|---|
| L1 | Premier assets | What compounds because of how the system works? | Annual review | Thesis + slow metrics |
| L2 | Regime | What environment are we in? | Monthly | Rule-based classifier |
| L3 | Structural trends | Which themes are durable, and where is the bottleneck? | Quarterly | Judgment, logged |
| L4 | Expression | Is it cheap or crowded, and what is the best vehicle? | Monthly | Rule-based |
| L5 | Timing and risk | Are liquidity and price confirming? | Weekly | Rule-based |

**Universe (v0.1)**

| ID | Premier asset | Primary proxy | Secondary proxies |
|---|---|---|---|
| EQ | Equities | S&P 500 total return | MSCI ACWI, equal-weight S&P (RSP) for breadth |
| AU | Gold | Spot gold (USD) | GLD |
| BTC | Bitcoin | BTC/USD | IBIT, FBTC |
| EN | Energy | Energy sector (XLE) | WTI crude, natural gas, XOP |
| USD | US dollar | Broad trade-weighted dollar | DXY |

**The USD has two roles, scored separately:**
- `USD_FIAT`: the dollar against other currencies (the network-dominance thesis).
- `USD_HARD`: the dollar against hard assets, i.e. the debasement thesis, tracked as gold/USD and BTC/USD.

These two can diverge, and the framework expects that they sometimes will.

---

## 3. Scoring methodology (applies to every rule-based metric)

### 3.1 Normalization

For each metric `x_t`:

1. **Point-in-time alignment.** Use first-release (vintage) data where revisions matter, such as GDP, profits, and payrolls. Apply a publication lag: monthly macro +1 month, quarterly macro +2 months, market data +0.
2. **Rolling percentile.** `p_t` is the percentile rank of `x_t` within a trailing window. The default window is 10 years, with a minimum of 5 years of history before a score is issued. Bitcoin uses a 4-year window with a 2-year minimum.
3. **Direction.** If a higher value is bullish for the asset, `d = +1`. If bearish, `d = −1`, and use `p_t = 1 − p_t`.
4. **Map to 1–5.** `s_t = 1 + 4 · p_t` (continuous). Display rounded to one decimal place.

Alternatives Claude Code should support through config: z-score with a ±2σ clip mapped to 1–5, and fixed thresholds for metrics with natural levels (for example, a real yield above 2%).

### 3.2 Aggregation

- **Component score** = weighted mean of its metric scores. Default is equal weights.
- **Missing data:** drop the metric and renormalize the remaining weights. If more than 50% of a component's metrics are missing, the component returns `NA`.
- **Composite score** (per asset) = weighted mean of component scores, using the default weights in §3.3.

### 3.3 Components and default weights

| Component | Code | Layer | Default weight |
|---|---|---|---|
| Structural strength | `STR` | L1 | 0.20 |
| Regime fit | `REG` | L2 | 0.20 |
| Capital cycle / supply | `CAP` | L4 | 0.15 |
| Valuation | `VAL` | L4 | 0.15 |
| Liquidity and flows | `LIQ` | L5 | 0.15 |
| Momentum | `MOM` | L5 | 0.15 |

### 3.4 Stance rules

- **Overweight** if composite ≥ 3.6. **Underweight** if composite ≤ 2.4. **Neutral** otherwise.
- **Hysteresis.** Stance changes only when the composite crosses a threshold by more than 0.1, to prevent flip-flopping.
- **Structural gate.** If `STR` < 2.5, the stance is capped at Neutral, no matter how strong the timing signals are.
- **Momentum veto (optional, off by default).** If `MOM` ≤ 1.5, the stance is capped at Neutral.

### 3.5 Model allocation (optional output)

- **Strategic base weights** `b_i` (config). Default: EQ 40%, AU 15%, BTC 5%, EN 10%, USD cash/T-bills 30%.
- **Tilt.** `w_i = b_i · (1 + k · (C_i − 3) / 2)`, with `k = 0.5` by default. This is clipped to `[0.5 · b_i, 1.5 · b_i]` and then renormalized.
- **Optional volatility targeting** at the portfolio level: 10% annualized by default, using a 60-day EWMA.

These numbers are placeholders for testing, not a recommendation.

---

## 4. Layer 1 — Premier assets: thesis, metrics, and rules

**Source notes**
- Series IDs are FRED unless marked otherwise.
- Every ID should be verified at build time. Some FRED series get discontinued; for example, the LBMA gold price was removed from FRED in 2022.
- Items marked **(paid/manual)** may need a subscription or a manual CSV upload.

### 4.1 EQ — Equities

**Thesis.** Equities are the claim on long-run human economic growth, driven by population, productivity, and innovation. Wealth creation is highly concentrated in a small share of companies, so owning the winners matters as much as owning the market.

**Breaks if** growth stalls permanently, or if profits lose share to labor or the state for a long period.

| Comp | Metric | Construction | Source | Dir |
|---|---|---|---|---|
| STR | Real earnings growth | 5-yr CAGR of trailing real S&P EPS | Shiller data / S&P | + |
| STR | Labor productivity | 5-yr avg YoY of `OPHNFB` | FRED | + |
| STR | Profit share | Corporate profits `CP` / `GDP` | FRED | + |
| CAP | Net equity supply | Net issuance (IPOs + secondaries − buybacks) % of market cap, trailing 12m | Manual / data vendor | − |
| CAP | Margin debt | FINRA margin debt YoY | FINRA | − |
| VAL | CAPE | Shiller CAPE | Shiller data | − |
| VAL | Equity risk premium | Forward earnings yield − 10y real yield (`DFII10`) | S&P / FRED | + |
| LIQ | Global liquidity | Ethan's global liquidity index, 6m change | Internal | + |
| LIQ | Fed net liquidity | `WALCL` − `WTREGEN` − `RRPONTSYD`, 13-wk change | FRED | + |
| MOM | Trend | 12-1 month total return | Prices | + |
| MOM | Trend filter | Price / 200-day moving average | Prices | + |

**Diagnostic panel (displayed, not scored):**
- Top-10 weight in the S&P 500
- % of S&P stocks above their 200-day average
- RSP/SPY ratio

These show how concentrated the market is and whether leadership is broad or narrow.

### 4.2 AU — Gold

**Thesis.** Fiat currencies lose purchasing power over time because governments choose debasement over default. Fiscal dominance and central bank buying strengthen this.

**Breaks if** real interest rates stay high for years alongside genuine fiscal restraint.

| Comp | Metric | Construction | Source | Dir |
|---|---|---|---|---|
| STR | Fiscal deficit | Federal deficit % GDP (`FYFSGDA188S`, inverted sign) | FRED | + |
| STR | Debt burden | Federal debt % GDP (`GFDEGDQ188S`) | FRED | + |
| STR | Interest burden | Federal interest outlays / receipts (`A091RC1Q027SBEA` / `W006RC1Q027SBEA`) | FRED | + |
| STR | Central bank demand | Official-sector net purchases, trailing 4Q | World Gold Council | + |
| CAP | Mine supply response | Price − all-in sustaining cost (AISC) margin, % | WGC / miner filings (manual) | − |
| VAL | Gold vs money supply | Gold price / `M2SL` | Prices / FRED | − |
| VAL | Real-yield residual | Residual of log(gold) regressed on `DFII10` (rolling 10y); z-score | Calculated | − |
| LIQ | ETF flows | Global gold ETF holdings, 3m change in tonnes | WGC | + |
| LIQ | Positioning | CFTC COT managed money net long, percentile | CFTC | − |
| MOM | Trend | 12-1 month return; price / 200DMA | Prices | + |

The gold–real-yield relationship weakened after 2022. Track the regression's rolling R² and set the metric's weight to zero if R² falls below 0.2.

### 4.3 BTC — Bitcoin

**Thesis.** Bitcoin is digital scarcity with a fixed supply, plus a growing network and institutional adoption. Think of it as the high-beta version of the debasement thesis.

**Breaks if** there is a regulatory ban in a major market, a technical or security failure, or adoption stalls.

| Comp | Metric | Construction | Source | Dir |
|---|---|---|---|---|
| STR | Network security | Hash rate, 1-yr growth | CoinMetrics / blockchain.com | + |
| STR | Adoption | Active addresses (30d avg), 1-yr growth | CoinMetrics | + |
| STR | Institutional share | Spot ETF holdings as % of circulating supply | Issuer data / Farside | + |
| CAP | Halving cycle | Days since last halving, mapped to phase (see below) | Calculated | phase |
| VAL | MVRV z-score | (Market cap − realized cap) / std(market cap) | CoinMetrics / Glassnode (paid) | − |
| VAL | 200-week multiple | Price / 200-week moving average | Prices | − |
| LIQ | ETF flows | US spot ETF net flows, 20-day sum | Farside / issuers | + |
| LIQ | Stablecoin liquidity | Total stablecoin supply, 3m change | DefiLlama / CoinMetrics | + |
| LIQ | Global liquidity | Ethan's global liquidity index, 6m change | Internal | + |
| MOM | Trend | 12-1 month return; price / 200DMA | Prices | + |

**Halving dates:** 2012-11-28, 2016-07-09, 2020-05-11, 2024-04-20. The next is expected around April 2028.

**Halving phase rule (prior, to be validated):**

| Days since halving | Phase | Score |
|---|---|---|
| 0–365 | Expansion | 4 |
| 366–550 | Late expansion / topping | 2 |
| 551–900 | Bear / bottoming | 2 → 4 (linear ramp) |
| 901+ | Pre-halving accumulation | 4 |

### 4.4 EN — Energy

**Thesis.** Energy is the base input to all economic output. Demand from AI, electrification, and reshoring is rising while supply has been underinvested.

**Caution.** Energy is a structural trend but a cyclical investment, so the capital-cycle component carries the most weight here.

**Breaks if** demand collapses or there is a step-change in efficiency or supply technology.

| Comp | Metric | Construction | Source | Dir |
|---|---|---|---|---|
| STR | Power demand | US electricity consumption, 3-yr CAGR | EIA | + |
| STR | Global demand | World oil + gas demand, 3-yr CAGR | EIA / IEA | + |
| CAP | Reinvestment rate | Sector capex / depreciation (XLE constituents) | Company filings / vendor | − |
| CAP | Rig count | Baker Hughes US total rigs, YoY | Baker Hughes | − |
| CAP | Inventories | US crude stocks ex-SPR (`WCESTUS1`) vs. 5-yr seasonal avg | EIA / FRED | − |
| CAP | Curve shape | WTI front-month − 12th-month spread (backwardation = positive) | Futures data | + |
| VAL | Free cash flow yield | Sector FCF yield vs. history | Vendor (Zacks data) | + |
| VAL | Relative valuation | XLE forward P/E ÷ S&P 500 forward P/E | Vendor | − |
| LIQ | Positioning | CFTC COT crude managed-money net long | CFTC | − |
| MOM | Relative trend | XLE/SPY 12-1 month; WTI 12-1 month | Prices | + |

Raise `CAP` to 0.25 for EN, and take the extra weight from `STR`.

### 4.5 USD — US dollar

**Thesis.** The dollar is the global network: debt, trade, and reserves run on it, and that network effect is hard to replace. The dollar can win against other fiat currencies while losing against hard assets.

**Breaks if** a credible alternative settlement system gains real share, or the US abuses dollar access (sanctions, capital controls) badly enough to push others to a substitute.

| Comp | Metric | Construction | Source | Dir |
|---|---|---|---|---|
| STR | Reserve share | USD share of allocated FX reserves | IMF COFER | + |
| STR | Payments share | USD share of SWIFT payments (ex-EUR) | SWIFT RMB Tracker (manual) | + |
| STR | Foreign Treasury demand | Foreign holdings % of marketable Treasuries | Treasury TIC | + |
| VAL | Real exchange rate | Real broad dollar (`RBUSBIS`) vs. 20-yr avg | FRED / BIS | − |
| CAP | Rate differential | US 2y − G10 avg 2y | FRED / central banks | + |
| LIQ | Capital flows | TIC net long-term inflows, 3m sum | Treasury TIC | + |
| LIQ | Positioning | CFTC COT USD net long | CFTC | − |
| MOM | Trend | Broad dollar (`DTWEXBGS`) 12-1 month | FRED | + |

**`USD_HARD` panel (displayed, not scored):**
- USD vs. gold
- USD vs. BTC
- M2 growth minus real GDP growth (a debasement pace proxy)

---

## 5. Layer 2 — Regime classifier

### 5.1 Axes

| Axis | Signal | Construction | Source | States |
|---|---|---|---|---|
| Growth | Leading indicator | 6m change in OECD US CLI (or ISM manufacturing new orders if the CLI is unavailable) | OECD / FRED / ISM | Rising / Falling |
| Inflation | Core inflation momentum | Core PCE (`PCEPILFE`) 6m annualized minus 12m YoY | FRED | Rising / Falling |
| Liquidity driver | Monetary vs. fiscal | See §5.2 | Calculated | Monetary-led / Fiscal-led |
| Real rates | 10y TIPS | `DFII10` level and 6m change | FRED | Restrictive (>1.5% and rising) / Neutral / Easy |
| Global order | Dollar system health | Composite of the USD `STR` metrics plus central bank gold buying | Calculated | Unipolar / Fragmenting |

### 5.2 Fiscal dominance index (FDI)

FDI is the equal-weighted mean of the percentile scores of:
- the deficit as % of GDP (larger = more fiscal),
- interest outlays / receipts,
- the 12m change in Fed balance sheet (`WALCL`), inverted (shrinking Fed while the deficit is large = fiscal-led),
- the 12m change in Treasury debt held by the public.

FDI above 0.6 is **Fiscal-led**, and below 0.4 is **Monetary-led**. This should eventually merge with or be replaced by Ethan's global liquidity framework.

### 5.3 Quadrants and regime-fit priors

Quadrant = Growth × Inflation. `REG` for each asset is set from the matrix below. **These are priors only.** Replace them with empirical conditional returns once §9.2 is complete.

| Quadrant | EQ | AU | BTC | EN | USD_FIAT |
|---|---|---|---|---|---|
| Growth ↑ / Inflation ↓ (Goldilocks) | 5 | 2 | 4 | 3 | 2 |
| Growth ↑ / Inflation ↑ (Reflation) | 4 | 4 | 4 | 5 | 2 |
| Growth ↓ / Inflation ↑ (Stagflation) | 1 | 5 | 2 | 4 | 3 |
| Growth ↓ / Inflation ↓ (Deflationary bust) | 2 | 3 | 1 | 1 | 5 |

**Modifiers:**
- Fiscal-led adds +0.5 to AU and BTC.
- Restrictive real rates subtract −0.5 from AU, BTC, and EQ.
- Fragmenting global order adds +0.5 to AU and subtracts −0.5 from USD_FIAT.

All modified scores are clipped to the 1–5 range.

---

## 6. Layer 3 — Structural trends

Trends are judgment-based and stored as one YAML file per trend in `config/trends/`. Each file has a dated history, so past scores are never overwritten.

### 6.1 Schema

```yaml
id: ai_infrastructure
name: AI infrastructure build-out
driver: technology            # demographics | technology | policy | scarcity | monetary
thesis: >
  One plain sentence: what changes and why it can't easily reverse.
linked_premier_assets: [EQ, EN]
durability:
  horizon_years: 10           # expected run length
  reversibility: 2            # 1 = very hard to reverse ... 5 = easy to reverse
  commitment: 5               # 1-5; governments, balance sheets, physical capex lock it in
value_chain:
  - node: semiconductors
    bottleneck: false
  - node: power_generation_and_grid
    bottleneck: true
  - node: data_centers
    bottleneck: false
capital_cycle_stage: expansion  # early_scarcity | expansion | overbuild | bust | consolidation
priced_in: 4                    # 1 = ignored by market ... 5 = fully priced
vehicles:
  - {type: bottleneck_owner, tickers: []}
  - {type: second_order, tickers: []}
kill_criteria:
  - Hyperscaler capex guidance cut for 2 consecutive quarters
  - Bottleneck lead times normalize (e.g., transformer lead times < 12 months)
review_date: 2027-01-15
history:
  - date: 2026-10-08
    scores: {durability: 4.5, cycle: 3, priced_in: 4}
    note: Initial score.
```

### 6.2 Trend scoring

- **Durability** = mean of: `min(horizon_years / 2, 5)`, `(6 − reversibility)`, and `commitment`.
- **Cycle score:** early_scarcity = 5, consolidation = 4, expansion = 3, bust = 2 (rising to 4 when supply exits are confirmed), overbuild = 1.
- **Opportunity** = `0.4 · durability + 0.35 · cycle + 0.25 · (6 − priced_in)`.
- Trends feed the premier-asset `STR` score as an optional overlay: the mean opportunity of linked trends, at 25% weight within `STR`. This is off until validated.

---

## 7. Dashboard specification

### 7.1 Views

1. **Overview.** One row per premier asset and per trend. Columns: STR, REG, CAP, VAL, LIQ, MOM, Composite, Stance, Δ vs. last month, and sparkline. Cells are color-coded on the 1–5 scale.
2. **Regime panel.** Current quadrant, the FDI gauge, the real-rate state, the global-order state, and a timeline of past regimes.
3. **Asset drilldown.** Each metric's raw value, percentile, score, and history chart, plus a "what changed" note listing the metrics that moved the composite most.
4. **Trend cards.** Thesis, value chain with the bottleneck highlighted, capital cycle stage, kill criteria with status flags, and score history.
5. **Model allocation.** Base vs. tilted weights and the drivers of each tilt.
6. **Change log.** Every config change and judgment score, with date and reason.

### 7.2 Snapshots

Each run writes `snapshots/YYYY-MM-DD.json` containing all metric values, scores, the regime, stances, and the config hash. Snapshots are immutable, and they are the live track record.

---

## 8. Repository structure (suggested)

```
structural-framework/
  CLAUDE.md                  # project rules for Claude Code (see §11)
  SPEC.md                    # this document
  config/
    assets.yaml              # metric definitions, sources, directions, weights
    regimes.yaml             # axes, thresholds, prior matrix, modifiers
    scoring.yaml             # windows, stance thresholds, hysteresis, gates
    allocation.yaml          # base weights, k, clip bounds, vol target
    trends/*.yaml
  data/
    raw/                     # untouched downloads, with retrieval date
    processed/               # point-in-time aligned panels (parquet)
    manual/                  # CSVs for paid/manual sources
  src/sf/
    ingest/                  # fred.py, wgc.py, eia.py, imf.py, tic.py, cftc.py, crypto.py, prices.py
    pit/                     # vintage handling, publication lags
    scoring/                 # normalize.py, components.py, composite.py, stance.py
    regime/                  # classify.py, fdi.py
    trends/                  # load.py, score.py
    allocation/              # tilt.py, voltarget.py
    backtest/                # ic.py, conditional.py, portfolio.py, ablation.py, walkforward.py
    dashboard/               # app.py (Streamlit to start)
  snapshots/
  notebooks/
  tests/
```

**Stack:** Python 3.11+, pandas, pyarrow, pydantic (config validation), fredapi / ALFRED for vintages, yfinance or a paid price source, Streamlit for v1 of the dashboard, pytest.

---

## 9. Testing protocol

### 9.1 Component tests (does each piece predict anything?)

For each metric and component, per asset:
- **Information coefficient (IC):** Spearman rank correlation between the score at *t* and the forward return over 1, 3, 6, and 12 months. Report the mean IC, the IC t-stat (with Newey-West adjustment for overlapping returns), and the hit rate.
- **Quintile spreads:** average forward return when the score is in the top vs. bottom quintile.
- **Pass bar (default):** 12m IC ≥ 0.05 with t ≥ 2 in-sample, and the same sign out of sample.

Components that fail are kept on the dashboard but get zero weight in the composite.

### 9.2 Regime tests

- Rebuild the regime history point-in-time.
- For each quadrant and modifier, compute each asset's annualized return, volatility, and hit rate.
- Replace the prior matrix in §5.3 with ranks derived from these numbers, and log both versions.

### 9.3 Portfolio tests

Backtest the model allocation (§3.5) monthly, with 10 bps transaction costs.

**Benchmarks:**
- (a) equal weight across the five assets
- (b) the strategic base weights with no tilts
- (c) 60/40
- (d) 100% S&P 500

**Report:** CAGR, volatility, Sharpe, max drawdown, turnover, and returns by regime.

### 9.4 Ablation

Re-run §9.3 removing one component at a time, and then removing one layer at a time. A component earns its place only if removing it worsens out-of-sample Sharpe or drawdown.

### 9.5 Robustness

- **Walk-forward:** expanding window, re-estimated annually, with a final 5-year holdout that is never touched during development.
- **Cross-country check of L1 logic:** test equity compounding and hard-asset performance during debasement episodes across major markets, using long-run global returns data. This checks survivorship bias in the US-centric thesis.
- **Parameter sensitivity:** percentile windows of 5, 10, and 15 years; stance thresholds ±0.2; and k from 0.25 to 1.0.

### 9.6 Historical replay (L3)

The full replay library and protocol are in §16. The short version is below.

Score past trends using only contemporaneous information, and store the results as `config/trends/historical/*.yaml`. Candidates: railroads (1840s), electrification (1900–1930), autos (1910–1930), oil (1970s), fiber and internet (1995–2002), and shale (2010–2020). Check whether the opportunity score would have flagged the overbuild phase before the bust. This doubles as book material.

### 9.7 Known biases to guard against

- **Look-ahead:** revised data, or index membership that wasn't known at the time.
- **Survivorship:** in asset selection, and in the US-only history.
- **Overfitting:** limit tuned parameters, prefer equal weights, and keep the holdout untouched.
- **Small sample:** fifty years contain only a handful of true regime changes, so treat regime results as directional evidence, not proof.

---

## 10. Build milestones

1. **M1 — Data spine.** FRED and price ingestion, point-in-time alignment, and the processed panel for 1990–present (BTC from 2013).
2. **M2 — Scoring engine.** Normalization, components, composite, stance, and snapshot writer. Unit tests on toy data.
3. **M3 — Regime classifier.** FDI, quadrants, modifiers, and the regime history.
4. **M4 — Dashboard v1.** Overview, regime panel, and asset drilldown in Streamlit.
5. **M5 — Backtests.** Component ICs, regime conditional returns, portfolio backtest, and ablation.
6. **M6 — Trends.** YAML loader, trend scoring, trend cards, and historical replays.
7. **M7 — Integrate the global liquidity index** as the LIQ input and possible FDI replacement.
8. **M8 — Hardening.** Paid data sources, scheduled runs, and alerts on stance changes and kill-criteria triggers.
9. **M9 — Universe expansion.** Run the admission test (§13) on candidate assets, and add the control assets (§14).
10. **M10 — Long-run history.** Ingest the long-run datasets (§17) and run the cross-country and monetary-era tests (§15).
11. **M11 — Replay library.** Build the historical replays (§16) as structured YAML, with an evidence log for each.

---

## 11. Suggested CLAUDE.md contents

- SPEC.md is the source of truth. Propose spec changes before implementing behavior that differs from it.
- Never use data unavailable at the scoring date. Every ingest function must return publication dates.
- No hard-coded parameters. Everything lives in `config/` and is validated by pydantic.
- Snapshots are append-only. Never rewrite history.
- Every new metric needs: a source, a construction, a direction, a test, and an IC report before it gets a nonzero weight.
- Prefer simple, readable code over cleverness. Explain results in plain English.

---

## 12. Open decisions for Ethan

1. Strategic base weights for the five premier assets (§3.5 placeholders).
2. Whether `MOM` can veto a stance (§3.4), or only inform it.
3. Data budget for paid sources: Glassnode, Bloomberg/FactSet, or Zacks internal data, which covers capex, FCF yields, and forward P/E.
4. Whether energy is scored on the commodity, the equities, or both as separate rows.
5. How the global liquidity index is defined and weighted (§5.2, M7).
6. Which structural trends to load first. Suggested: AI infrastructure, power and grid, fiscal dominance as a theme, and reshoring.
7. Which candidate assets to run through the admission test first (§13.3).
8. Whether to pay for long-run return data (Dimson-Marsh-Staunton, Global Financial Data) or start with free sources (§17).
9. The book's single core thesis sentence (§18). Every chapter should prove it from a new angle.

---

## 13. Expanding the asset universe

### 13.1 Admission test

A candidate becomes a premier asset only if it passes all four tests below. The results are documented in `config/universe/<asset_id>.yaml`.

| # | Test | Pass criterion |
|---|---|---|
| A1 | Structural reason to compound | A one-sentence mechanism tied to how the economic or monetary system works, not to a theme or product cycle |
| A2 | Falsifiable "breaks if" | At least one observable condition that would invalidate the thesis, with a metric attached |
| A3 | Testable history | ≥ 30 years of price data (≥ 10 for digital assets), ideally across more than one country or monetary era |
| A4 | Investable | A liquid vehicle exists today (ETF, futures, listed equities, or spot) |

**Further admission rules:**
- **Distinctiveness.** The asset's 10-year rolling correlation with every existing premier asset must stay below 0.8. Otherwise it is a duplicate exposure and gets classed as a *satellite*, not a premier asset.
- **Tiers:**
  - **Premier:** passes A1–A4 and the distinctiveness rule.
  - **Satellite:** passes A1, A2, and A4, but has limited history or overlaps another asset. It is displayed and scored, with zero weight in the model allocation.
  - **Watchlist:** passes A1 only. It is tracked for evidence.

### 13.2 Admission file schema

```yaml
id: CU
name: Copper
tier: candidate            # candidate | watchlist | satellite | premier
mechanism: >
  Electrification and grid build-out need copper, with no easy substitute at scale;
  new mines take 10+ years to develop.
breaks_if:
  - Substitution (e.g., aluminum) gains share at scale
  - Demand from China construction collapses without offsetting grid demand
tests:
  A1: pass
  A2: pass
  A3: {years_of_data: 60, countries: [US, UK], result: pass}
  A4: {vehicles: [HG futures, CPER, COPX], result: pass}
  max_corr_vs_premier: {asset: EN, value: 0.55}
decision: satellite
decision_date: 2026-10-08
notes: Re-test after 3 years of live scores.
```

### 13.3 Candidate assets

| ID | Candidate | Proposed mechanism | Key metrics to build | Likely tier |
|---|---|---|---|---|
| RE | Land and real estate | Fixed land supply plus population and income growth | Real home prices, price-to-rent, price-to-income, housing starts vs. household formation, mortgage rates | Premier candidate |
| CU | Copper and grid metals | Physical bottleneck of electrification; long mine lead times | Mine supply growth, LME/COMEX inventories, smelter treatment charges, grid capex | Satellite → Premier |
| AG | Silver | Monetary-metal cousin of gold plus industrial (solar) demand | Gold/silver ratio, solar demand, ETF holdings, mine supply | Satellite (gold overlap) |
| FL | Farmland | Fixed arable land, rising food demand, inflation hedge | Farmland values vs. cash rents, crop prices, real rates | Satellite (limited liquid vehicles) |
| WA | Water | Scarcity plus infrastructure underinvestment | Utility capex, water rights prices (where available), drought indices | Watchlist |
| EM | Emerging-market equities | Tests whether the "human growth" thesis holds outside the US | Real GDP per capita growth, EPS growth, CAPE, dollar strength | Premier candidate (key thesis test) |
| UR | Uranium / nuclear | Baseload power for AI and decarbonization; long supply lead times | Term contract price, reactor build pipeline, utility inventory cover | Satellite |
| INFRA | Listed infrastructure | Toll-road-style ownership of physical bottlenecks | Contracted revenue share, inflation linkage, regulated returns | Satellite |

---

## 14. Control assets (what the thesis says should lose)

Control assets are scored with the same engine. The framework passes only if it ranks them correctly **out of sample**. This is the main defense against hindsight bias in picking the premier assets.

| ID | Control | Why the thesis says it should lag | Expected result |
|---|---|---|---|
| LTB | Long-dated nominal Treasuries | Under fiscal dominance and debasement, real returns on long fixed-rate debt erode | Low STR, Underweight in fiscal-led regimes |
| CASH | Cash / T-bills (real return) | Fiat loses purchasing power over long periods | Low long-run real return; useful only as a defensive sleeve |
| AIR | Airlines | The classic "real trend, poor shareholder returns" case: capital floods in and returns get competed away | Low CAP across most of its history |
| TEL | Telecom carriers | A heavy-capex industry where users captured the gains of a structural trend | Low CAP, low long-run excess return |
| EMFX | EM currencies (basket) | They lose to the dollar network and to hard assets | Low STR vs. USD_FIAT and AU |
| UTIL_OLD | Pre-2020 regulated utilities | Capped returns; tests whether the energy-demand thesis leaks into the wrong vehicles | Mid; should improve only where a bottleneck exists |

**Pass criteria:**
- The average composite score of the controls must be below the average of the premier assets in ≥ 70% of months.
- The controls' realized forward 5-year real returns must rank below the premier assets in the out-of-sample period.

If the framework can't separate winners from losers this way, its asset-selection layer is not adding information.

---

## 15. Cross-country and monetary-era tests

### 15.1 Purpose

These tests check the **logic** of each premier asset, not just its US track record. Every L1 thesis should hold in at least two settings beyond the one it was built on.

### 15.2 Case library

| Case | Period | Tests which thesis | Question to answer |
|---|---|---|---|
| Sterling → dollar handover | 1914–1956 | USD_FIAT | What were the leading indicators of reserve-currency loss (debt, reserve share, trade invoicing, war finance), and how long did the handover take? Which of those signals is the US flashing today? |
| Dutch guilder decline | 1720–1795 | USD_FIAT | How did the prior reserve currency fade? |
| Weimar Germany | 1919–1923 | AU, EQ | How did hard assets, equities, and real estate perform in hyperinflation, in real terms? |
| UK in the 1970s | 1970–1980 | AU, EQ, EN | Stagflation with a weakening currency: which assets preserved purchasing power? |
| US in the 1970s | 1971–1982 | AU, EN, LTB | The first fiat decade: gold, oil, and the bond bear market |
| Argentina | 1975–present (multiple episodes) | AU, BTC (2014+), EQ | Repeated debasement: does the hard-asset thesis hold across several episodes? |
| Japan after 1990 | 1990–2012 | EQ, RE | When does the equity "human growth" thesis fail? Starting valuation, demographics, and debt deflation |
| Post-WWII financial repression | 1945–1980 | LTB, AU, EQ | How governments inflate away debt with negative real rates — the closest analog to fiscal dominance today |
| Emerging-market crises | 1982, 1997, 2001, 2018 | EMFX, USD_FIAT | The dollar wrecking-ball effect in tightening cycles |

### 15.3 Monetary-era panel

Score each premier asset's real return, volatility, and drawdown within each era. Then check whether the regime classifier (§5) identifies the same patterns.

| Era | Approx. dates | Defining rule |
|---|---|---|
| Classical gold standard | 1870–1914 | Currency convertible to gold; little inflation |
| War and interwar | 1914–1944 | Suspended convertibility; war finance; deflation then reflation |
| Bretton Woods | 1944–1971 | Dollar pegged to gold; others pegged to the dollar; capital controls |
| Early fiat / stagflation | 1971–1982 | Floating currencies; high inflation; oil shocks |
| Great Moderation | 1982–2007 | Independent central banks; falling inflation and rates |
| QE era | 2008–2019 | Monetary-led liquidity; zero rates; asset inflation |
| Fiscal dominance | 2020– | Large deficits drive liquidity; central banks constrained |

### 15.4 Pass criteria

For each L1 thesis, document in `reports/l1_tests/<asset>.md`:
- the settings where it held, the settings where it failed, and why;
- whether the failures match the asset's "breaks if" conditions.

A failure that matches a stated "breaks if" condition **supports** the framework. A failure that doesn't means the thesis needs revising.

---

## 16. Historical trend replay library

### 16.1 Protocol

1. **Information cutoff.** Each replay is scored at several dates (for example, early, mid, and peak of the boom) using only sources available at that date: contemporary newspapers, company reports, and economic data as first published.
2. **Score with the L3 schema (§6.1):** driver, durability, value chain and bottleneck, capital-cycle stage, priced-in, and vehicles.
3. **Record the outcome** afterward: the trend's real economic impact, investor returns by value-chain node, and who captured the profits.
4. **Grade the framework.** Did the opportunity score fall before the bust? Did the bottleneck call identify the nodes that kept the returns?

### 16.2 Library

| Replay | Period | Bottleneck / lesson to test | Book role |
|---|---|---|---|
| Canals (UK and US) | 1790–1840 | Early infrastructure mania; a superior technology (railroads) arrived mid-cycle | Opening example of a trend overtaken by the next one |
| Railroads (UK mania, US build-out) | 1840s; 1860–1900 | The trend was transformative but most investors lost money; land grants and monopoly routes captured value | Core case: right trend, wrong vehicle |
| Electrification | 1890–1930 | Utility holding-company leverage; equipment makers vs. utilities vs. users | Bottleneck shifts along the value chain |
| Autos and radio | 1910–1929 | Hundreds of automakers consolidated to three; radio stocks in the 1929 peak | Competition destroys returns; leaders emerge late |
| Postwar suburbanization | 1946–1970 | Land, homebuilders, highways, and autos as one linked trend | A policy-driven trend (GI Bill, highways) |
| Nifty Fifty | 1965–1974 | Great companies at bad prices | Valuation beats quality at the extremes |
| 1970s oil and gold | 1971–1981 | Hard assets in a new fiat regime; an energy supply shock | Regime layer in action |
| Japan's bubble | 1985–1990 | Land and equities with debt; demographics | When "growth compounds" breaks |
| Internet and fiber | 1995–2002 | Fiber overbuilt by about 95%; users and later platforms captured value | The capital cycle at its most extreme |
| China commodity supercycle | 2002–2015 | Iron ore, copper, and shipping capacity overshoot | Supply response kills returns |
| Shale | 2008–2020 | Technology success, negative free cash flow, investor losses | Energy as a cyclical investment |
| Smartphones / mobile | 2007–2020 | Value concentrated in one platform plus app layers | Power-law winners |
| Cloud and SaaS | 2010–2021 | Recurring revenue; multiple expansion and compression | Priced-in risk |
| AI infrastructure (live) | 2023– | GPUs → power and grid → ? | The present-day application of every lesson |

### 16.3 Files

- `config/trends/historical/<replay_id>.yaml`: the L3 schema, plus `information_cutoff_dates`, `outcome`, and `framework_grade`.
- `reports/replays/<replay_id>.md`: narrative, charts, sources, and a lessons section. This is written so it can become a book chapter draft.

---

## 17. Long-run data sources

| Source | Coverage | Access | Use |
|---|---|---|---|
| Jordà-Schularick-Taylor Macrohistory Database | 18 advanced economies, 1870–present; returns on equities, bonds, housing, bills; macro and credit data | Free | Cross-country L1 tests; monetary-era panel |
| Bank of England — "A millennium of macroeconomic data" | UK, 1200s–2016 | Free | Sterling handover; long-run UK prices, rates, and money |
| Shiller data | US equities, earnings, CAPE, rates, 1871–present | Free | EQ history; valuation tests |
| FRED / ALFRED | US macro, with historical vintages | Free | Point-in-time US data |
| IMF COFER, BIS, World Bank | Reserves, exchange rates, debt | Free | USD and EM tests |
| World Gold Council | Gold prices, central bank purchases, ETF holdings | Free (registration) | AU |
| Energy Institute Statistical Review | Global energy production and consumption, 1965– | Free | EN |
| Dimson-Marsh-Staunton (UBS Global Investment Returns Yearbook) | Equity, bond, bill, and currency returns, 35+ countries, 1900– | Paid | Strongest cross-country survivorship test |
| Global Financial Data | Very long price histories across assets and countries | Paid | Replays and pre-1900 cases |
| Historical newspaper archives (e.g., ProQuest Historical Newspapers) | Contemporary coverage | Paid / library | Information-cutoff scoring for replays |

All long-run data goes into `data/longrun/`, with source, retrieval date, and known gaps documented in `data/longrun/README.md`.

---

## 18. Book mapping

**Working premise.** The framework is the book's backbone, and the repo produces its evidence. Every chapter should prove one core thesis from a new angle. Draft thesis, for Ethan to refine:

> A few assets compound because of how the economic and monetary system works. Structural trends decide where growth shows up, but the capital cycle decides who keeps the money.

| Part | Content | Spec sections that feed it |
|---|---|---|
| I. The framework | Why structural trends matter; the five layers; bottlenecks and the capital cycle | §1–3, §6 |
| II. The premier assets | One chapter each: equities, gold, Bitcoin, energy, the dollar. Each has its thesis, history, "breaks if," and evidence across countries and eras | §4, §13, §15 |
| III. The replays | Historical trends scored as if in real time, including the failures and control cases | §14, §16 |
| IV. Regimes | Monetary eras and the shift to fiscal dominance | §5, §15.3 |
| V. Today | AI infrastructure, power, fiscal dominance, and the live dashboard as a companion to the book | §7, §16 (AI live case) |

**Workflow:**
- Each `reports/replays/*.md` and `reports/l1_tests/*.md` file is written as a rough chapter draft.
- Charts are generated from the repo, so every figure in the book is reproducible.
- The live dashboard and its snapshot log become the book's ongoing track record, and a reason for readers and event audiences to keep following.
