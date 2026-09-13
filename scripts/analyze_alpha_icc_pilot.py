"""Estimate source-frame ICC in AlphaBench pilot data."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from analyze_fidelity import (
    load_corpus_families,
    load_corpus_subcategories,
    load_eval_ids,
    parse_payload,
)
from stats_utils import percentile_interval


def one_way_icc(values: list[float], families: list[str]) -> float:
    """Unequal-cluster one-way random-effects ICC by ANOVA moments."""
    if not values or len(values) != len(families):
        raise ValueError("values and families must be non-empty and equal length")
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, family in zip(values, families, strict=True):
        grouped[family].append(float(value))
    n = len(values)
    g = len(grouped)
    if g < 2 or n <= g:
        raise ValueError("ICC requires at least two families and one repeated family")
    grand = sum(values) / n
    ss_between = sum(
        len(items) * (sum(items) / len(items) - grand) ** 2
        for items in grouped.values()
    )
    ss_within = sum(
        sum((value - sum(items) / len(items)) ** 2 for value in items)
        for items in grouped.values()
    )
    ms_between = ss_between / (g - 1)
    ms_within = ss_within / (n - g)
    n0 = (n - sum(len(items) ** 2 for items in grouped.values()) / n) / (g - 1)
    denominator = ms_between + (n0 - 1) * ms_within
    if denominator <= 0:
        return 0.0
    return (ms_between - ms_within) / denominator


def bootstrap_icc(
    values: list[float],
    families: list[str],
    *,
    n_boot: int,
    seed: int,
) -> tuple[float, tuple[float, float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, family in zip(values, families, strict=True):
        grouped[family].append(float(value))
    family_ids = sorted(grouped)
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(n_boot):
        sample_values: list[float] = []
        sample_families: list[str] = []
        for draw, family in enumerate(rng.choices(family_ids, k=len(family_ids))):
            items = grouped[family]
            sample_values.extend(items)
            sample_families.extend([f"draw:{draw}"] * len(items))
        estimate = one_way_icc(sample_values, sample_families)
        if math.isfinite(estimate):
            samples.append(estimate)
    if len(samples) < 0.95 * n_boot:
        raise ValueError("too many invalid ICC bootstrap replicates")
    return one_way_icc(values, families), percentile_interval(samples)


def analyze(
    rows: list[dict[str, Any]],
    *,
    baseline: str,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    by_model: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_model[row["model_tag"]][row["item_id"]] = row
    if baseline not in by_model:
        raise ValueError(f"baseline {baseline!r} not found")
    baseline_rows = by_model[baseline]
    results: dict[str, Any] = {}
    for offset, competitor in enumerate(
        model for model in sorted(by_model) if model != baseline
    ):
        common = sorted(set(baseline_rows) & set(by_model[competitor]))
        differences = [
            float(by_model[competitor][item]["majority_error"])
            - float(baseline_rows[item]["majority_error"])
            for item in common
        ]
        families = [baseline_rows[item]["family_id"] for item in common]
        estimate, interval = bootstrap_icc(
            differences,
            families,
            n_boot=n_boot,
            seed=seed + offset,
        )
        results[competitor] = {
            "scripts": len(common),
            "frames": len(set(families)),
            "rho_hat": estimate,
            "rho_ci_95": list(interval),
        }
    return {"baseline": baseline, "competitors": results}


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# AlphaBench ICC pilot diagnostic",
        "",
        "Source-frame dependence in the supplied pilot observations.",
        "",
        "| comparison | scripts | frames | rho | 95% interval |",
        "|---|---:|---:|---:|---:|",
    ]
    for competitor, row in sorted(result["competitors"].items()):
        low, high = row["rho_ci_95"]
        lines.append(
            f"| {competitor} | {row['scripts']} | {row['frames']} "
            f"| {row['rho_hat']:.3f} | [{low:.3f}, {high:.3f}] |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stats-json", nargs="*", type=Path, default=[])
    parser.add_argument("--eval-ids", nargs="*", default=[])
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("data/pilot_alphabench_icc.jsonl"),
    )
    parser.add_argument("--baseline", default="rime_coda_clementine")
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--outdir", type=Path, default=Path("results/alpha_icc_pilot"))
    args = parser.parse_args()
    if not args.stats_json and not args.eval_ids:
        sys.exit("Pass --stats-json or --eval-ids.")
    families = load_corpus_families(args.corpus)
    subcategories = load_corpus_subcategories(args.corpus)
    payloads = [
        (str(path), json.loads(path.read_text(encoding="utf-8")))
        for path in args.stats_json
    ]
    payloads.extend(load_eval_ids(args.eval_ids))
    try:
        rows = [
            row
            for source, payload in payloads
            for row in parse_payload(
                payload,
                source=source,
                corpus_families=families,
                corpus_subcategories=subcategories,
                require_corpus_match=True,
            )
        ]
        result = analyze(
            rows,
            baseline=args.baseline,
            n_boot=args.n_boot,
            seed=args.seed,
        )
    except ValueError as exc:
        sys.exit(str(exc))
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "alpha_icc_pilot.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = markdown_report(result)
    (args.outdir / "alpha_icc_pilot.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
