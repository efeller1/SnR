# SnR: screening for Natera-like stocks

This is a point-in-time screen for US stocks that look like Natera (NTRA) did in 2022–23. It looks for:

- fast, accelerating revenue growth
- few analysts, little news and little social or options activity for the company's size
- a stock price that has just started moving on company-specific news rather than with the market or its sector

## Running it

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name you@example.com"   # SEC requires a contact string

python -m snr build-facts                  # once: EDGAR bulk XBRL -> data/cache/facts.parquet
python -m snr validate --start 2021 --end 2024   # reports/validation.md (+ CSVs)
python -m snr screen                       # today's list -> reports/screen_<date>.md (+ CSVs)
python -m pytest -q                        # offline tests on synthetic data
```

These hosts must be reachable:

- `www.sec.gov` and `data.sec.gov`: fundamentals and SIC codes
- `query1.finance.yahoo.com`, `query2.finance.yahoo.com` and `fc.yahoo.com`: prices, analyst counts and options
- `api.gdeltproject.org`: news counts
- `www.reddit.com`: current social mentions only
- `api.x.com`: optional, needs `X_BEARER_TOKEN`

## The screen

The steps run in this order. Every threshold is set in `snr/config.py`.

| Step | Rule | Where |
|---|---|---|
| Universe | Listed on NYSE, Nasdaq or Cboe. Market cap $2–50B, computed as the as-traded price × shares from the cover page of the last filing. Average daily dollar volume over 63 days above $10M. Excludes SIC 6770 (SPACs), 6798 (REITs) and 6722/6726/6799 (funds). ADRs drop out because they file 20-F/40-F, not 10-Q. | `screen.py` |
| Filter 1 | Year-over-year revenue growth above 20% in the latest quarter. The latest quarter's growth must beat the average of the prior two quarters. The gross margin slope over 4 quarters must be at least −0.5pp per quarter, and the net change at least −1pp. When `unit_volumes.csv` has data, unit growth must be at least 50% of revenue growth. No profitability test. | `fundamentals.py` |
| Filter 2 | Each attention measure is regressed on log(market cap) across the names being ranked, and the residual is converted to a percentile. The percentiles are averaged, and names at or below the 40th percentile pass. | `attention.py` |
| Filter 3 | Daily returns over 252 days are regressed on market (SPY), sector (sector SPDR − SPY), size (IWM − SPY), value (IWD − IWF), momentum (MTUM − SPY) and quality (QUAL − SPY). A name passes when all of these hold: R² < 0.35; 3-month and 6-month residuals are positive; the 6-month residual is in the top 30% of the names that reached this step; and the cumulative residual over the 12 months *before* those 6 months is at most +5%. | `residual.py` |
| Length | If more than 30 names pass on a date, the screen reruns with growth of 30% or more and acceleration in at least 2 consecutive quarters. | `screen.py` |

## Point-in-time rules

- **Fundamentals:** a figure is used only if its filing date is on or before the screening date. For each quarter, the screen takes the latest value known on that date, so a restatement is invisible until it is filed. Q4 figures come from the 10-K (annual total minus the 9-month year-to-date, or minus Q1–Q3), so they count as known on the 10-K's filing date.
- **Prices and factors:** only data on or before the screening date is used. Factors are built from ETFs instead of Ken French's library because his data is published with a delay.
- **Tests:** `tests/` checks that unfiled quarters and restatements stay hidden and that returns after the screening date don't change the results.

## Known limitations (read before trusting a backtest)

1. **Survivorship.** EDGAR has no history of tickers, so the universe is today's listings. Companies acquired or delisted since a backtest date are missing, which probably makes the hit rate look better than it was.
2. **Attention history is not free.**
   - What the backtest uses: GDELT news counts, which are point-in-time, and share turnover as a stand-in. Turnover is only used when fewer than 2 of the 4 real measures are available.
   - What only works for today's screen: Yahoo analyst counts, Yahoo options volume and Reddit mentions.
   - For a faithful backtest: put I/B/E/S analyst counts, OptionMetrics volume and archived social counts in `data/manual/attention.csv` (`ticker,date,measure,value`, where measure is `analysts`, `news_90d`, `social_90d` or `options_ratio`).
3. **Unit volumes** (tests, users, units shipped) are not in XBRL. Add them to `data/manual/unit_volumes.csv`. Without them, the check that growth is volume-driven is skipped and the report says so.
4. **Sector** comes from an approximate SIC-to-GICS mapping, using today's SIC code.
5. **Filter 2 ranking group.** Filter 2 ranks names against the other Filter 1 survivors in the universe, not against every stock. When fewer than 3 names reach it, nothing passes.
