# Series verification (build time, 2026-10-08)

The spec asks that every ID be verified at build time. Checked against `fredgraph.csv` and Yahoo.

| Series | Result | Last observation |
|---|---|---|
| OPHNFB, CP, GDP, GDPC1, A091RC1Q027SBEA, W006RC1Q027SBEA | OK | 2026-04-01 (Q2) |
| DFII10, DGS2, DGS10 | OK | 2026-10-06 |
| WALCL, WTREGEN | OK | 2026-09-30 |
| RRPONTSYD | OK | 2026-10-07 |
| FYFSGDA188S | OK (annual, fiscal year) | 2025 |
| GFDEGDQ188S, FYGFDPUN | OK | 2026-01-01 (Q1) |
| M2SL, PCEPILFE, CPIAUCSL | OK | 2026-08 |
| RBUSBIS | OK | 2026-07 |
| DTWEXBGS | OK | 2026-10-02 |
| TB3MS | OK | 2026-09 |
| **USALOLITONOSTSAM** (OECD CLI, normalised) | **Stale: last value 2024-01** | replaced by **USALOLITOAASTSAM** (amplitude adjusted), last 2026-08 |
| **WCESTUS1** (crude stocks ex-SPR) | **Not a FRED series** (it is an EIA ID) | moved to a manual EIA CSV |
| LBMA gold | Not on FRED since 2022 (as the spec notes) | `GC=F` from Yahoo instead |
| CBBTCUSD (Coinbase BTC) | OK on FRED from 2014-12 | available as a fallback; `BTC-USD` from Yahoo is primary |
| ISM new orders | Not on FRED (ISM withdrew it) | manual CSV fallback for the growth axis |
| Shiller `ie_data.xls` (free) | Downloads, but the public file ends 2024-09 (earnings 2024-06) | CAPE and real EPS go stale (NA) after that until refreshed |
| Yahoo prices (^SP500TR, SPY, RSP, GC=F, BTC-USD, XLE, CL=F, AGG, VUSTX) | OK via yfinance (raw HTTP gets rate-limited) | 2026-10-07 |

No `FRED_API_KEY` was set during the build, so every series uses latest values with the
publication-lag rule (`pit = lagged` in `data/processed/ingest_report.csv`). Set the key to get
ALFRED first-release values for the series marked `vintage: first_release`.
