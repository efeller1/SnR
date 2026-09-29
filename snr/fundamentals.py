"""Point-in-time quarterly fundamentals and Filter 1 (fast, volume-driven growth).

Only facts with ``filed <= as_of`` are used, and for each period we take the
most recent value *known on the screening date* (a later restatement is
invisible until it is filed).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import ScreenConfig
from .sec import COST_TAGS, GROSS_PROFIT_TAGS, REVENUE_TAGS

PERIODIC_FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A", "10-KT", "10-QT"}
Q_DAYS, FY_DAYS, YTD9_DAYS = (80, 100), (350, 380), (260, 290)


def point_in_time(facts: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    return facts[(facts["filed"] <= as_of) & facts["form"].astype(str).isin(PERIODIC_FORMS)]


def _latest_known(d: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return d.sort_values("filed").groupby(keys, as_index=False, observed=True).last()


def _quarterly_one_tag(d: pd.DataFrame) -> pd.DataFrame:
    """Discrete quarters for one tag, deriving Q4 from annual minus 9-month YTD (or minus Q1-Q3)."""
    d = d.dropna(subset=["start"]).copy()
    if d.empty:
        return pd.DataFrame(columns=["end", "val", "filed"])
    d["dur"] = (d["end"] - d["start"]).dt.days
    d = _latest_known(d, ["start", "end"])
    q = d[d["dur"].between(*Q_DAYS)].copy()
    q["dist"] = (q["dur"] - 91).abs()
    q = q.sort_values("dist").drop_duplicates("end")[["end", "val", "filed"]]
    fy = d[d["dur"].between(*FY_DAYS)]
    ytd = d[d["dur"].between(*YTD9_DAYS)]
    derived = []
    tol = pd.Timedelta(days=10)
    for _, a in fy.iterrows():
        if ((q["end"] - a["end"]).abs() <= tol).any():
            continue
        y = ytd[((ytd["start"] - a["start"]).abs() <= tol) & (ytd["end"] < a["end"] - pd.Timedelta(days=60))]
        if not y.empty:
            y = y.sort_values("end").iloc[-1]
            derived.append((a["end"], a["val"] - y["val"], max(a["filed"], y["filed"])))
            continue
        inside = q[(q["end"] > a["start"]) & (q["end"] < a["end"] - pd.Timedelta(days=60))]
        if len(inside) == 3:
            derived.append((a["end"], a["val"] - inside["val"].sum(), max(a["filed"], inside["filed"].max())))
    if derived:
        q = pd.concat([q, pd.DataFrame(derived, columns=["end", "val", "filed"])], ignore_index=True)
    return q.sort_values("end").reset_index(drop=True)


def quarterly(facts_pit: pd.DataFrame, tags: tuple, combine: str = "max") -> pd.DataFrame:
    """Quarterly series across alternative tags. ``combine='max'`` picks the largest
    reported value per quarter (total revenue >= any component line)."""
    parts = []
    for tag in tags:
        t = facts_pit[facts_pit["tag"].astype(str) == tag]
        if not t.empty:
            parts.append(_quarterly_one_tag(t).assign(tag=tag))
    if not parts:
        return pd.DataFrame(columns=["end", "val", "filed"])
    allq = pd.concat(parts, ignore_index=True)
    if combine == "max":
        allq = allq.sort_values("val", ascending=False)
    else:  # first tag in priority order wins
        allq["prio"] = allq["tag"].map({t: i for i, t in enumerate(tags)})
        allq = allq.sort_values("prio")
    out = allq.drop_duplicates("end").sort_values("end")[["end", "val", "filed"]]
    return out.reset_index(drop=True)


def _prev_quarter(ends: pd.Series, end: pd.Timestamp, lo: int, hi: int):
    gap = (end - ends).dt.days
    hit = ends[(gap >= lo) & (gap <= hi)]
    return hit.iloc[-1] if len(hit) else None


def yoy_growth(q: pd.DataFrame) -> pd.Series:
    """YoY growth per quarter end (NaN when the year-ago quarter is missing or <= 0)."""
    s = q.set_index("end")["val"]
    out = {}
    for end, v in s.items():
        prev = _prev_quarter(s.index.to_series(), end, 350, 380)
        out[end] = v / s[prev] - 1 if prev is not None and s[prev] > 0 else np.nan
    return pd.Series(out, dtype=float)


def consecutive_tail(ends: list, n: int) -> list | None:
    """Last n quarter ends if they are consecutive (80-100 days apart), else None."""
    if len(ends) < n:
        return None
    tail = ends[-n:]
    for a, b in zip(tail, tail[1:]):
        if not 80 <= (b - a).days <= 100:
            return None
    return tail


@dataclass
class Fundamentals:
    as_of: pd.Timestamp
    latest_end: pd.Timestamp | None = None
    latest_filed: pd.Timestamp | None = None
    revenue: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    growth: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    gross_margin: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    net_income_ttm: float = np.nan
    op_cash_flow_ttm: float = np.nan
    cash: float = np.nan
    shares: float = np.nan
    shares_yoy: float = np.nan

    @property
    def last_growth(self) -> list[float]:
        """Growth for the latest consecutive quarters, oldest first."""
        return list(self.growth.dropna().values)


def _latest_instant(fp: pd.DataFrame, tag: str, sum_classes: bool = False) -> tuple[float, pd.Timestamp | None]:
    t = fp[fp["tag"].astype(str) == tag]
    if t.empty:
        return np.nan, None
    if sum_classes:  # multi-class issuers report one cover-page fact per class
        t = t.groupby(["accn", "end", "filed"], as_index=False, observed=True)["val"].sum()
    t = t.sort_values(["filed", "end"]).iloc[-1]
    return float(t["val"]), t["end"]


def _instant_before(fp: pd.DataFrame, tag: str, before: pd.Timestamp, sum_classes: bool) -> float:
    t = fp[(fp["tag"].astype(str) == tag) & (fp["end"] <= before)]
    if t.empty:
        return np.nan
    if sum_classes:
        t = t.groupby(["accn", "end", "filed"], as_index=False, observed=True)["val"].sum()
    return float(t.sort_values(["end", "filed"]).iloc[-1]["val"])


def snapshot(facts_cik: pd.DataFrame, as_of: pd.Timestamp, min_growth: float | None = None) -> Fundamentals:
    """Point-in-time fundamentals. With ``min_growth`` set, stops after revenue when the
    latest growth cannot pass (a large speed-up across a full universe)."""
    fp = point_in_time(facts_cik, as_of)
    f = Fundamentals(as_of=as_of)
    rev = quarterly(fp, REVENUE_TAGS, "max")
    if rev.empty:
        return f
    f.latest_end = rev["end"].iloc[-1]
    f.latest_filed = rev["filed"].iloc[-1]
    ends = list(rev["end"])
    growth = yoy_growth(rev)
    tail = ends[-1:]
    for n in range(min(8, len(ends)), 1, -1):  # longest consecutive run, up to 8 quarters
        t = consecutive_tail(ends, n)
        if t:
            tail = t
            break
    f.revenue = rev.set_index("end")["val"].loc[tail]
    f.growth = growth.reindex(tail)
    if min_growth is not None and not f.growth.iloc[-1] > min_growth:
        return f

    gp = quarterly(fp, GROSS_PROFIT_TAGS, "priority").set_index("end")["val"]
    cost = quarterly(fp, COST_TAGS, "priority").set_index("end")["val"]
    revs = rev.set_index("end")["val"]
    gm = {}
    for end in tail[-4:]:
        if revs.get(end, 0) <= 0:
            continue
        if end in gp.index:
            gm[end] = gp[end] / revs[end]
        elif end in cost.index:
            gm[end] = 1 - cost[end] / revs[end]
    f.gross_margin = pd.Series(gm, dtype=float)

    for tag, attr in (("NetIncomeLoss", "net_income_ttm"), ("NetCashProvidedByUsedInOperatingActivities", "op_cash_flow_ttm")):
        s = quarterly(fp, (tag,), "priority")
        last4 = consecutive_tail(list(s["end"]), 4)
        if last4:
            setattr(f, attr, float(s.set_index("end")["val"].loc[last4].sum()))
    f.cash, _ = _latest_instant(fp, "CashAndCashEquivalentsAtCarryingValue")
    f.shares, sh_end = _latest_instant(fp, "EntityCommonStockSharesOutstanding", sum_classes=True)
    tag_used = "EntityCommonStockSharesOutstanding"
    if np.isnan(f.shares):
        f.shares, sh_end = _latest_instant(fp, "CommonStockSharesOutstanding")
        tag_used = "CommonStockSharesOutstanding"
    if sh_end is not None:
        prior = _instant_before(fp, tag_used, sh_end - pd.Timedelta(days=330), tag_used.startswith("Entity"))
        if prior and prior > 0:
            f.shares_yoy = f.shares / prior - 1
    return f


def accel_streak(growth: list[float]) -> int:
    """Number of most-recent consecutive quarters where g_t > mean(g_{t-1}, g_{t-2})."""
    streak = 0
    for i in range(len(growth) - 1, 1, -1):
        g, p1, p2 = growth[i], growth[i - 1], growth[i - 2]
        if any(np.isnan(x) for x in (g, p1, p2)) or not g > (p1 + p2) / 2:
            break
        streak += 1
    return streak


def gm_trend(gm: pd.Series) -> tuple[float, float]:
    """(OLS slope per quarter, latest minus first) over the last four quarters."""
    if len(gm) < 4:
        return np.nan, np.nan
    y = gm.values[-4:]
    slope = np.polyfit(np.arange(4), y, 1)[0]
    return float(slope), float(y[-1] - y[0])


def filter1(f: Fundamentals, cfg: ScreenConfig, unit_growth: float | None = None) -> tuple[bool, str]:
    if f.latest_end is None:
        return False, "no revenue data"
    if (f.as_of - f.latest_end).days > cfg.max_staleness_days:
        return False, "stale fundamentals"
    g = f.last_growth
    if not g or f.growth.isna().iloc[-1]:
        return False, "no YoY growth"
    if g[-1] <= cfg.min_rev_growth:
        return False, f"growth {g[-1]:.0%} <= {cfg.min_rev_growth:.0%}"
    streak = accel_streak(list(f.growth.values))
    if streak < cfg.accel_quarters:
        return False, f"not accelerating ({streak}/{cfg.accel_quarters} qtrs)"
    slope, change = gm_trend(f.gross_margin)
    if np.isnan(slope):
        if cfg.require_gross_margin:
            return False, "gross margin unavailable"
    elif slope < cfg.gm_min_slope or change < cfg.gm_min_change:
        return False, f"gross margin falling ({change:+.1%})"
    if unit_growth is not None and g[-1] > 0 and unit_growth / g[-1] < cfg.min_volume_share_of_growth:
        return False, f"price-driven growth (units {unit_growth:.0%} vs revenue {g[-1]:.0%})"
    return True, "pass"
