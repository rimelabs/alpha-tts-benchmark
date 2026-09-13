"""Calibrate AlphaBench's percentile interval on its real design.

The simulation preserves the source-frame sizes and fixed subcategory
weights. It generates paired binary differences with a known frame ICC,
checks percentile interval coverage, and checks the family sign-flip test
under symmetric null scenarios. It also measures coverage for wild cluster
bootstrap-t.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from analyze_fidelity import ALPHABENCH_SUBCATEGORY_WEIGHTS

ERROR_RATE_PAIRS = (
    (0.02, 0.02),
    (0.05, 0.05),
    (0.10, 0.10),
    (0.20, 0.20),
    (0.05, 0.08),
    (0.10, 0.15),
)
RHO_GRID = (0.0, 0.05, 0.10, 0.20, 0.30)
COVERAGE_FLOOR = 0.935
TYPE_I_CEILING = 0.055


def read_design(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows.sort(key=lambda row: row["id"])
    if len(rows) != 580 or len({row["family_id"] for row in rows}) < 80:
        raise ValueError(
            "AlphaBench calibration requires the 580-item design "
            "with at least 80 source frames"
        )
    return rows


def design_matrices(
    rows: list[dict[str, Any]],
    *,
    n_boot: int,
    n_signs: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    grouped: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for index, row in enumerate(rows):
        grouped[row["subcategory"]][row["family_id"]].append(index)
    if set(grouped) != set(ALPHABENCH_SUBCATEGORY_WEIGHTS):
        raise ValueError("AlphaBench subcategories do not match weights")

    item_weights = np.zeros(len(rows), dtype=float)
    family_ids: list[str] = []
    family_strata: list[str] = []
    family_item_weights: list[np.ndarray] = []
    for subcategory in sorted(grouped):
        families = grouped[subcategory]
        subcategory_weight = ALPHABENCH_SUBCATEGORY_WEIGHTS[subcategory]
        for family in sorted(families):
            indices = families[family]
            weight = subcategory_weight / len(families) / len(indices)
            item_weights[indices] = weight
            contribution = np.zeros(len(rows), dtype=float)
            contribution[indices] = weight
            family_item_weights.append(contribution)
            family_ids.append(family)
            family_strata.append(subcategory)

    rng = np.random.default_rng(seed)
    bootstrap_weights = np.zeros((n_boot, len(rows)), dtype=np.float32)
    for replicate in range(n_boot):
        for subcategory in sorted(grouped):
            families = sorted(grouped[subcategory])
            subcategory_weight = ALPHABENCH_SUBCATEGORY_WEIGHTS[subcategory]
            selected = rng.choice(families, size=len(families), replace=True)
            for family in selected:
                indices = grouped[subcategory][family]
                sampled = rng.choice(indices, size=len(indices), replace=True)
                increment = subcategory_weight / len(families) / len(indices)
                np.add.at(bootstrap_weights[replicate], sampled, increment)

    family_matrix = np.stack(family_item_weights, axis=1)
    signs = rng.choice(
        np.array([-1.0, 1.0], dtype=np.float32),
        size=(n_signs, len(family_ids)),
    )
    return item_weights, bootstrap_weights, family_matrix, signs, family_strata


def family_standard_errors(
    family_means: np.ndarray,
    family_strata: list[str],
) -> np.ndarray:
    variance = np.zeros(family_means.shape[:-1], dtype=float)
    for stratum in sorted(set(family_strata)):
        indices = [
            index for index, value in enumerate(family_strata) if value == stratum
        ]
        weight = ALPHABENCH_SUBCATEGORY_WEIGHTS[stratum]
        variance += weight**2 * np.var(
            family_means[..., indices],
            axis=-1,
            ddof=1,
        ) / len(indices)
    return np.sqrt(np.maximum(variance, 0.0))


def wild_cluster_t_coverage(
    differences: np.ndarray,
    *,
    truth: float,
    family_matrix: np.ndarray,
    family_strata: list[str],
    signs: np.ndarray,
    batch_size: int = 50,
) -> tuple[float, float]:
    family_weights = np.sum(family_matrix, axis=0)
    mean_matrix = family_matrix / family_weights[None, :]
    family_means = differences @ mean_matrix
    estimates = family_means @ family_weights
    observed_se = family_standard_errors(family_means, family_strata)
    residuals = family_means.copy()
    for stratum in sorted(set(family_strata)):
        indices = [
            index for index, value in enumerate(family_strata) if value == stratum
        ]
        residuals[:, indices] -= np.mean(
            family_means[:, indices],
            axis=1,
            keepdims=True,
        )

    covered = 0
    valid = 0
    invalid = 0
    for start in range(0, differences.shape[0], batch_size):
        stop = min(start + batch_size, differences.shape[0])
        batch_residuals = residuals[start:stop]
        pseudo_residuals = batch_residuals[:, None, :] * signs[None, :, :]
        numerators = np.sum(
            pseudo_residuals * family_weights[None, None, :],
            axis=2,
        )
        pseudo_se = family_standard_errors(pseudo_residuals, family_strata)
        usable = pseudo_se > 1e-12
        t_values = np.divide(
            numerators,
            pseudo_se,
            out=np.full_like(numerators, np.nan),
            where=usable,
        )
        for local, row in enumerate(t_values):
            finite = row[np.isfinite(row)]
            if finite.size < 0.99 * signs.shape[0] or observed_se[start + local] <= 1e-12:
                invalid += 1
                continue
            low_t, high_t = np.quantile(finite, [0.025, 0.975])
            low = estimates[start + local] - high_t * observed_se[start + local]
            high = estimates[start + local] - low_t * observed_se[start + local]
            covered += low <= truth <= high
            valid += 1
    coverage = covered / valid if valid else 0.0
    return coverage, invalid / differences.shape[0]


def categorical_draws(
    rng: np.random.Generator,
    probabilities: tuple[float, float, float],
    size: tuple[int, ...],
) -> np.ndarray:
    negative, zero, _ = probabilities
    uniforms = rng.random(size)
    return np.where(uniforms < negative, -1.0, np.where(uniforms < negative + zero, 0.0, 1.0))


def simulate_differences(
    rows: list[dict[str, Any]],
    *,
    simulations: int,
    rime_error: float,
    competitor_error: float,
    rho: float,
    seed: int,
) -> np.ndarray:
    family_ids = sorted({row["family_id"] for row in rows})
    family_index = {family: index for index, family in enumerate(family_ids)}
    rng = np.random.default_rng(seed)
    p_negative = rime_error * (1.0 - competitor_error)
    p_positive = competitor_error * (1.0 - rime_error)
    probabilities = (p_negative, 1.0 - p_negative - p_positive, p_positive)
    independent = categorical_draws(
        rng,
        probabilities,
        (simulations, len(rows)),
    )
    shared = categorical_draws(
        rng,
        probabilities,
        (simulations, len(family_ids)),
    )
    family_shared = rng.random((simulations, len(family_ids))) < rho
    result = independent
    for item, row in enumerate(rows):
        family = family_index[row["family_id"]]
        mask = family_shared[:, family]
        result[mask, item] = shared[mask, family]
    return result


def run_scenario(
    differences: np.ndarray,
    *,
    truth: float,
    item_weights: np.ndarray,
    bootstrap_weights: np.ndarray,
    family_matrix: np.ndarray,
    signs: np.ndarray,
    family_strata: list[str],
) -> dict[str, float]:
    estimates = differences @ item_weights
    bootstrap = differences @ bootstrap_weights.T
    low = np.quantile(bootstrap, 0.025, axis=1)
    high = np.quantile(bootstrap, 0.975, axis=1)
    coverage = float(np.mean((low <= truth) & (truth <= high)))
    nearest_bound_bias = float(
        np.mean(low - truth) if truth > 0 else np.mean(np.minimum(abs(low), abs(high)))
    )

    family_contributions = differences @ family_matrix
    observed = np.abs(np.sum(family_contributions, axis=1))
    flipped = np.abs(family_contributions @ signs.T)
    p_values = (1.0 + np.sum(flipped >= observed[:, None] - 1e-15, axis=1)) / (
        signs.shape[0] + 1.0
    )
    type_i = float(np.mean(p_values <= 0.05)) if abs(truth) < 1e-12 else None
    wild_coverage, wild_invalid = wild_cluster_t_coverage(
        differences,
        truth=truth,
        family_matrix=family_matrix,
        family_strata=family_strata,
        signs=signs[: min(999, signs.shape[0])],
    )
    return {
        "coverage": coverage,
        "mean_estimate": float(np.mean(estimates)),
        "estimate_bias": float(np.mean(estimates) - truth),
        "mean_interval_width": float(np.mean(high - low)),
        "near_zero_bound_summary": nearest_bound_bias,
        "sign_flip_type_i": type_i,
        "wild_cluster_t_coverage": wild_coverage,
        "wild_cluster_t_invalid_fraction": wild_invalid,
    }


def simulate(
    rows: list[dict[str, Any]],
    *,
    simulations: int,
    n_boot: int,
    n_signs: int,
    seed: int,
) -> dict[str, Any]:
    item_weights, bootstrap_weights, family_matrix, signs, family_strata = design_matrices(
        rows,
        n_boot=n_boot,
        n_signs=n_signs,
        seed=seed,
    )
    scenarios = []
    scenario_number = 0
    for rho in RHO_GRID:
        for rime_error, competitor_error in ERROR_RATE_PAIRS:
            truth = competitor_error - rime_error
            differences = simulate_differences(
                rows,
                simulations=simulations,
                rime_error=rime_error,
                competitor_error=competitor_error,
                rho=rho,
                seed=seed + 1000 + scenario_number,
            )
            metrics = run_scenario(
                differences,
                truth=truth,
                item_weights=item_weights,
                bootstrap_weights=bootstrap_weights,
                family_matrix=family_matrix,
                signs=signs,
                family_strata=family_strata,
            )
            scenarios.append({
                "rime_error_rate": rime_error,
                "competitor_error_rate": competitor_error,
                "true_paired_difference": truth,
                "rho": rho,
                **metrics,
            })
            scenario_number += 1
    coverage_failures = [
        scenario for scenario in scenarios
        if scenario["coverage"] < COVERAGE_FLOOR
    ]
    type_i_failures = [
        scenario for scenario in scenarios
        if scenario["sign_flip_type_i"] is not None
        and scenario["sign_flip_type_i"] > TYPE_I_CEILING
    ]
    wild_failures = [
        scenario for scenario in scenarios
        if scenario["wild_cluster_t_coverage"] < COVERAGE_FLOOR
        or scenario["wild_cluster_t_invalid_fraction"] > 0.01
    ]
    return {
        "design": {
            "scripts": len(rows),
            "frames": len({row["family_id"] for row in rows}),
            "simulations_per_scenario": simulations,
            "bootstrap_replicates": n_boot,
            "sign_flip_assignments": n_signs,
            "rho_grid": list(RHO_GRID),
            "error_rate_pairs": [list(pair) for pair in ERROR_RATE_PAIRS],
            "seed": seed,
        },
        "diagnostics": {
            "minimum_scenario_coverage": COVERAGE_FLOOR,
            "maximum_null_type_i": TYPE_I_CEILING,
            "coverage_failures": len(coverage_failures),
            "type_i_failures": len(type_i_failures),
            "wild_cluster_t_failures": len(wild_failures),
        },
        "scenarios": scenarios,
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# AlphaBench interval calibration",
        "",
        "Simulated coverage and type I error for two interval methods.",
        "",
        "| Rime error | competitor error | rho | percentile coverage | wild-t coverage | width | sign-flip type I |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["scenarios"]:
        type_i = row["sign_flip_type_i"]
        lines.append(
            f"| {row['rime_error_rate']:.0%} | {row['competitor_error_rate']:.0%} "
            f"| {row['rho']:.2f} | {row['coverage']:.1%} "
            f"| {row['wild_cluster_t_coverage']:.1%} "
            f"| {row['mean_interval_width']:.3f} "
            f"| {'n/a' if type_i is None else f'{type_i:.1%}'} |"
        )
    lines.extend([
        "",
        f"Coverage failures: {result['diagnostics']['coverage_failures']}.",
        f"Type I failures: {result['diagnostics']['type_i_failures']}.",
        f"Wild cluster-t failures: {result['diagnostics']['wild_cluster_t_failures']}.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", type=Path, default=Path("data/alphabench.jsonl"))
    parser.add_argument("--simulations", type=int, default=10_000)
    parser.add_argument("--n-boot", type=int, default=2_000)
    parser.add_argument("--n-signs", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--outdir", type=Path, default=Path("docs/calibration"))
    args = parser.parse_args()
    try:
        result = simulate(
            read_design(args.corpus),
            simulations=args.simulations,
            n_boot=args.n_boot,
            n_signs=args.n_signs,
            seed=args.seed,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "alphabench_calibration.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = markdown_report(result)
    (args.outdir / "alphabench_calibration.md").write_text(
        report,
        encoding="utf-8",
    )
    print(report)


if __name__ == "__main__":
    main()
