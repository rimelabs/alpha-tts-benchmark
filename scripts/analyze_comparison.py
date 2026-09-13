"""Analyze SupportBench or ContentBench aggregate Podonos exports.

Podonos comparison scores are positive for canonical target A. This script
uses target metadata to recode every item so positive always favors Rime.
It averages repeated judgments within item, bootstraps families,
performs a cluster sign-flip test, and applies Holm correction across the
four competitor comparisons.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from stats_utils import (
    clustered_bootstrap_mean,
    clustered_sign_flip_p,
    holm_adjust,
    kish_effective_clusters,
    tag_value,
)
from claim_rules import assess_directional_claim


def load_corpus_families(path: Path | None) -> dict[str, str]:
    families, _coarse_clusters = load_corpus_metadata(path)
    return families


def _author_cluster(row: dict[str, Any]) -> str:
    family = row["family_id"]
    if row.get("category") != "content_reading":
        return family
    if row.get("subcategory") != "literature":
        return f"content-genre:{row['subcategory']}"
    author = row.get("author")
    if not author:
        notes = str(row.get("notes", ""))
        if not notes.startswith("Source: ") or ", " not in notes:
            raise ValueError(
                f"literature item {row['id']} lacks author metadata"
            )
        _title, author = notes.removeprefix("Source: ").rsplit(", ", 1)
    slug = re.sub(r"[^a-z0-9]+", "-", str(author).lower()).strip("-")
    if not slug:
        raise ValueError(f"literature item {row['id']} has an empty author")
    return f"content-author:{slug}"


def load_corpus_metadata(
    path: Path | None,
) -> tuple[dict[str, str], dict[str, str]]:
    if path is None:
        return {}, {}
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return (
        {row["id"]: row["family_id"] for row in rows},
        {row["id"]: _author_cluster(row) for row in rows},
    )


def frequency_moments(frequency: list[dict[str, Any]]) -> tuple[int, float, float]:
    observations = [
        float(entry["score"])
        for entry in frequency
        for _ in range(int(entry["count"]))
    ]
    if not observations:
        raise ValueError("comparison item has no judgments")
    mean = sum(observations) / len(observations)
    if len(observations) == 1:
        variance = 0.0
    else:
        variance = sum(
            (value - mean) ** 2 for value in observations
        ) / (len(observations) - 1)
    return len(observations), mean, variance


def parse_export(
    path: Path,
    *,
    rime_prefix: str,
    corpus_families: dict[str, str],
    coarse_clusters: dict[str, str] | None = None,
    require_corpus_match: bool = False,
) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"{path} is not a Podonos question export")
    responses = payload[0].get("responses", [])
    rows: list[dict[str, Any]] = []
    for response in responses:
        targets = response.get("targets", [])
        if len(targets) != 2:
            raise ValueError(f"{path} contains a non-pair response")
        by_type = {target["type"]: target for target in targets}
        if set(by_type) != {"A", "B"}:
            raise ValueError(f"{path} target types are not A/B: {set(by_type)}")
        rime_targets = [
            target
            for target in targets
            if target["model_tag"].startswith(rime_prefix)
        ]
        if len(rime_targets) != 1:
            raise ValueError(
                f"{path} requires exactly one Rime target per pair"
            )
        rime_target = rime_targets[0]
        competitor_target = next(
            target for target in targets if target is not rime_target
        )
        tags = list(rime_target.get("tags", []))
        item_id = tag_value(tags, "utt_")
        if item_id is None:
            item_id = Path(rime_target["path"]).stem
        tagged_family = tag_value(tags, "family_")
        corpus_family = corpus_families.get(item_id)
        if require_corpus_match and corpus_families and corpus_family is None:
            raise ValueError(
                f"{path} item {item_id} is absent from the corpus"
            )
        if tagged_family and corpus_family and tagged_family != corpus_family:
            raise ValueError(
                f"{path} item {item_id} has family {tagged_family!r} in the "
                f"export but {corpus_family!r} in the corpus"
            )
        family = (
            corpus_family
            or tagged_family
            or tag_value(tags, "sub_")
            or f"item:{item_id}"
        )
        coarse_cluster = (coarse_clusters or {}).get(item_id, family)
        judgments, canonical_mean, within_variance = frequency_moments(
            response["frequency"]
        )
        rime_sign = 1.0 if rime_target["type"] == "A" else -1.0
        rows.append({
            "item_id": item_id,
            "family_id": family,
            "coarse_cluster_id": coarse_cluster,
            "competitor": competitor_target["model_tag"],
            "rime_target": rime_target["type"],
            "judgments": judgments,
            "rime_minus_competitor": rime_sign * canonical_mean,
            "within_variance": within_variance,
            "source": str(path),
        })
    return rows


def combine_repeated_item_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pool aggregate moments when one item is rated in more than one job."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["competitor"], row["item_id"])].append(row)
    combined: list[dict[str, Any]] = []
    for _key, item_rows in sorted(grouped.items()):
        first = item_rows[0]
        if len({row["family_id"] for row in item_rows}) != 1:
            raise ValueError(f"family changed across jobs for {first['item_id']}")
        if len({row.get("coarse_cluster_id") for row in item_rows}) != 1:
            raise ValueError(
                f"coarse cluster changed across jobs for {first['item_id']}"
            )
        total = sum(row["judgments"] for row in item_rows)
        mean = sum(
            row["judgments"] * row["rime_minus_competitor"]
            for row in item_rows
        ) / total
        if total == 1:
            variance = 0.0
        else:
            sum_squares = sum(
                (row["judgments"] - 1) * row["within_variance"]
                + row["judgments"]
                * (row["rime_minus_competitor"] - mean) ** 2
                for row in item_rows
            )
            variance = sum_squares / (total - 1)
        combined.append({
            **first,
            "judgments": total,
            "rime_minus_competitor": mean,
            "within_variance": variance,
            "source": sorted({row["source"] for row in item_rows}),
            "source_jobs": len(item_rows),
        })
    return combined


def analyze(
    rows: list[dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in combine_repeated_item_rows(rows):
        grouped[row["competitor"]].append(row)
    raw_p: dict[str, float] = {}
    coarse_raw_p: dict[str, float] = {}
    has_coarse_sensitivity = any(
        row.get("coarse_cluster_id", row["family_id"]) != row["family_id"]
        for row in rows
    )
    results: dict[str, dict[str, Any]] = {}
    for offset, (competitor, competitor_rows) in enumerate(sorted(grouped.items())):
        item_ids = [row["item_id"] for row in competitor_rows]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError(f"duplicate items for {competitor}")
        values = [row["rime_minus_competitor"] for row in competitor_rows]
        families = [row["family_id"] for row in competitor_rows]
        coarse_clusters = [
            row.get("coarse_cluster_id", row["family_id"])
            for row in competitor_rows
        ]
        estimate, interval, _ = clustered_bootstrap_mean(
            values,
            families,
            n_boot=n_boot,
            seed=seed + offset,
        )
        p_value = clustered_sign_flip_p(
            values,
            families,
            seed=seed + offset,
        )
        raw_p[competitor] = p_value
        items = len(values)
        wins = sum(value > 0 for value in values)
        ties = sum(value == 0 for value in values)
        losses = sum(value < 0 for value in values)
        results[competitor] = {
            "items": items,
            "families": len(set(families)),
            "kish_effective_families": kish_effective_clusters(families),
            "valid_judgments": sum(row["judgments"] for row in competitor_rows),
            "mean_rime_minus_competitor": estimate,
            "ci_95": list(interval),
            "raw_cluster_sign_flip_p": p_value,
            "win_items": wins,
            "tie_items": ties,
            "loss_items": losses,
            "win_item_rate": wins / items,
            "tie_item_rate": ties / items,
            "loss_item_rate": losses / items,
        }
        if has_coarse_sensitivity:
            coarse_estimate, coarse_interval, _ = clustered_bootstrap_mean(
                values,
                coarse_clusters,
                n_boot=n_boot,
                seed=seed + 10_000 + offset,
            )
            coarse_p = clustered_sign_flip_p(
                values,
                coarse_clusters,
                seed=seed + 10_000 + offset,
            )
            coarse_raw_p[competitor] = coarse_p
            results[competitor]["sensitivity_coarse_dependency"] = {
                "method": (
                    "cluster literature excerpts by author and other "
                    "ContentBench items by genre"
                ),
                "clusters": len(set(coarse_clusters)),
                "kish_effective_clusters": kish_effective_clusters(
                    coarse_clusters
                ),
                "mean_rime_minus_competitor": coarse_estimate,
                "ci_95": list(coarse_interval),
                "raw_cluster_sign_flip_p": coarse_p,
            }
    adjusted = holm_adjust(raw_p)
    coarse_adjusted = holm_adjust(coarse_raw_p) if coarse_raw_p else {}
    for competitor, p_value in adjusted.items():
        results[competitor]["holm_p"] = p_value
        results[competitor]["claim"] = assess_directional_claim(
            results[competitor]["mean_rime_minus_competitor"],
            results[competitor]["ci_95"],
            p_value,
        )
        if competitor in coarse_adjusted:
            results[competitor]["sensitivity_coarse_dependency"]["holm_p"] = (
                coarse_adjusted[competitor]
            )
    return results


def markdown_report(
    benchmark: str,
    results: dict[str, dict[str, Any]],
) -> str:
    lines = [
        f"# {benchmark} comparison results",
        "",
        (
            "Positive effects favor Rime. Confidence intervals use the "
            "family-clustered bootstrap. Holm p-values cover the planned competitor "
            "comparisons included in this run."
        ),
        "",
        "| competitor | items | families | Kish G | judgments | Rime - competitor [95% CI] | W/T/L count | W/T/L proportion | raw p | Holm p | claim status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for competitor, result in sorted(results.items()):
        low, high = result["ci_95"]
        lines.append(
            f"| {competitor} | {result['items']} | {result['families']} "
            f"| {result['kish_effective_families']:.2f} "
            f"| {result['valid_judgments']} "
            f"| {result['mean_rime_minus_competitor']:+.3f} "
            f"[{low:+.3f}, {high:+.3f}] "
            f"| {result['win_items']}/{result['tie_items']}/{result['loss_items']} "
            f"| {result['win_item_rate']:.1%}/{result['tie_item_rate']:.1%}/"
            f"{result['loss_item_rate']:.1%} "
            f"| {result['raw_cluster_sign_flip_p']:.4g} "
            f"| {result['holm_p']:.4g} | {result['claim']['status']} |"
        )
    if any("sensitivity_coarse_dependency" in item for item in results.values()):
        lines.extend([
            "",
            "## Coarser dependence sensitivity",
            "",
            (
                "This ContentBench sensitivity clusters literature "
                "excerpts by author and other items by genre. It can qualify a "
                "primary claim but cannot license one."
            ),
            "",
            "| competitor | clusters | Kish G | Rime - competitor [95% CI] | raw p | Holm p |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for competitor, result in sorted(results.items()):
            sensitivity = result["sensitivity_coarse_dependency"]
            low, high = sensitivity["ci_95"]
            lines.append(
                f"| {competitor} | {sensitivity['clusters']} "
                f"| {sensitivity['kish_effective_clusters']:.2f} "
                f"| {sensitivity['mean_rime_minus_competitor']:+.3f} "
                f"[{low:+.3f}, {high:+.3f}] "
                f"| {sensitivity['raw_cluster_sign_flip_p']:.4g} "
                f"| {sensitivity['holm_p']:.4g} |"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stats-json", nargs="+", type=Path, required=True)
    parser.add_argument("--benchmark", choices=["SupportBench", "ContentBench"], required=True)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--rime-prefix", default="rime_")
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="analyze a smaller exploratory comparison family",
    )
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()

    families, coarse_clusters = load_corpus_metadata(args.corpus)
    rows: list[dict[str, Any]] = []
    for path in args.stats_json:
        try:
            rows.extend(
                parse_export(
                    path,
                    rime_prefix=args.rime_prefix,
                    corpus_families=families,
                    coarse_clusters=coarse_clusters,
                    require_corpus_match=bool(args.corpus),
                )
            )
        except ValueError as exc:
            sys.exit(str(exc))
    results = analyze(rows, n_boot=args.n_boot, seed=args.seed)
    if len(results) != 4 and not args.allow_partial:
        sys.exit(
            f"The benchmark analysis covers four competitors; found {len(results)}. "
            "Pass --allow-partial to analyze a smaller exploratory comparison family."
        )
    args.outdir.mkdir(parents=True, exist_ok=True)
    stem = args.benchmark.lower()
    (args.outdir / f"{stem}_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = markdown_report(args.benchmark, results)
    (args.outdir / f"{stem}_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
