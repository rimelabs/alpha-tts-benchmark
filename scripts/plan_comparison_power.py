"""Plan A/B vote counts from completed Podonos pilot exports.

The calculation separates within-item judgment variance from between-item
variance, carries forward the observed family-cluster inflation, and uses a
conservative four-comparison critical value. It is a planning calculation,
not a perceptual threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from analyze_comparison import load_corpus_families, parse_export
from scipy.stats import norm
from stats_utils import clustered_bootstrap_mean


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan(
    rows: list[dict[str, Any]],
    *,
    planned_items: int,
    comparisons: int,
    power: float,
    alpha: float,
    target_mde: float,
    candidate_votes: list[int],
    seed: int,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["competitor"]].append(row)
    critical = float(
        norm.ppf(1 - alpha / (2 * comparisons)) + norm.ppf(power)
    )
    competitors: dict[str, Any] = {}
    for offset, (competitor, competitor_rows) in enumerate(sorted(grouped.items())):
        values = np.asarray(
            [row["rime_minus_competitor"] for row in competitor_rows],
            dtype=float,
        )
        families = [row["family_id"] for row in competitor_rows]
        pilot_votes = float(np.mean(
            [row["judgments"] for row in competitor_rows]
        ))
        within_variance = float(np.mean(
            [row["within_variance"] for row in competitor_rows]
        ))
        item_mean_variance = float(np.var(values, ddof=1))
        between_variance = max(
            0.0,
            item_mean_variance - within_variance / pilot_votes,
        )
        _, _, bootstrap_samples = clustered_bootstrap_mean(
            values.tolist(),
            families,
            n_boot=5_000,
            seed=seed + offset,
        )
        naive_pilot_variance = item_mean_variance / len(values)
        bootstrap_variance = float(np.var(bootstrap_samples, ddof=1))
        cluster_inflation = (
            max(1.0, bootstrap_variance / naive_pilot_variance)
            if naive_pilot_variance > 0
            else 1.0
        )
        table = []
        for votes in candidate_votes:
            standard_error = math.sqrt(
                cluster_inflation
                * (between_variance + within_variance / votes)
                / planned_items
            )
            mde = float(critical * standard_error)
            table.append({
                "votes_per_item": votes,
                "standard_error": standard_error,
                "mde_80_power": mde,
                "meets_target": bool(mde <= target_mde),
            })
        competitors[competitor] = {
            "pilot_items": len(values),
            "pilot_votes_per_item": pilot_votes,
            "pilot_item_mean_variance": item_mean_variance,
            "estimated_within_item_variance": within_variance,
            "estimated_between_item_variance": between_variance,
            "observed_cluster_inflation": cluster_inflation,
            "candidates": table,
        }

    selected = next(
        (
            votes
            for votes in candidate_votes
            if all(
                next(
                    row for row in result["candidates"]
                    if row["votes_per_item"] == votes
                )["meets_target"]
                for result in competitors.values()
            )
        ),
        None,
    )
    return {
        "planned_items": planned_items,
        "comparisons": comparisons,
        "alpha_familywise": alpha,
        "power": power,
        "target_mde": target_mde,
        "critical_value": critical,
        "minimum_votes_per_item": selected,
        "competitors": competitors,
    }


def markdown_report(benchmark: str, result: dict[str, Any]) -> str:
    lines = [
        f"# {benchmark} pilot-based vote planning",
        "",
        (
            f"Planned items: {result['planned_items']}. "
            f"Familywise alpha: {result['alpha_familywise']}. "
            f"Comparisons: {result['comparisons']}. "
            f"Power: {result['power']:.0%}. "
            f"Planning MDE target: {result['target_mde']:.3f}."
        ),
        "",
        "| competitor | pilot items | cluster inflation | votes | MDE | target met |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for competitor, competitor_result in sorted(
        result["competitors"].items()
    ):
        for row in competitor_result["candidates"]:
            lines.append(
                f"| {competitor} | {competitor_result['pilot_items']} "
                f"| {competitor_result['observed_cluster_inflation']:.2f} "
                f"| {row['votes_per_item']} "
                f"| {row['mde_80_power']:.3f} "
                f"| {'yes' if row['meets_target'] else 'no'} |"
            )
    selected = result["minimum_votes_per_item"]
    lines.extend([
        "",
        (
            f"Smallest tested vote count meeting the target: {selected}."
            if selected is not None
            else "No candidate vote count meets the target for every competitor."
        ),
        "",
        (
            "The MDE target is a planning resolution, not a claim that listeners "
            "can or cannot perceive a difference of that size."
        ),
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stats-json", nargs="+", type=Path, required=True)
    parser.add_argument("--benchmark", choices=["SupportBench", "ContentBench"], required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--planned-items", type=int, required=True)
    parser.add_argument("--comparisons", type=int, default=4)
    parser.add_argument("--power", type=float, default=0.8)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target-mde", type=float, default=0.15)
    parser.add_argument("--candidate-votes", default="3,5,7,10,15,20")
    parser.add_argument("--rime-prefix", default="rime_")
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()

    candidates = sorted({
        int(value)
        for value in args.candidate_votes.split(",")
        if value.strip()
    })
    families = load_corpus_families(args.corpus)
    try:
        rows = [
            row
            for path in args.stats_json
            for row in parse_export(
                path,
                rime_prefix=args.rime_prefix,
                corpus_families=families,
                require_corpus_match=True,
            )
        ]
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    result = plan(
        rows,
        planned_items=args.planned_items,
        comparisons=args.comparisons,
        power=args.power,
        alpha=args.alpha,
        target_mde=args.target_mde,
        candidate_votes=candidates,
        seed=args.seed,
    )
    result["sources"] = [
        {"file": path.name, "sha256": sha256_file(path)}
        for path in args.stats_json
    ]
    result["corpus"] = {
        "path": str(args.corpus),
        "sha256": sha256_file(args.corpus),
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    stem = args.benchmark.lower()
    (args.outdir / f"{stem}_power.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = markdown_report(args.benchmark, result)
    (args.outdir / f"{stem}_power.md").write_text(
        report,
        encoding="utf-8",
    )
    print(report)


if __name__ == "__main__":
    main()
