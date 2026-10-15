"""Dual Momentum as a 130/30: 130% long the model, 30% short SPY or IWM.

Monthly portfolio return = 1.30 * model - 0.30 * hedge - borrow/12, rebalanced
back to 130/30 each month. The short proceeds pay for the extra 30% long, so
there is no margin interest; the short pays the ETF's dividends (adjusted-close
total returns). Usage: python scripts/dual_momentum_130_30.py [workbook.xlsx] [borrow_bps]
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd, yfinance as yf
from dual_momentum_load import load, F

LONG, SHORT = 1.30, 0.30

def etf_monthly(tickers, start, end):
    px = yf.download(tickers + ["BIL"], start=start, end=end, auto_adjust=True, progress=False)["Close"]
    m = px.resample("ME").last().pct_change()
    m.index = pd.MultiIndex.from_arrays([m.index.year, m.index.month], names=["year", "month"])
    return m

def stats(r, rf, spy):
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    ex = r - rf
    return {
        "CAGR": eq.iloc[-1] ** (1 / yrs) - 1,
        "Total return": eq.iloc[-1] - 1,
        "Vol / yr": r.std() * np.sqrt(12),
        "Sharpe": ex.mean() / ex.std() * np.sqrt(12),
        "Max drawdown": (eq / eq.cummax() - 1).min(),
        "Beta to SPY": np.cov(r, spy)[0, 1] / spy.var(),
        "Worst month": r.min(),
        "Best month": r.max(),
        "Up months": (r > 0).mean(),
    }

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else F
    borrow = (float(sys.argv[2]) if len(sys.argv) > 2 else 0) / 1e4
    d = load(path).set_index(["year", "month"])
    first, last = d.index[0], d.index[-1]
    etf = etf_monthly(["SPY", "IWM"], f"{first[0]-1}-12-01",
                      str(pd.Period(f"{last[0]}-{last[1]:02d}", "M").end_time.date() + pd.Timedelta(days=7)))
    etf = etf.reindex(d.index)
    assert etf.notna().all().all(), "missing ETF months"
    model, spy, iwm, rf = d["model"], etf["SPY"], etf["IWM"], etf["BIL"]
    series = {
        "Dual Momentum (100% long)": model,
        "130/30, short SPY": LONG * model - SHORT * spy - SHORT * borrow / 12,
        "130/30, short IWM": LONG * model - SHORT * iwm - SHORT * borrow / 12,
        "SPY": spy,
        "IWM": iwm,
    }
    t = pd.DataFrame({k: stats(v, rf, spy) for k, v in series.items()}).T
    pct = [c for c in t.columns if c not in ("Sharpe", "Beta to SPY")]
    fmt = t.copy().astype(object)
    for c in t.columns:
        f = "{:.2f}" if c not in pct else "{:.1%}" if c in ("Vol / yr", "Up months") else "{:+.1%}"
        fmt[c] = t[c].map(f.format)
    print(f"{len(d)} months, {first[1]}/{first[0]} to {last[1]}/{last[0]}; borrow cost {borrow*1e4:.0f} bp/yr on the short\n")
    print(fmt.to_string())
    yr = pd.DataFrame({k: (1 + v).groupby(level="year").prod() - 1 for k, v in series.items()})
    print("\nCalendar-year returns\n" + yr.map(lambda x: f"{x:+.1%}").to_string())
    out = pd.DataFrame(series)
    out.to_csv(Path(__file__).resolve().parents[1] / "reports/dual_momentum_130_30_monthly.csv", float_format="%.6f")

if __name__ == "__main__":
    main()
