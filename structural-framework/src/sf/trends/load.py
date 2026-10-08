"""§6.1 trend files: one YAML per trend in config/trends/ (and config/trends/historical/ for replays)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..config import CONFIG_DIR

Stage = Literal["early_scarcity", "expansion", "overbuild", "bust", "consolidation"]


class Durability(BaseModel):
    horizon_years: float = Field(gt=0)
    reversibility: int = Field(ge=1, le=5)
    commitment: int = Field(ge=1, le=5)


class Node(BaseModel):
    node: str
    bottleneck: bool = False


class Vehicle(BaseModel):
    type: str
    tickers: list[str] = []


class KillCriterion(BaseModel):
    text: str
    triggered: bool = False
    checked: date | None = None


class HistoryEntry(BaseModel):
    """A dated judgment. Each entry carries the full judgment so any past score can be recomputed."""
    model_config = ConfigDict(extra="allow")
    date: date
    note: str
    durability: Durability | None = None
    capital_cycle_stage: Stage | None = None
    supply_exits_confirmed: bool | None = None
    priced_in: int | None = Field(default=None, ge=1, le=5)
    scores: dict[str, float] = {}


class Trend(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    driver: Literal["demographics", "technology", "policy", "scarcity", "monetary"]
    thesis: str
    linked_premier_assets: list[str] = []
    durability: Durability
    value_chain: list[Node] = []
    capital_cycle_stage: Stage
    supply_exits_confirmed: bool = False      # §6.2: a bust scores 4 instead of 2 once exits are confirmed
    priced_in: int = Field(ge=1, le=5)
    vehicles: list[Vehicle] = []
    kill_criteria: list[str | KillCriterion] = []
    review_date: date | None = None
    history: list[HistoryEntry] = []

    @property
    def kills(self) -> list[KillCriterion]:
        return [k if isinstance(k, KillCriterion) else KillCriterion(text=k) for k in self.kill_criteria]

    @property
    def bottlenecks(self) -> list[str]:
        return [n.node for n in self.value_chain if n.bottleneck]


def load_trends(directory: Path | str = CONFIG_DIR / "trends") -> dict[str, Trend]:
    out = {}
    for p in sorted(Path(directory).glob("*.yaml")):
        with open(p) as f:
            t = Trend(**yaml.safe_load(f))
        if t.id in out:
            raise ValueError(f"duplicate trend id {t.id}")
        out[t.id] = t
    return out
