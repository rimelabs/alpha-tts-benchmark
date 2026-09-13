"""Estimate precision at different preference-benchmark vote counts.

The script accepts four Podonos exports from the 120-item tranche. It
prints variance components and vote-count projections without printing model
names, effect directions, item scores, or win counts. Projection uses the
actual family-size distribution of the complete corpus.
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
from scipy.stats import norm

from analyze_comparison import load_corpus_families, parse_export

TRANCHE_ITEMS = 120
INITIAL_VOTES = 7
CANDIDATE_VOTES = (3, 5, 7, 10, 15, 20)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_corpus(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def nested_variance_components(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Unequal-family one-way ANOVA with judgment-noise subtraction."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["family_id"]].append(row)
    n = len(rows)
    g = len(grouped)
    if g < 2 or n <= g:
        raise ValueError(
            "the tranche needs repeated items within at least one family to "
            "estimate nested variance"
        )
    values = np.asarray(
        [row["rime_minus_competitor"] for row in rows],
        dtype=float,
    )
    grand = float(np.mean(values))
    ss_between = 0.0
    ss_within = 0.0
    for family_rows in grouped.values():
        family_values = np.asarray(
            [row["rime_minus_competitor"] for row in family_rows],
            dtype=float,
        )
        family_mean = float(np.mean(family_values))
        ss_between += len(family_rows) * (family_mean - grand) ** 2
        ss_within += float(np.sum((family_values - family_mean) ** 2))
    ms_between = ss_between / (g - 1)
    ms_within = ss_within / (n - g)
    n0 = (n - sum(len(items) ** 2 for items in grouped.values()) / n) / (g - 1)
    judgment_variance = float(np.mean([row["within_variance"] for row in rows]))
    mean_judgment_noise = float(np.mean([
        row["within_variance"] / row["judgments"] for row in rows
    ]))
    item_variance = max(0.0, ms_within - mean_judgment_noise)
    family_variance = max(0.0, (ms_between - ms_within) / n0)
    total = family_variance + item_variance + judgment_variance
    rho = family_variance / total if total > 0 else 0.0
    return {
        "family_variance": family_variance,
        "item_variance": item_variance,
        "judgment_variance": judgment_variance,
        "frame_icc": rho,
        "tranche_families": float(g),
        "repeated_tranche_families": float(sum(len(items) > 1 for items in grouped.values())),
    }


def projected_standard_error(
    components: dict[str, float],
    *,
    full_family_sizes: list[int],
    tranche_items: int,
    initial_votes: int,
    continuation_votes: int,
) -> float:
    total_items = sum(full_family_sizes)
    family_weight_square_sum = sum(
        (size / total_items) ** 2 for size in full_family_sizes
    )
    retained_tranche_votes = max(initial_votes, continuation_votes)
    judgment_inverse_votes = (
        tranche_items / retained_tranche_votes
        + (total_items - tranche_items) / continuation_votes
    )
    variance = (
        components["family_variance"] * family_weight_square_sum
        + components["item_variance"] / total_items
        + components["judgment_variance"]
        * judgment_inverse_votes
        / total_items**2
    )
    return math.sqrt(max(0.0, variance))


def plan(
    rows: list[dict[str, Any]],
    *,
    corpus: list[dict[str, Any]],
    comparisons: int,
    power: float,
    alpha: float,
    target_mde: float,
    candidate_votes: list[int],
    tranche_items: int,
    initial_votes: int,
    blinding_seed: int,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["competitor"]].append(row)
    if len(grouped) != comparisons:
        raise ValueError(f"expected {comparisons} comparisons, found {len(grouped)}")
    family_sizes: dict[str, int] = defaultdict(int)
    for row in corpus:
        family_sizes[row["family_id"]] += 1
    critical = float(
        norm.ppf(1 - alpha / (2 * comparisons)) + norm.ppf(power)
    )

    comparison_results: list[dict[str, Any]] = []
    for index, (_, comparison_rows) in enumerate(sorted(grouped.items()), start=1):
        if len(comparison_rows) != tranche_items:
            raise ValueError(
                f"comparison {index} has {len(comparison_rows)} items, expected "
                f"the {tranche_items}-item tranche"
            )
        if {row["judgments"] for row in comparison_rows} != {initial_votes}:
            raise ValueError(
                f"comparison {index} does not have exactly {initial_votes} "
                "valid judgments on every tranche item"
            )
        blind_sign = -1.0 if int(
            hashlib.sha256(f"{blinding_seed}:{index}".encode()).hexdigest(),
            16,
        ) % 2 else 1.0
        blinded_rows = [
            {
                **row,
                "rime_minus_competitor": blind_sign * row["rime_minus_competitor"],
            }
            for row in comparison_rows
        ]
        components = nested_variance_components(blinded_rows)
        candidates = []
        for votes in candidate_votes:
            standard_error = projected_standard_error(
                components,
                full_family_sizes=list(family_sizes.values()),
                tranche_items=tranche_items,
                initial_votes=initial_votes,
                continuation_votes=votes,
            )
            mde = critical * standard_error
            candidates.append({
                "votes_per_remaining_item": votes,
                "tranche_votes_retained_or_topped_up_to": max(initial_votes, votes),
                "projected_standard_error": standard_error,
                "mde_80_power": mde,
                "meets_target": mde <= target_mde,
            })
        comparison_results.append({
            "blinded_comparison": f"comparison_{index:02d}",
            "variance_components": components,
            "candidates": candidates,
        })

    selected = next(
        (
            votes for votes in candidate_votes
            if all(
                next(
                    candidate for candidate in result["candidates"]
                    if candidate["votes_per_remaining_item"] == votes
                )["meets_target"]
                for result in comparison_results
            )
        ),
        None,
    )
    return {
        "blinding": (
            "No model names, effect directions, item scores, or win counts are "
            "written to this report. Only variance components are inspected."
        ),
        "full_design": {
            "items": len(corpus),
            "families": len(family_sizes),
            "family_size_min": min(family_sizes.values()),
            "family_size_max": max(family_sizes.values()),
            "kish_effective_families": (
                len(corpus) ** 2
                / sum(size * size for size in family_sizes.values())
            ),
        },
        "planning_parameters": {
            "tranche_items_per_comparison": tranche_items,
            "initial_votes_per_item": initial_votes,
            "comparisons": comparisons,
            "familywise_alpha": alpha,
            "power": power,
            "target_mde": target_mde,
            "candidate_votes": candidate_votes,
            "critical_value": critical,
            "global_sign_blinding_seed": blinding_seed,
        },
        "selected_votes_per_remaining_item": selected,
        "comparisons": comparison_results,
    }


def markdown_report(benchmark: str, result: dict[str, Any]) -> str:
    lines = [
        f"# {benchmark} blinded variance-tranche plan",
        "",
        result["blinding"],
        "",
        (
            f"Full design: {result['full_design']['items']} items, "
            f"{result['full_design']['families']} families, Kish effective "
            f"families {result['full_design']['kish_effective_families']:.2f}."
        ),
        "",
        "| comparison | family variance | item variance | judgment variance | ICC | votes | projected MDE | meets target |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for comparison in result["comparisons"]:
        components = comparison["variance_components"]
        for candidate in comparison["candidates"]:
            lines.append(
                f"| {comparison['blinded_comparison']} "
                f"| {components['family_variance']:.4f} "
                f"| {components['item_variance']:.4f} "
                f"| {components['judgment_variance']:.4f} "
                f"| {components['frame_icc']:.3f} "
                f"| {candidate['votes_per_remaining_item']} "
                f"| {candidate['mde_80_power']:.3f} "
                f"| {'yes' if candidate['meets_target'] else 'no'} |"
            )
    selected = result["selected_votes_per_remaining_item"]
    lines.extend([
        "",
        (
            f"Smallest tested continuation vote count meeting the target: {selected}."
            if selected is not None
            else "No tested vote count meets the target for every comparison."
        ),
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stats-json", nargs="+", type=Path, required=True)
    parser.add_argument("--benchmark", choices=["SupportBench", "ContentBench"], required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--comparisons", type=int, default=4)
    parser.add_argument("--power", type=float, default=0.8)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target-mde", type=float, default=0.15)
    parser.add_argument("--candidate-votes", default=",".join(map(str, CANDIDATE_VOTES)))
    parser.add_argument("--tranche-items", type=int, default=TRANCHE_ITEMS)
    parser.add_argument("--initial-votes", type=int, default=INITIAL_VOTES)
    parser.add_argument("--blinding-seed", type=int, default=20260826)
    parser.add_argument("--rime-prefix", default="rime_")
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    candidates = sorted({
        int(value) for value in args.candidate_votes.split(",") if value.strip()
    })
    corpus_rows = read_corpus(args.corpus)
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
        result = plan(
            rows,
            corpus=corpus_rows,
            comparisons=args.comparisons,
            power=args.power,
            alpha=args.alpha,
            target_mde=args.target_mde,
            candidate_votes=candidates,
            tranche_items=args.tranche_items,
            initial_votes=args.initial_votes,
            blinding_seed=args.blinding_seed,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    result["sources"] = [
        {"sha256": sha256_file(path)} for path in args.stats_json
    ]
    result["benchmark"] = args.benchmark
    result["corpus"] = {"sha256": sha256_file(args.corpus)}
    args.outdir.mkdir(parents=True, exist_ok=True)
    stem = args.benchmark.lower()
    (args.outdir / f"{stem}_tranche_plan.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = markdown_report(args.benchmark, result)
    (args.outdir / f"{stem}_tranche_plan.md").write_text(
        report,
        encoding="utf-8",
    )
    print(report)


if __name__ == "__main__":
    main()
