"""Statistical helpers shared by benchmark analyses."""

from __future__ import annotations

import itertools
import math
import random
from collections import defaultdict
from collections.abc import Iterable

import numpy as np


def _stratified_families(
    values: list[float],
    families: list[str],
    strata: list[str],
) -> dict[str, dict[str, list[float]]]:
    if not values or len(values) != len(families) or len(values) != len(strata):
        raise ValueError("values, families, and strata must be non-empty and equal length")
    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    family_strata: dict[str, str] = {}
    for value, family, stratum in zip(values, families, strata, strict=True):
        previous = family_strata.setdefault(family, stratum)
        if previous != stratum:
            raise ValueError(f"family {family!r} appears in more than one stratum")
        grouped[stratum][family].append(float(value))
    return {
        stratum: dict(family_values)
        for stratum, family_values in grouped.items()
    }


def normalized_stratum_weights(
    strata: Iterable[str],
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    present = sorted(set(strata))
    if not present:
        raise ValueError("at least one stratum is required")
    if weights is None:
        return {stratum: 1.0 / len(present) for stratum in present}
    missing = set(present) - set(weights)
    extra = set(weights) - set(present)
    if missing or extra:
        raise ValueError(
            f"stratum weights do not match data; missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    total = sum(float(weights[stratum]) for stratum in present)
    if total <= 0:
        raise ValueError("stratum weights must sum to a positive value")
    normalized = {
        stratum: float(weights[stratum]) / total for stratum in present
    }
    if any(value <= 0 for value in normalized.values()):
        raise ValueError("every stratum weight must be positive")
    return normalized


def stratified_equal_family_mean(
    values: list[float],
    families: list[str],
    strata: list[str],
    *,
    stratum_weights: dict[str, float] | None = None,
) -> float:
    """Fixed stratum weights, equal family weights, then item means."""
    grouped = _stratified_families(values, families, strata)
    weights = normalized_stratum_weights(grouped, stratum_weights)
    estimate = 0.0
    for stratum, family_values in grouped.items():
        family_means = [
            sum(items) / len(items) for items in family_values.values()
        ]
        estimate += weights[stratum] * sum(family_means) / len(family_means)
    return estimate


def stratified_clustered_bootstrap_mean(
    values: list[float],
    families: list[str],
    strata: list[str],
    *,
    stratum_weights: dict[str, float] | None = None,
    n_boot: int = 10_000,
    seed: int = 20260825,
) -> tuple[float, tuple[float, float], list[float]]:
    """Resample families within strata, then items within selected families."""
    grouped = _stratified_families(values, families, strata)
    weights = normalized_stratum_weights(grouped, stratum_weights)
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(n_boot):
        sample = 0.0
        for stratum in sorted(grouped):
            family_values = grouped[stratum]
            family_ids = sorted(family_values)
            selected_means: list[float] = []
            for family in rng.choices(family_ids, k=len(family_ids)):
                items = family_values[family]
                selected = rng.choices(items, k=len(items))
                selected_means.append(sum(selected) / len(selected))
            sample += weights[stratum] * sum(selected_means) / len(selected_means)
        samples.append(sample)
    estimate = stratified_equal_family_mean(
        values,
        families,
        strata,
        stratum_weights=weights,
    )
    return estimate, percentile_interval(samples), samples


def stratified_cluster_sign_flip_p(
    values: list[float],
    families: list[str],
    strata: list[str],
    *,
    stratum_weights: dict[str, float] | None = None,
    seed: int = 20260825,
    simulations: int = 200_000,
) -> float:
    """Two-sided family sign-flip test for a stratified weighted mean."""
    grouped = _stratified_families(values, families, strata)
    weights = normalized_stratum_weights(grouped, stratum_weights)
    contributions: list[float] = []
    for stratum in sorted(grouped):
        family_values = grouped[stratum]
        family_count = len(family_values)
        for family in sorted(family_values):
            items = family_values[family]
            family_mean = sum(items) / len(items)
            contributions.append(weights[stratum] * family_mean / family_count)
    observed = abs(sum(contributions))
    if len(contributions) <= 18:
        assignments = itertools.product((-1.0, 1.0), repeat=len(contributions))
        extreme = 0
        total = 0
        for signs in assignments:
            statistic = abs(sum(
                sign * value
                for sign, value in zip(signs, contributions, strict=True)
            ))
            extreme += statistic >= observed - 1e-15
            total += 1
        return extreme / total
    rng = random.Random(seed)
    extreme = 1
    for _ in range(simulations):
        statistic = abs(sum(
            rng.choice((-1.0, 1.0)) * value for value in contributions
        ))
        extreme += statistic >= observed - 1e-15
    return extreme / (simulations + 1)


def stratified_family_standard_error(
    values: list[float],
    families: list[str],
    strata: list[str],
    *,
    stratum_weights: dict[str, float] | None = None,
) -> float:
    """Standard error from between-family variation within fixed strata."""
    grouped = _stratified_families(values, families, strata)
    weights = normalized_stratum_weights(grouped, stratum_weights)
    variance = 0.0
    for stratum, family_values in grouped.items():
        means = [sum(items) / len(items) for items in family_values.values()]
        if len(means) < 2:
            raise ValueError(
                f"stratum {stratum!r} needs at least two families for a "
                "cluster standard error"
            )
        center = sum(means) / len(means)
        sample_variance = sum((value - center) ** 2 for value in means) / (
            len(means) - 1
        )
        variance += weights[stratum] ** 2 * sample_variance / len(means)
    return math.sqrt(max(0.0, variance))


def stratified_wild_cluster_t_interval(
    values: list[float],
    families: list[str],
    strata: list[str],
    *,
    stratum_weights: dict[str, float] | None = None,
    simulations: int = 10_000,
    seed: int = 20260825,
    level: float = 0.95,
) -> tuple[float, tuple[float, float], dict[str, float]]:
    """Rademacher wild cluster bootstrap-t interval over source frames."""
    grouped = _stratified_families(values, families, strata)
    weights = normalized_stratum_weights(grouped, stratum_weights)
    family_means: dict[str, dict[str, float]] = {}
    stratum_means: dict[str, float] = {}
    for stratum, family_values in grouped.items():
        means = {
            family: sum(items) / len(items)
            for family, items in family_values.items()
        }
        if len(means) < 2:
            raise ValueError(
                f"stratum {stratum!r} needs at least two families for "
                "wild cluster bootstrap-t"
            )
        family_means[stratum] = means
        stratum_means[stratum] = sum(means.values()) / len(means)
    estimate = sum(
        weights[stratum] * stratum_means[stratum]
        for stratum in sorted(grouped)
    )
    observed_se = stratified_family_standard_error(
        values,
        families,
        strata,
        stratum_weights=weights,
    )
    if observed_se <= 1e-12:
        raise ValueError("wild cluster bootstrap-t observed standard error is zero")
    rng = random.Random(seed)
    t_values: list[float] = []
    invalid = 0
    for _ in range(simulations):
        pseudo_values: list[float] = []
        pseudo_families: list[str] = []
        pseudo_strata: list[str] = []
        for stratum in sorted(family_means):
            center = stratum_means[stratum]
            for family in sorted(family_means[stratum]):
                sign = rng.choice((-1.0, 1.0))
                pseudo = center + sign * (family_means[stratum][family] - center)
                pseudo_values.append(pseudo)
                pseudo_families.append(family)
                pseudo_strata.append(stratum)
        pseudo_estimate = stratified_equal_family_mean(
            pseudo_values,
            pseudo_families,
            pseudo_strata,
            stratum_weights=weights,
        )
        pseudo_se = stratified_family_standard_error(
            pseudo_values,
            pseudo_families,
            pseudo_strata,
            stratum_weights=weights,
        )
        if pseudo_se <= 1e-12 or not math.isfinite(pseudo_se):
            invalid += 1
            continue
        t_values.append((pseudo_estimate - estimate) / pseudo_se)
    if len(t_values) < 0.99 * simulations:
        raise ValueError(
            f"wild cluster bootstrap-t had {invalid}/{simulations} invalid replicates"
        )
    tail = (1.0 - level) / 2.0
    low_t, high_t = np.quantile(t_values, [tail, 1.0 - tail])
    interval = (
        float(estimate - high_t * observed_se),
        float(estimate - low_t * observed_se),
    )
    diagnostics = {
        "observed_cluster_se": observed_se,
        "valid_replicates": float(len(t_values)),
        "invalid_replicates": float(invalid),
    }
    return estimate, interval, diagnostics


def kish_effective_clusters(families: Iterable[str]) -> float:
    counts: dict[str, int] = defaultdict(int)
    for family in families:
        counts[family] += 1
    if not counts:
        raise ValueError("at least one family is required")
    total = sum(counts.values())
    return total**2 / sum(count * count for count in counts.values())


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Return Holm-adjusted p-values with monotonic step-down correction."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, p_value) in enumerate(ordered):
        candidate = min(1.0, (count - rank) * p_value)
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


def percentile_interval(
    samples: Iterable[float],
    *,
    level: float = 0.95,
) -> tuple[float, float]:
    values = np.asarray(list(samples), dtype=float)
    if values.size == 0:
        raise ValueError("cannot calculate an interval from no samples")
    tail = (1.0 - level) / 2.0
    low, high = np.quantile(values, [tail, 1.0 - tail])
    return float(low), float(high)


def bootstrap_mean(
    values: list[float],
    *,
    n_boot: int = 10_000,
    seed: int = 20260825,
) -> tuple[float, tuple[float, float], list[float]]:
    """Bootstrap a mean by resampling independent items."""
    if not values:
        raise ValueError("values must be non-empty")
    numeric = [float(value) for value in values]
    rng = random.Random(seed)
    samples = [
        sum(rng.choices(numeric, k=len(numeric))) / len(numeric)
        for _ in range(n_boot)
    ]
    estimate = sum(numeric) / len(numeric)
    return estimate, percentile_interval(samples), samples


def clustered_bootstrap_mean(
    values: list[float],
    families: list[str],
    *,
    n_boot: int = 10_000,
    seed: int = 20260825,
) -> tuple[float, tuple[float, float], list[float]]:
    """Hierarchical bootstrap: families, then items within family."""
    if len(values) != len(families) or not values:
        raise ValueError("values and families must be non-empty and equal length")
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, family in zip(values, families, strict=True):
        grouped[family].append(float(value))
    family_ids = sorted(grouped)
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(n_boot):
        selected_values: list[float] = []
        for family in rng.choices(family_ids, k=len(family_ids)):
            items = grouped[family]
            selected_values.extend(rng.choices(items, k=len(items)))
        samples.append(sum(selected_values) / len(selected_values))
    estimate = sum(values) / len(values)
    return estimate, percentile_interval(samples), samples


def clustered_sign_flip_p(
    values: list[float],
    families: list[str],
    *,
    seed: int = 20260825,
    simulations: int = 200_000,
) -> float:
    """Two-sided cluster sign-flip test for a zero paired mean."""
    if len(values) != len(families) or not values:
        raise ValueError("values and families must be non-empty and equal length")
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, family in zip(values, families, strict=True):
        grouped[family].append(float(value))
    totals = [sum(grouped[family]) for family in sorted(grouped)]
    denominator = len(values)
    observed = abs(sum(totals) / denominator)

    if len(totals) <= 18:
        assignments = itertools.product((-1.0, 1.0), repeat=len(totals))
        extreme = 0
        total = 0
        for signs in assignments:
            statistic = abs(sum(sign * value for sign, value in zip(signs, totals, strict=True)) / denominator)
            extreme += statistic >= observed - 1e-15
            total += 1
        return extreme / total

    rng = random.Random(seed)
    extreme = 1
    for _ in range(simulations):
        statistic = abs(
            sum(rng.choice((-1.0, 1.0)) * value for value in totals)
            / denominator
        )
        extreme += statistic >= observed - 1e-15
    return extreme / (simulations + 1)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    half = z * math.sqrt(
        p * (1 - p) / n + z**2 / (4 * n**2)
    ) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def mcnemar_exact_p(b: int, c: int) -> float:
    discordant = b + c
    if discordant == 0:
        return 1.0
    smaller = min(b, c)
    tail = sum(
        math.comb(discordant, value)
        for value in range(smaller + 1)
    ) / 2.0**discordant
    return min(1.0, 2 * tail)


def tag_value(tags: list[str], prefix: str) -> str | None:
    return next(
        (tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)),
        None,
    )
