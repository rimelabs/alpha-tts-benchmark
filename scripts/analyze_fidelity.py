"""Compute optional AlphaBench statistical diagnostics.

The AlphaBench report is qualitative and uses
``analyze_alphabench_qualitative.py``. These diagnostics cannot license
provider rankings or directional claims.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from stats_utils import (
    bootstrap_mean,
    holm_adjust,
    kish_effective_clusters,
    mcnemar_exact_p,
    stratified_cluster_sign_flip_p,
    stratified_clustered_bootstrap_mean,
    stratified_wild_cluster_t_interval,
    tag_value,
    wilson_ci,
)
from claim_rules import assess_directional_claim

ALPHABENCH_SUBCATEGORY_COUNTS = {
    "confirmation_code": 98,
    "confusable": 40,
    "flight_number": 66,
    "license_plate": 40,
    "long_code": 40,
    "name_spelling": 80,
    "order_number": 96,
    "policy_case_id": 73,
    "tracking_number": 47,
}
ALPHABENCH_SUBCATEGORY_WEIGHTS = {
    name: count / sum(ALPHABENCH_SUBCATEGORY_COUNTS.values())
    for name, count in ALPHABENCH_SUBCATEGORY_COUNTS.items()
}
PERCENTILE_ALPHA_INTERVAL_METHOD = "stratified family percentile bootstrap"
WILD_ALPHA_INTERVAL_METHOD = "stratified wild cluster bootstrap-t"
PRIMARY_ALPHA_INTERVAL_METHOD = PERCENTILE_ALPHA_INTERVAL_METHOD

ERROR_LABELS = ("Reading error", "Yes — there is an issue")
PASS_LABELS = ("No reading error", "No — the sequence is clear and complete")
TRIVIAL_NOTES = {
    "none",
    "n/a",
    "na",
    "no",
    "-",
    "nothing",
    "no issues",
    "none.",
}


def load_corpus_families(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {row["id"]: row["family_id"] for row in rows}


def load_corpus_subcategories(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {row["id"]: row["subcategory"] for row in rows}


def load_corpus_diagnostics(path: Path | None) -> dict[str, dict[str, int]]:
    if path is None:
        return {}
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        row["id"]: {
            "target_entities": len(row.get("spell_spans", [])),
            "script_length_chars": len(row["text"]),
        }
        for row in rows
    }


def response_count(response: dict[str, Any], labels: tuple[str, ...]) -> int:
    return sum(int(response.get(label, 0)) for label in labels)


def parse_payload(
    payload: list[dict[str, Any]],
    *,
    source: str,
    corpus_families: dict[str, str],
    corpus_subcategories: dict[str, str] | None = None,
    corpus_diagnostics: dict[str, dict[str, int]] | None = None,
    require_corpus_match: bool = False,
) -> list[dict[str, Any]]:
    if not payload:
        return []
    responses = payload[0].get("responses", [])
    rows: list[dict[str, Any]] = []
    for response in responses:
        tags = list(response.get("tags", []))
        item_id = tag_value(tags, "utt_") or Path(response["path"]).stem
        tagged_family = tag_value(tags, "family_")
        corpus_family = corpus_families.get(item_id)
        if require_corpus_match and corpus_families and corpus_family is None:
            raise ValueError(
                f"{source} item {item_id} is absent from the corpus"
            )
        if tagged_family and corpus_family and tagged_family != corpus_family:
            raise ValueError(
                f"{source} item {item_id} has family {tagged_family!r} in the "
                f"export but {corpus_family!r} in the corpus"
            )
        family = (
            corpus_family
            or tagged_family
            or tag_value(tags, "sub_")
            or f"item:{item_id}"
        )
        error_votes = response_count(response, ERROR_LABELS)
        pass_votes = response_count(response, PASS_LABELS)
        if error_votes + pass_votes == 0:
            raise ValueError(
                f"{source} item {item_id} has no recognized AlphaBench votes"
            )
        notes = []
        for annotation in response.get("annotations", []):
            note = str(
                annotation.get("reason")
                or annotation.get("content")
                or ""
            ).strip()
            if note and note.lower() not in TRIVIAL_NOTES:
                notes.append(note)
        corpus_subcategory = (corpus_subcategories or {}).get(item_id)
        tagged_subcategory = tag_value(tags, "sub_")
        if (
            corpus_subcategory
            and tagged_subcategory
            and corpus_subcategory != tagged_subcategory
        ):
            raise ValueError(
                f"{source} item {item_id} has subcategory "
                f"{tagged_subcategory!r} in the export but "
                f"{corpus_subcategory!r} in the corpus"
            )
        diagnostics = (corpus_diagnostics or {}).get(item_id, {})
        script = response.get("script", "")
        rows.append({
            "model_tag": response["model_tag"],
            "item_id": item_id,
            "family_id": family,
            "subcategory": (
                corpus_subcategory
                or tagged_subcategory
                or next(
                    (
                        tag
                        for tag in tags
                        if not tag.startswith(
                            ("utt_", "family_", "campaign_", "protocol_")
                        )
                    ),
                    "?",
                )
            ),
            "script": script,
            "target_entities": diagnostics.get("target_entities"),
            "script_length_chars": diagnostics.get(
                "script_length_chars", len(script)
            ),
            "error_votes": error_votes,
            "pass_votes": pass_votes,
            "majority_error": error_votes > pass_votes,
            "notes": notes,
            "source": source,
        })
    return rows


def load_eval_ids(eval_ids: list[str]) -> list[tuple[str, list[dict[str, Any]]]]:
    if not eval_ids:
        return []
    import podonos

    api_key = os.environ.get("PODONOS_API_KEY", "")
    if not api_key:
        sys.exit("Set PODONOS_API_KEY to load --eval-ids.")
    client = podonos.init(api_key=api_key)
    loaded = []
    for evaluation_id in eval_ids:
        payload = client.get_stats_json_by_id(evaluation_id)
        if not payload:
            raise ValueError(f"no stats returned for {evaluation_id}")
        loaded.append((evaluation_id, payload))
    return loaded


def analyze(
    rows: list[dict[str, Any]],
    *,
    baseline: str,
    n_boot: int,
    seed: int,
    subcategory_weights: dict[str, float] | None = None,
    primary_interval_method: str = PRIMARY_ALPHA_INTERVAL_METHOD,
) -> dict[str, Any]:
    by_model: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        model_rows = by_model[row["model_tag"]]
        if row["item_id"] in model_rows:
            raise ValueError(
                f"duplicate item {row['item_id']} for {row['model_tag']}"
            )
        model_rows[row["item_id"]] = row
    if baseline not in by_model:
        raise ValueError(f"baseline {baseline!r} not found")

    present_subcategories = sorted({
        row["subcategory"] for row in rows if row["subcategory"] != "?"
    })
    if subcategory_weights is not None:
        missing = set(present_subcategories) - set(subcategory_weights)
        if missing:
            raise ValueError(
                f"no AlphaBench weight for {sorted(missing)}"
            )
        selected = {
            name: subcategory_weights[name] for name in present_subcategories
        }
        total = sum(selected.values())
        subcategory_weights = {
            name: value / total for name, value in selected.items()
        }
    else:
        if present_subcategories and set(present_subcategories).issubset(
            ALPHABENCH_SUBCATEGORY_WEIGHTS
        ):
            selected = {
                name: ALPHABENCH_SUBCATEGORY_WEIGHTS[name]
                for name in present_subcategories
            }
            total = sum(selected.values())
            subcategory_weights = {
                name: value / total for name, value in selected.items()
            }
        else:
            subcategory_weights = None

    providers: dict[str, Any] = {}
    for model_tag, model_rows in sorted(by_model.items()):
        values = list(model_rows.values())
        clips = len(values)
        majority_errors = sum(row["majority_error"] for row in values)
        any_errors = sum(row["error_votes"] > 0 for row in values)
        error_votes = sum(row["error_votes"] for row in values)
        votes = sum(
            row["error_votes"] + row["pass_votes"] for row in values
        )
        binary = [float(row["majority_error"]) for row in values]
        vote_means = [
            row["error_votes"] / (row["error_votes"] + row["pass_votes"])
            for row in values
        ]
        families = [row["family_id"] for row in values]
        strata = [row["subcategory"] for row in values]
        weighted_rate, weighted_interval, _ = stratified_clustered_bootstrap_mean(
            binary,
            families,
            strata,
            stratum_weights=subcategory_weights,
            n_boot=n_boot,
            seed=seed,
        )
        vote_mean_rate, vote_mean_interval, _ = stratified_clustered_bootstrap_mean(
            vote_means,
            families,
            strata,
            stratum_weights=subcategory_weights,
            n_boot=n_boot,
            seed=seed + 25_000,
        )
        target_entities = sum(
            int(row["target_entities"])
            for row in values
            if row.get("target_entities") is not None
        )
        providers[model_tag] = {
            "clips": clips,
            "families": len(set(families)),
            "kish_effective_families": kish_effective_clusters(families),
            "valid_votes": votes,
            "error_votes": error_votes,
            "vote_error_rate": error_votes / votes,
            "any_flagged_clips": any_errors,
            "majority_flagged_clips": majority_errors,
            "primary_weighted_majority_error_rate": weighted_rate,
            "descriptive_family_percentile_ci_95": list(weighted_interval),
            "item_weighted_majority_error_rate_sensitivity": majority_errors / clips,
            "item_weighted_wilson_ci_sensitivity": list(
                wilson_ci(majority_errors, clips)
            ),
            "weighted_mean_vote_error_rate_sensitivity": vote_mean_rate,
            "weighted_mean_vote_error_ci_95_sensitivity": list(
                vote_mean_interval
            ),
            "registered_target_entities": target_entities,
            "majority_error_clips_per_target_entity_diagnostic": (
                majority_errors / target_entities if target_entities else None
            ),
        }

    comparisons: dict[str, Any] = {}
    raw_p: dict[str, float] = {}
    baseline_rows = by_model[baseline]
    competitors = [
        model_tag for model_tag in sorted(by_model) if model_tag != baseline
    ]
    for offset, competitor in enumerate(competitors):
        competitor_rows = by_model[competitor]
        common = sorted(set(baseline_rows) & set(competitor_rows))
        if not common:
            raise ValueError(f"no paired items for {competitor}")
        differences = [
            float(competitor_rows[item_id]["majority_error"])
            - float(baseline_rows[item_id]["majority_error"])
            for item_id in common
        ]
        vote_mean_differences = [
            competitor_rows[item_id]["error_votes"]
            / (
                competitor_rows[item_id]["error_votes"]
                + competitor_rows[item_id]["pass_votes"]
            )
            - baseline_rows[item_id]["error_votes"]
            / (
                baseline_rows[item_id]["error_votes"]
                + baseline_rows[item_id]["pass_votes"]
            )
            for item_id in common
        ]
        families = [
            baseline_rows[item_id]["family_id"]
            for item_id in common
        ]
        percentile_estimate, percentile_interval, _ = stratified_clustered_bootstrap_mean(
            differences,
            families,
            [baseline_rows[item_id]["subcategory"] for item_id in common],
            stratum_weights=subcategory_weights,
            n_boot=n_boot,
            seed=seed + offset,
        )
        strata = [
            baseline_rows[item_id]["subcategory"] for item_id in common
        ]
        families_by_stratum: dict[str, set[str]] = defaultdict(set)
        for family, stratum in zip(families, strata, strict=True):
            families_by_stratum[stratum].add(family)
        wild_available = all(
            len(stratum_families) >= 2
            for stratum_families in families_by_stratum.values()
        )
        if wild_available:
            wild_estimate, wild_interval, wild_diagnostics = (
                stratified_wild_cluster_t_interval(
                    differences,
                    families,
                    strata,
                    stratum_weights=subcategory_weights,
                    simulations=n_boot,
                    seed=seed + 5_000 + offset,
                )
            )
        else:
            wild_estimate = None
            wild_interval = None
            wild_diagnostics = None
        if primary_interval_method == WILD_ALPHA_INTERVAL_METHOD:
            if not wild_available:
                raise ValueError(
                    "wild cluster bootstrap-t needs at least two families "
                    "in every subcategory"
                )
            estimate = wild_estimate
            interval = wild_interval
        elif primary_interval_method == PERCENTILE_ALPHA_INTERVAL_METHOD:
            estimate = percentile_estimate
            interval = percentile_interval
        else:
            raise ValueError(
                f"unknown AlphaBench interval method {primary_interval_method!r}"
            )
        clustered_p = stratified_cluster_sign_flip_p(
            differences,
            families,
            [baseline_rows[item_id]["subcategory"] for item_id in common],
            stratum_weights=subcategory_weights,
            seed=seed + offset,
        )
        item_estimate, item_interval, _ = bootstrap_mean(
            differences,
            n_boot=n_boot,
            seed=seed + 10_000 + offset,
        )
        vote_mean_estimate, vote_mean_interval, _ = (
            stratified_clustered_bootstrap_mean(
                vote_mean_differences,
                families,
                [
                    baseline_rows[item_id]["subcategory"]
                    for item_id in common
                ],
                stratum_weights=subcategory_weights,
                n_boot=n_boot,
                seed=seed + 20_000 + offset,
            )
        )
        b = sum(
            competitor_rows[item_id]["majority_error"]
            and not baseline_rows[item_id]["majority_error"]
            for item_id in common
        )
        c = sum(
            baseline_rows[item_id]["majority_error"]
            and not competitor_rows[item_id]["majority_error"]
            for item_id in common
        )
        mcnemar_p = mcnemar_exact_p(b, c)
        raw_p[competitor] = clustered_p
        comparisons[competitor] = {
            "paired_items": len(common),
            "families": len(set(families)),
            "kish_effective_families": kish_effective_clusters(families),
            "primary_weighting": (
                "fixed subcategory weights; equal source-frame weights within "
                "subcategory; script mean within source frame"
            ),
            "confidence_interval_method": primary_interval_method,
            "competitor_minus_rime_error_rate": estimate,
            "ci_95": list(interval),
            "wild_cluster_t_diagnostics": wild_diagnostics,
            "raw_family_sign_flip_p": clustered_p,
            "discordant_competitor_only": b,
            "discordant_rime_only": c,
            "sensitivity_item_weighted_effect": item_estimate,
            "sensitivity_item_bootstrap_ci_95": list(item_interval),
            "sensitivity_raw_mcnemar_p": mcnemar_p,
            "sensitivity_family_percentile_effect": percentile_estimate,
            "sensitivity_family_percentile_ci_95": list(percentile_interval),
            "sensitivity_wild_cluster_t_effect": wild_estimate,
            "sensitivity_wild_cluster_t_ci_95": (
                list(wild_interval) if wild_interval is not None else None
            ),
            "sensitivity_weighted_mean_vote_error_effect": vote_mean_estimate,
            "sensitivity_weighted_mean_vote_error_ci_95": list(
                vote_mean_interval
            ),
        }
    adjusted = holm_adjust(raw_p)
    for competitor, p_value in adjusted.items():
        comparisons[competitor]["holm_p"] = p_value
        comparisons[competitor]["claim"] = assess_directional_claim(
            comparisons[competitor]["competitor_minus_rime_error_rate"],
            comparisons[competitor]["ci_95"],
            p_value,
        )

    annotations = [
        {
            "model_tag": row["model_tag"],
            "item_id": row["item_id"],
            "script": row["script"],
            "error_votes": row["error_votes"],
            "valid_votes": row["error_votes"] + row["pass_votes"],
            "notes": row["notes"],
        }
        for row in rows
        if row["error_votes"] > 0 or row["notes"]
    ]
    corpus_rows = list(baseline_rows.values())
    lengths_by_family: dict[str, list[int]] = defaultdict(list)
    for row in corpus_rows:
        lengths_by_family[row["family_id"]].append(row["script_length_chars"])
    script_lengths = [row["script_length_chars"] for row in corpus_rows]
    frame_mean_lengths = [
        sum(lengths) / len(lengths) for lengths in lengths_by_family.values()
    ]
    return {
        "baseline": baseline,
        "primary_subcategory_weights": subcategory_weights,
        "providers": providers,
        "comparisons": comparisons,
        "flagged_annotations": annotations,
        "corpus_diagnostics": {
            "script_length_unit": "Unicode code points in the canonical script",
            "scripts": len(corpus_rows),
            "frames": len(lengths_by_family),
            "script_length_chars_min": min(script_lengths),
            "script_length_chars_mean": sum(script_lengths) / len(script_lengths),
            "script_length_chars_max": max(script_lengths),
            "frame_mean_script_length_chars_min": min(frame_mean_lengths),
            "frame_mean_script_length_chars_mean": (
                sum(frame_mean_lengths) / len(frame_mean_lengths)
            ),
            "frame_mean_script_length_chars_max": max(frame_mean_lengths),
        },
    }


def markdown_report(results: dict[str, Any]) -> str:
    lines = [
        "# AlphaBench statistical diagnostic",
        "",
        (
            "This is an optional statistical diagnostic. The "
            "AlphaBench plan is qualitative, so this report cannot "
            "license a provider ranking or directional claim."
        ),
        "",
        (
            "Lower provider error rates are better. Primary estimates use fixed "
            "subcategory weights, equal source-frame weights within each "
            "subcategory, and the script mean within each frame. Paired intervals "
            "use the calibrated stratified family percentile bootstrap. Positive paired "
            "effects mean the competitor made more majority-flagged errors than "
            "Rime."
        ),
        "",
        "## Provider error rates",
        "",
        "| model | clips | frames | Kish G | valid votes | vote errors | any flag | weighted majority error [95% CI] | item-weighted sensitivity | mean-of-votes sensitivity [95% CI] | majority-error clips / target entity |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model_tag, result in sorted(
        results["providers"].items(),
        key=lambda item: item[1]["primary_weighted_majority_error_rate"],
    ):
        low, high = result["descriptive_family_percentile_ci_95"]
        vote_low, vote_high = result[
            "weighted_mean_vote_error_ci_95_sensitivity"
        ]
        entity_rate = result[
            "majority_error_clips_per_target_entity_diagnostic"
        ]
        entity_rate_text = (
            f"{entity_rate:.3f}" if entity_rate is not None else "not available"
        )
        lines.append(
            f"| {model_tag} | {result['clips']} | {result['families']} "
            f"| {result['kish_effective_families']:.2f} "
            f"| {result['valid_votes']} "
            f"| {result['error_votes']} ({result['vote_error_rate']:.1%}) "
            f"| {result['any_flagged_clips']} "
            f"| {result['primary_weighted_majority_error_rate']:.1%} "
            f"[{low:.1%}, {high:.1%}] "
            f"| {result['item_weighted_majority_error_rate_sensitivity']:.1%} "
            f"| {result['weighted_mean_vote_error_rate_sensitivity']:.1%} "
            f"[{vote_low:.1%}, {vote_high:.1%}] "
            f"| {entity_rate_text} |"
        )
    lines.extend([
        "",
        "## Paired comparisons against Rime",
        "",
        (
            "Primary intervals use the stratified family percentile bootstrap "
            "over source frames. The family sign-flip test and its Holm "
            "adjustment govern directional claims. Item bootstrap and McNemar "
            "results are sensitivities and cannot license a claim rejected by "
            "the primary analysis."
        ),
        "",
        "| competitor | paired clips | frames | Kish G | competitor - Rime weighted error rate [95% CI] | family p | Holm p | claim status | item sensitivity [95% CI]; McNemar p | mean-of-votes sensitivity [95% CI] |",
        "|---|---:|---:|---:|---:|---:|---:|---|---:|---:|",
    ])
    for competitor, result in sorted(results["comparisons"].items()):
        low, high = result["ci_95"]
        item_low, item_high = result["sensitivity_item_bootstrap_ci_95"]
        vote_low, vote_high = result[
            "sensitivity_weighted_mean_vote_error_ci_95"
        ]
        lines.append(
            f"| {competitor} | {result['paired_items']} "
            f"| {result['families']} "
            f"| {result['kish_effective_families']:.2f} "
            f"| {result['competitor_minus_rime_error_rate']:+.1%} "
            f"[{low:+.1%}, {high:+.1%}] "
            f"| {result['raw_family_sign_flip_p']:.4g} "
            f"| {result['holm_p']:.4g} "
            f"| {result['claim']['status']} "
            f"| {result['sensitivity_item_weighted_effect']:+.1%} "
            f"[{item_low:+.1%}, {item_high:+.1%}]; "
            f"{result['sensitivity_raw_mcnemar_p']:.4g} "
            f"| {result['sensitivity_weighted_mean_vote_error_effect']:+.1%} "
            f"[{vote_low:+.1%}, {vote_high:+.1%}] |"
        )
    diagnostics = results["corpus_diagnostics"]
    lines.extend([
        "",
        "## Script-length balance diagnostic",
        "",
        (
            "Lengths count Unicode code points in the canonical script. "
            "Frame values are unweighted means across their scripts."
        ),
        "",
        "| unit | count | minimum | mean | maximum |",
        "|---|---:|---:|---:|---:|",
        (
            f"| scripts | {diagnostics['scripts']} "
            f"| {diagnostics['script_length_chars_min']} "
            f"| {diagnostics['script_length_chars_mean']:.1f} "
            f"| {diagnostics['script_length_chars_max']} |"
        ),
        (
            f"| frame means | {diagnostics['frames']} "
            f"| {diagnostics['frame_mean_script_length_chars_min']:.1f} "
            f"| {diagnostics['frame_mean_script_length_chars_mean']:.1f} "
            f"| {diagnostics['frame_mean_script_length_chars_max']:.1f} |"
        ),
    ])
    lines.extend(["", "## Flagged clips and annotations", ""])
    for row in results["flagged_annotations"]:
        lines.append(
            f"- {row['model_tag']} / {row['item_id']}: "
            f"{row['error_votes']}/{row['valid_votes']} error votes. "
            f"{row['script']}"
        )
        for note in row["notes"]:
            lines.append(f"  - {note}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stats-json", nargs="*", type=Path, default=[])
    parser.add_argument("--eval-ids", nargs="*", default=[])
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--baseline", default="rime_coda_clementine")
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument(
        "--diagnostic-inferential",
        action="store_true",
        help=(
            "explicitly run an optional inferential diagnostic; it cannot "
            "license an AlphaBench provider claim"
        ),
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="permit fewer than four competitors for pilot diagnostics",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("out/alphabench_results"),
    )
    args = parser.parse_args()
    if not args.diagnostic_inferential:
        sys.exit(
            "AlphaBench uses scripts/analyze_alphabench_qualitative.py. "
            "Pass --diagnostic-inferential only to run an optional "
            "statistical sensitivity."
        )
    if not args.stats_json and not args.eval_ids:
        sys.exit("Pass --stats-json or --eval-ids.")

    corpus_families = load_corpus_families(args.corpus)
    corpus_subcategories = load_corpus_subcategories(args.corpus)
    corpus_diagnostics = load_corpus_diagnostics(args.corpus)
    payloads: list[tuple[str, list[dict[str, Any]]]] = []
    for path in args.stats_json:
        payloads.append(
            (str(path), json.loads(path.read_text(encoding="utf-8")))
        )
    try:
        payloads.extend(load_eval_ids(args.eval_ids))
        rows = [
            row
            for source, payload in payloads
            for row in parse_payload(
                payload,
                source=source,
                corpus_families=corpus_families,
                corpus_subcategories=corpus_subcategories,
                corpus_diagnostics=corpus_diagnostics,
                require_corpus_match=bool(args.corpus),
            )
        ]
        results = analyze(
            rows,
            baseline=args.baseline,
            n_boot=args.n_boot,
            seed=args.seed,
            subcategory_weights=(
                ALPHABENCH_SUBCATEGORY_WEIGHTS if args.corpus else None
            ),
        )
        if len(results["comparisons"]) != 4 and not args.allow_partial:
            raise ValueError(
                "The full AlphaBench diagnostic compares four competitors; "
                f"found {len(results['comparisons'])}. Pass --allow-partial "
                "only for a pilot diagnostic."
            )
    except ValueError as exc:
        sys.exit(str(exc))

    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "alphabench_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = markdown_report(results)
    (args.outdir / "alphabench_report.md").write_text(
        report,
        encoding="utf-8",
    )
    print(report)


if __name__ == "__main__":
    main()
