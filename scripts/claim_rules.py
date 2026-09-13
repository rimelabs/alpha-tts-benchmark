"""Directional claim rules used by the benchmark analyses."""

from __future__ import annotations

from typing import Any


DIRECTIONAL_ALPHA = 0.05


def assess_directional_claim(
    effect: float,
    interval: list[float] | tuple[float, float],
    holm_p: float,
) -> dict[str, Any]:
    """Apply the interval-plus-Holm directional claim gate."""
    if len(interval) != 2:
        raise ValueError("a claim interval must have two endpoints")
    low, high = (float(interval[0]), float(interval[1]))
    effect = float(effect)
    holm_p = float(holm_p)
    if low > high:
        raise ValueError("claim interval endpoints are reversed")
    if not low <= effect <= high:
        raise ValueError("effect must fall inside its claim interval")
    if not 0.0 <= holm_p <= 1.0:
        raise ValueError("Holm p-value must be between zero and one")

    if low > 0.0 and holm_p <= DIRECTIONAL_ALPHA:
        status = "rime_direction_supported"
        direction = "rime"
        bound = low
    elif high < 0.0 and holm_p <= DIRECTIONAL_ALPHA:
        status = "competitor_direction_supported"
        direction = "competitor"
        bound = high
    else:
        status = "inconclusive"
        direction = None
        bound = 0.0 if low <= 0.0 <= high else min((low, high), key=abs)

    return {
        "status": status,
        "supported_direction": direction,
        "directional_claim_allowed": direction is not None,
        "magnitude_bound_nearest_zero": bound,
        "magnitude_language_allowed": direction is not None,
        "equivalence_or_parity_claim_allowed": False,
        "causal_or_mechanistic_claim_allowed": False,
    }
