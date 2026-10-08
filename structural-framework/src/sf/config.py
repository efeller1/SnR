"""Load and validate everything in config/. No parameters live in code (CLAUDE.md)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = ROOT / "snapshots"
REPORTS_DIR = ROOT / "reports"

COMPONENTS = ("STR", "REG", "CAP", "VAL", "LIQ", "MOM")
Freq = Literal["daily", "weekly", "monthly", "quarterly", "annual"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- scoring.yaml
class Normalization(Strict):
    method: Literal["percentile", "zscore", "threshold", "raw"] = "percentile"
    window_years: float = 10
    min_years: float = 5
    zscore_clip: float = 2.0


class WindowOverride(Strict):
    window_years: float
    min_years: float


class Aggregation(Strict):
    max_missing_share: float = 0.5
    composite_max_missing_weight: float = 0.5


class StanceConfig(Strict):
    overweight: float = 3.6
    underweight: float = 2.4
    hysteresis: float = 0.1
    structural_gate: float = 2.5
    momentum_veto: bool = False
    momentum_veto_level: float = 1.5


class TrendOverlay(Strict):
    enabled: bool = False
    weight_within_str: float = 0.25


class ScoringConfig(Strict):
    calendar: str = "ME"
    publication_lag_months: dict[Freq, int]
    stale_after_days: dict[Freq, int]
    normalization: Normalization
    asset_overrides: dict[str, WindowOverride] = {}
    aggregation: Aggregation = Aggregation()
    component_weights: dict[str, float]
    stance: StanceConfig = StanceConfig()
    trend_overlay: TrendOverlay = TrendOverlay()

    @field_validator("component_weights")
    @classmethod
    def _known_components(cls, v: dict[str, float]) -> dict[str, float]:
        unknown = set(v) - set(COMPONENTS)
        if unknown:
            raise ValueError(f"unknown components {unknown}")
        return v


# --------------------------------------------------------------------------- assets.yaml
class SeriesDef(Strict):
    source: Literal["fred", "prices", "manual", "shiller"]
    id: str
    freq: Freq
    vintage: Literal["latest", "first_release"] = "latest"
    lag_months: int | None = None     # overrides the frequency default
    lag_days: int = 0                 # added on top (e.g. weekly H.4.1 published the next day)


class Step(BaseModel):
    """One transform step. `op` names a function in sf.transforms; other keys are its parameters."""
    model_config = ConfigDict(extra="allow")
    op: str


class Gate(Strict):
    metric: str
    min: float


class MetricDef(Strict):
    id: str
    name: str
    component: str | None = None
    role: Literal["score", "diagnostic"] = "score"
    formula: str
    steps: list[Step] = []
    direction: Literal[1, -1] = 1
    weight: float = 1.0
    normalize: Literal["percentile", "zscore", "threshold", "raw"] | None = None
    thresholds: list[tuple[float, float]] | None = None   # [(value, score), ...] for method=threshold
    gate: Gate | None = None

    @model_validator(mode="after")
    def _component(self) -> "MetricDef":
        if self.role == "score" and self.component not in COMPONENTS:
            raise ValueError(f"{self.id}: scored metrics need a component in {COMPONENTS}")
        if self.normalize == "threshold" and not self.thresholds:
            raise ValueError(f"{self.id}: threshold normalization needs thresholds")
        return self


class AssetDef(Strict):
    name: str
    group: Literal["premier", "satellite", "control"] = "premier"
    price: str | None = None
    thesis: str = ""
    breaks_if: list[str] = []
    component_weights: dict[str, float] = {}
    halving: dict[str, Any] | None = None
    metrics: list[MetricDef]


class AssetsConfig(Strict):
    series: dict[str, SeriesDef]
    assets: dict[str, AssetDef]

    @model_validator(mode="after")
    def _unique_ids(self) -> "AssetsConfig":
        ids = [m.id for a in self.assets.values() for m in a.metrics]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate metric ids: {dupes}")
        for aid, a in self.assets.items():
            if a.price is not None and a.price not in self.series:
                raise ValueError(f"{aid}: price series {a.price!r} not defined")
            for m in a.metrics:
                if m.gate and m.gate.metric not in ids:
                    raise ValueError(f"{m.id}: gate metric {m.gate.metric!r} not defined")
        return self

    def metric(self, metric_id: str) -> tuple[str, MetricDef]:
        for aid, a in self.assets.items():
            for m in a.metrics:
                if m.id == metric_id:
                    return aid, m
        raise KeyError(metric_id)


# --------------------------------------------------------------------------- regimes.yaml
class SignalDef(Strict):
    id: str
    formula: str
    steps: list[Step] = []
    direction: Literal[1, -1] = 1


class GlobalOrderMetric(Strict):
    id: str
    invert: bool = False


class RegimesConfig(Strict):
    growth: dict[str, SignalDef]
    inflation: dict[str, SignalDef]
    real_rates: dict[str, Any]
    fdi: dict[str, Any]
    global_order: dict[str, Any]
    prior_matrix: dict[str, dict[str, float]]
    modifiers: dict[str, dict[str, float]]

    @property
    def real_rate_level(self) -> SignalDef:
        return SignalDef(**self.real_rates["level"])

    @property
    def real_rate_change(self) -> SignalDef:
        return SignalDef(**self.real_rates["change"])

    @property
    def fdi_inputs(self) -> list[SignalDef]:
        return [SignalDef(**d) for d in self.fdi["inputs"]]

    @property
    def global_order_metrics(self) -> list[GlobalOrderMetric]:
        return [GlobalOrderMetric(**d) for d in self.global_order["metrics"]]

    @field_validator("prior_matrix")
    @classmethod
    def _quadrants(cls, v: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        need = {"goldilocks", "reflation", "stagflation", "deflationary_bust"}
        if set(v) != need:
            raise ValueError(f"prior_matrix must have exactly {need}")
        for row in v.values():
            if any(not 1 <= s <= 5 for s in row.values()):
                raise ValueError("prior scores must be in 1-5")
        return v


# --------------------------------------------------------------------------- allocation.yaml
class VolTarget(Strict):
    enabled: bool = False
    annual_vol: float = 0.10
    ewma_span_days: int = 60
    max_leverage: float = 1.0


class AllocationConfig(Strict):
    base_weights: dict[str, float]
    k: float = 0.5
    clip_low: float = 0.5
    clip_high: float = 1.5
    vol_target: VolTarget = VolTarget()
    transaction_cost_bps: float = 10

    @field_validator("base_weights")
    @classmethod
    def _sum_to_one(cls, v: dict[str, float]) -> dict[str, float]:
        if abs(sum(v.values()) - 1) > 1e-6:
            raise ValueError(f"base weights sum to {sum(v.values())}, not 1")
        return v


# --------------------------------------------------------------------------- backtest.yaml
class PassBar(Strict):
    horizon_months: int = 12
    min_ic: float = 0.05
    min_t: float = 2.0


class ControlsTest(Strict):
    min_share_months_below: float = 0.70
    forward_years: int = 5


class BacktestConfig(Strict):
    horizons_months: list[int] = [1, 3, 6, 12]
    pass_bar: PassBar = PassBar()
    holdout_years: float = 5
    oos_fraction: float = 0.33
    walkforward_first_train_years: int = 10
    quintiles: int = 5
    controls: ControlsTest = ControlsTest()
    benchmarks: dict[str, dict[str, float]] = {}
    bond_series: str = "agg"
    cash_series: str = "tbill_3m"
    sensitivity: dict[str, list[float]] = {}


# --------------------------------------------------------------------------- bundle
class Config(BaseModel):
    scoring: ScoringConfig
    assets: AssetsConfig
    regimes: RegimesConfig
    allocation: AllocationConfig
    backtest: BacktestConfig = BacktestConfig()
    raw: dict[str, Any] = Field(default_factory=dict, repr=False)

    def window(self, asset_id: str) -> tuple[float, float]:
        o = self.scoring.asset_overrides.get(asset_id)
        n = self.scoring.normalization
        return (o.window_years, o.min_years) if o else (n.window_years, n.min_years)

    def component_weights(self, asset_id: str) -> dict[str, float]:
        w = dict(self.scoring.component_weights)
        w.update(self.assets.assets[asset_id].component_weights)
        return w

    def lag(self, s: SeriesDef) -> tuple[int, int]:
        months = s.lag_months if s.lag_months is not None else self.scoring.publication_lag_months[s.freq]
        return months, s.lag_days

    @property
    def hash(self) -> str:
        blob = json.dumps(self.raw, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]


def _read(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_config(config_dir: Path | str = CONFIG_DIR) -> Config:
    d = Path(config_dir)
    raw = {name: _read(d / f"{name}.yaml") for name in ("scoring", "assets", "regimes", "allocation", "backtest")}
    cfg = Config(
        scoring=ScoringConfig(**raw["scoring"]),
        assets=AssetsConfig(**raw["assets"]),
        regimes=RegimesConfig(**raw["regimes"]),
        allocation=AllocationConfig(**raw["allocation"]),
        backtest=BacktestConfig(**raw["backtest"]),
        raw=raw,
    )
    missing = set(cfg.allocation.base_weights) - set(cfg.assets.assets)
    if missing:
        raise ValueError(f"allocation names unknown assets {missing}")
    return cfg

