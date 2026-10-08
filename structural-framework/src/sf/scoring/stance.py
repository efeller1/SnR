"""§3.4 stance rules: thresholds with hysteresis, then the structural gate and optional momentum veto."""
from __future__ import annotations

import math

import pandas as pd

from ..config import StanceConfig

OW, N, UW = "Overweight", "Neutral", "Underweight"


def raw_stance(composite: float, prev: str | None, c: StanceConfig) -> str | None:
    """Threshold stance with hysteresis.

    With no previous stance the plain thresholds apply. After that the composite has to cross a
    threshold by more than the hysteresis band to change stance: Neutral -> Overweight needs
    composite > 3.6 + 0.1, Overweight -> Neutral needs composite < 3.6 - 0.1 (same for Underweight).
    """
    if composite is None or math.isnan(composite):
        return prev
    h = c.hysteresis
    if prev is None:
        return OW if composite >= c.overweight else UW if composite <= c.underweight else N
    if prev == OW and composite >= c.overweight - h:
        return OW
    if prev == UW and composite <= c.underweight + h:
        return UW
    if composite > c.overweight + h:
        return OW
    if composite < c.underweight - h:
        return UW
    return N


def apply_caps(stance: str | None, str_score: float, mom_score: float, c: StanceConfig) -> tuple[str | None, list[str]]:
    """Cap Overweight at Neutral when STR is weak or (optionally) MOM vetoes. Returns (stance, reasons)."""
    reasons = []
    if stance == OW and str_score is not None and not math.isnan(str_score) and str_score < c.structural_gate:
        reasons.append(f"structural gate: STR {str_score:.2f} < {c.structural_gate}")
    if (stance == OW and c.momentum_veto and mom_score is not None and not math.isnan(mom_score)
            and mom_score <= c.momentum_veto_level):
        reasons.append(f"momentum veto: MOM {mom_score:.2f} <= {c.momentum_veto_level}")
    return (N if reasons else stance), reasons


def stance_history(composite: pd.Series, str_score: pd.Series, mom_score: pd.Series,
                   c: StanceConfig, initial: str | None = None) -> pd.DataFrame:
    """Walk the composite through time. The hysteresis state tracks the uncapped stance, so a gate
    lifting doesn't require the composite to re-cross a threshold."""
    rows, prev = [], initial
    for t in composite.index:
        prev = raw_stance(composite[t], prev, c)
        final, why = apply_caps(prev, str_score.get(t, float("nan")), mom_score.get(t, float("nan")), c)
        rows.append({"date": t, "raw": prev, "stance": final, "capped_by": "; ".join(why)})
    return pd.DataFrame(rows).set_index("date")
