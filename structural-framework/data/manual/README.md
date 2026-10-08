# Manual and paid sources

One CSV per series, named `<series id>.csv`, with columns `date,value` and optionally `published`
(the date the value became public). Without `published`, the lag rule in `config/scoring.yaml`
applies. If a file is missing the metric scores NA and its component renormalizes (§3.2).

Prices can be overridden the same way in `prices/<ticker>.csv` (e.g. `prices/GC_F.csv` for `GC=F`).

| File | Feeds | Units | Source |
|---|---|---|---|
| net_equity_issuance.csv | EQ CAP | % of market cap, trailing 12m | data vendor |
| margin_debt.csv | EQ CAP | $ (level; the YoY is computed) | FINRA |
| forward_eps_yield.csv | EQ VAL | % (forward E/P) | S&P / vendor |
| global_liquidity.csv | EQ, BTC LIQ | index level | Ethan's global liquidity index (M7) |
| top10_weight.csv, pct_above_200d.csv | EQ diagnostics | % | vendor |
| cb_gold_purchases.csv | AU STR, global order | tonnes per quarter | World Gold Council |
| gold_aisc_margin.csv | AU CAP | % | WGC / miner filings |
| gold_etf_tonnes.csv | AU LIQ | tonnes held | WGC |
| cot_gold_mm.csv, cot_crude_mm.csv, cot_usd.csv | LIQ positioning | net contracts | CFTC COT (date = Tuesday as-of) |
| btc_hashrate.csv, btc_active_addresses.csv | BTC STR | level | CoinMetrics / blockchain.com |
| btc_etf_share.csv | BTC STR | % of circulating supply | issuers / Farside |
| btc_mvrv_z.csv | BTC VAL | z-score | Glassnode / CoinMetrics (paid) |
| btc_etf_flows.csv | BTC LIQ | $m per day | Farside |
| stablecoin_supply.csv | BTC LIQ | $ | DefiLlama |
| us_power_consumption.csv | EN STR | GWh per month | EIA |
| world_oil_gas_demand.csv | EN STR | annual, common energy unit | EIA / IEA / Energy Institute |
| en_capex_depr.csv | EN CAP | ratio | company filings / Zacks data |
| rig_count.csv | EN CAP | rigs | Baker Hughes |
| crude_stocks_ex_spr.csv | EN CAP | thousand barrels (EIA WCESTUS1) | EIA |
| wti_curve_spread.csv | EN CAP | $ (front − 12th month) | futures data |
| en_fcf_yield.csv, en_rel_pe.csv | EN VAL | %, ratio | Zacks data |
| usd_reserve_share.csv | USD STR | % | IMF COFER |
| usd_swift_share.csv | USD STR | % (ex-EUR) | SWIFT RMB Tracker |
| foreign_ust_share.csv | USD STR | % | Treasury TIC |
| g10_2y.csv | USD CAP | % (G10 average 2y yield) | central banks |
| tic_lt_flows.csv | USD LIQ | $bn per month | Treasury TIC |
| ism_new_orders.csv | Regime growth fallback | index | ISM |
