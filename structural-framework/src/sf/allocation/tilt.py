"""§3.5 model allocation: tilt strategic base weights by composite score."""
from __future__ import annotations

import math

from ..config import AllocationConfig


def tilt_weights(composites: dict[str, float], cfg: AllocationConfig) -> dict[str, float]:
    """w_i = b_i (1 + k (C_i - 3) / 2), clipped to [lo b_i, hi b_i], then renormalized.

    A missing composite means no tilt. Renormalizing can push a weight back outside its clip
    band, so clip-and-renormalize repeats until it settles.
    """
    b = cfg.base_weights
    w = {}
    for a, bi in b.items():
        c = composites.get(a)
        c = 3.0 if c is None or (isinstance(c, float) and math.isnan(c)) else c
        w[a] = bi * (1 + cfg.k * (c - 3) / 2)
    for _ in range(50):
        w = {a: min(max(v, cfg.clip_low * b[a]), cfg.clip_high * b[a]) for a, v in w.items()}
        total = sum(w.values())
        w = {a: v / total for a, v in w.items()}
        if all(cfg.clip_low * b[a] - 1e-9 <= v <= cfg.clip_high * b[a] + 1e-9 for a, v in w.items()):
            break
    return w
