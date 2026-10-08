"""§13 asset admission test: config/universe/<asset_id>.yaml files, tiering, distinctiveness."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from .config import CONFIG_DIR

Result = Literal["pass", "fail", "pending"]
Tier = Literal["candidate", "watchlist", "satellite", "premier"]


class HistoryTest(BaseModel):
    years_of_data: float
    countries: list[str] = []
    result: Result


class VehicleTest(BaseModel):
    vehicles: list[str] = []
    result: Result


class MaxCorr(BaseModel):
    asset: str
    value: float


class Tests(BaseModel):
    A1: Result
    A2: Result
    A3: HistoryTest | Result
    A4: VehicleTest | Result
    max_corr_vs_premier: MaxCorr | None = None


class Admission(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    tier: Tier = "candidate"
    digital: bool = False
    mechanism: str
    breaks_if: list[str]
    tests: Tests
    decision: Tier | None = None
    decision_date: date | None = None
    notes: str = ""


def _result(t) -> str:
    return t if isinstance(t, str) else t.result


def tier_from_tests(a: Admission, max_corr: float = 0.8, min_years: float = 30, min_years_digital: float = 10) -> Tier:
    """§13.1 tiers. A3 is re-checked against the year threshold when years_of_data is given."""
    a1, a2, a4 = (_result(a.tests.A1) == "pass", _result(a.tests.A2) == "pass", _result(a.tests.A4) == "pass")
    a3 = _result(a.tests.A3) == "pass"
    if isinstance(a.tests.A3, HistoryTest):
        a3 = a3 and a.tests.A3.years_of_data >= (min_years_digital if a.digital else min_years)
    distinct = a.tests.max_corr_vs_premier is None or a.tests.max_corr_vs_premier.value < max_corr
    if a1 and a2 and a3 and a4 and distinct:
        return "premier"
    if a1 and a2 and a4:
        return "satellite"
    if a1:
        return "watchlist"
    return "candidate"


def max_rolling_corr(candidate: pd.Series, premier: pd.DataFrame, years: int = 10,
                     periods_per_year: int = 12) -> tuple[str | None, float]:
    """Highest rolling correlation of the candidate's returns with any premier asset's returns."""
    n = years * periods_per_year
    best = (None, -np.inf)
    for col in premier.columns:
        c = candidate.rolling(n, min_periods=n).corr(premier[col]).max()
        if pd.notna(c) and c > best[1]:
            best = (col, float(c))
    return best if best[0] else (None, np.nan)


def load_admissions(directory: Path = CONFIG_DIR / "universe") -> dict[str, Admission]:
    out = {}
    for p in sorted(Path(directory).glob("*.yaml")):
        with open(p) as f:
            a = Admission(**yaml.safe_load(f))
        out[a.id] = a
    return out
