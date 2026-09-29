"""All screen thresholds in one place. Defaults follow the research spec."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
MANUAL_DIR = ROOT / "data" / "manual"
REPORTS_DIR = ROOT / "reports"


@dataclass(frozen=True)
class ScreenConfig:
    # Universe
    min_mcap: float = 2e9
    max_mcap: float = 50e9
    min_adv: float = 10e6               # average daily dollar volume
    adv_window: int = 63                # trading days
    listed_exchanges: tuple = ("NYSE", "Nasdaq", "CBOE")
    excluded_sic: tuple = (6770, 6798, 6722, 6726, 6799)  # SPACs, REITs, funds/trusts

    # Filter 1: growth
    min_rev_growth: float = 0.20
    accel_quarters: int = 1             # consecutive quarters of acceleration required
    gm_min_slope: float = -0.005        # OLS slope of gross margin, per quarter (-0.5pp)
    gm_min_change: float = -0.01        # latest GM minus GM three quarters earlier (-1pp)
    require_gross_margin: bool = True
    max_staleness_days: int = 200       # latest filed quarter must end within this many days of as-of
    min_volume_share_of_growth: float = 0.5  # unit growth / revenue growth, when units are supplied

    # Filter 2: attention
    attention_max_pct: float = 0.40
    use_turnover_proxy: str = "auto"    # auto | always | never

    # Filter 3: idiosyncratic strength
    reg_window: int = 252
    recent_short: int = 63              # ~3 months
    recent_long: int = 126              # ~6 months
    prior_window: int = 252             # the 12 months before the recent 6 months
    min_obs: int = 200
    min_prior_obs: int = 150
    resid_top_pct: float = 0.30
    max_r2: float = 0.35
    prior_resid_max: float = 0.05       # "flat or negative": cumulative prior residual <= +5%
    require_prior_history: bool = True

    # List-length control
    max_names: int = 30
    tight_rev_growth: float = 0.30
    tight_accel_quarters: int = 2

    def tightened(self) -> "ScreenConfig":
        return replace(self, min_rev_growth=self.tight_rev_growth,
                       accel_quarters=max(self.accel_quarters, self.tight_accel_quarters))
