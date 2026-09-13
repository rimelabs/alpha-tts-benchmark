"""Build a qualitative AlphaBench failure report without winner statistics.

The report preserves listener vote counts as evidence strength, groups the
structured annotation labels, and prints the underlying clips and notes for
human review. It does not calculate confidence intervals, hypothesis tests,
provider rankings, or directional claims.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from analyze_fidelity import (
    ERROR_LABELS,
    PASS_LABELS,
    load_corpus_diagnostics,
    load_corpus_families,
    load_corpus_subcategories,
    load_eval_ids,
    parse_payload,
)


FAILURE_LABELS = (
    "OMISSION",
    "SUBSTITUTION",
    "INSERTION",
    "REPETITION",
    "REORDERING",
    "EARLY_STOP",
    "SLURRED_OR_AMBIGUOUS",
    "OTHER",
)
FAILURE_INTERPRETATION = {
    "OMISSION": (
        "functional failure",
        "Required content is missing. One missing identifier character can "
        "change the destination or record.",
    ),
    "SUBSTITUTION": (
        "functional failure",
        "Required content was replaced with different content.",
    ),
    "INSERTION": (
        "functional failure",
        "The clip added content that the canonical script did not contain.",
    ),
    "REPETITION": (
        "functional failure",
        "Required content was spoken more than once.",
    ),
    "REORDERING": (
        "functional failure",
        "The right characters appeared in the wrong order.",
    ),
    "EARLY_STOP": (
        "functional failure",
        "The audio ended before the sentence or identifier was complete.",
    ),
    "SLURRED_OR_AMBIGUOUS": (
        "functional failure",
        "Required content cannot be identified confidently by the listener.",
    ),
    "OTHER": (
        "manual review",
        "The note does not fit a failure type. Review the clip "
        "before treating it as model evidence.",
    ),
}
LABEL_PATTERN = re.compile(
    r"\[(" + "|".join(FAILURE_LABELS) + r")\]",
    re.IGNORECASE,
)
VISUAL_SEPARATOR_PATTERN = re.compile(r"\b[A-Z](?:-[A-Z]){2,}\b")


def _annotation_text(annotation: dict[str, Any]) -> str:
    return str(
        annotation.get("reason")
        or annotation.get("content")
        or ""
    ).strip()


def aggregate_individual_export(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Podonos individual responses into the aggregate parser shape."""
    notes_by_target: dict[tuple[str, str], list[str]] = defaultdict(list)
    for annotation in payload.get("annotation_records", []):
        target = annotation.get("target", {})
        path = str(target.get("path", ""))
        model_tag = str(target.get("model_tag", ""))
        note = _annotation_text(annotation)
        if path and model_tag and note:
            notes_by_target[(model_tag, path)].append(note)

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for record in payload.get("records", []):
        targets = record.get("targets", [])
        if len(targets) != 1:
            raise ValueError("AlphaBench individual responses need one target")
        target = targets[0]
        path = str(target["path"])
        model_tag = str(target["model_tag"])
        key = (model_tag, path)
        row = grouped.setdefault(
            key,
            {
                "path": path,
                "model_tag": model_tag,
                "tags": list(target.get("script_tags", [])),
                "script": target.get("script", ""),
                **{label: 0 for label in ERROR_LABELS + PASS_LABELS},
                "annotations": [],
            },
        )
        for label in record.get("response", []):
            if label in row:
                row[label] += 1

    for key, notes in notes_by_target.items():
        if key in grouped:
            grouped[key]["annotations"] = [
                {"reason": note} for note in notes
            ]
    return [{"responses": list(grouped.values())}]


def parse_source(
    payload: Any,
    *,
    source: str,
    corpus_families: dict[str, str],
    corpus_subcategories: dict[str, str],
    corpus_diagnostics: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and "records" in payload:
        payload = aggregate_individual_export(payload)
    if not isinstance(payload, list):
        raise ValueError(f"{source} is not a supported Podonos export")
    if any(isinstance(block, dict) and "model" in block for block in payload):
        payload = flatten_model_export(payload)
    return parse_payload(
        payload,
        source=source,
        corpus_families=corpus_families,
        corpus_subcategories=corpus_subcategories,
        corpus_diagnostics=corpus_diagnostics,
        require_corpus_match=bool(corpus_families),
    )


def flatten_model_export(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Read model-grouped votes and their annotation reasons once per clip."""
    clips: dict[tuple[str, str], dict[str, Any]] = {}
    for block in payload:
        model = block.get("model")
        if not model:
            continue
        for question in block.get("responses", []):
            for response in question.get("responses", []):
                if response.get("model_tag") != model:
                    raise ValueError("AlphaBench model block and clip disagree")
                key = (model, response["path"])
                if key in clips:
                    raise ValueError(f"duplicate AlphaBench model clip: {key}")
                clips[key] = dict(response)

    for block in payload:
        if block.get("type") != "annotation" or block.get("model"):
            continue
        for response in block.get("responses", []):
            key = (response["model_tag"], response["path"])
            if key not in clips:
                raise ValueError(f"annotation has no AlphaBench votes: {key}")
            annotations = response.get("annotations", [])
            existing = clips[key].get("annotations", [])
            if existing and annotations:
                canonical = lambda rows: Counter(
                    json.dumps(row, sort_keys=True) for row in rows
                )
                if canonical(existing) != canonical(annotations):
                    raise ValueError(f"conflicting AlphaBench annotations: {key}")
            elif annotations:
                clips[key]["annotations"] = annotations

    for clip in clips.values():
        # In this export, content is highlighted script text. The review note
        # is reason; missing reasons must not become apparent listener notes.
        clip["annotations"] = [
            annotation
            for annotation in clip.get("annotations", [])
            if str(annotation.get("reason") or "").strip()
        ]
    return [{"responses": list(clips.values())}]


def annotation_labels(notes: list[str]) -> list[str]:
    return sorted({
        match.group(1).upper()
        for note in notes
        for match in LABEL_PATTERN.finditer(note)
    })


def review_flags(script: str, notes: list[str]) -> list[str]:
    flags: set[str] = set()
    has_visual_separators = bool(VISUAL_SEPARATOR_PATTERN.search(script))
    for note in notes:
        normalized = note.lower()
        if "dash" not in normalized:
            continue
        negated = any(phrase in normalized for phrase in (
            "not mention",
            "not pronounced",
            "no dash",
            "no dashes",
            "did not mention",
            "didn't mention",
            "did not include",
            "not include",
            "was not pronounced",
            "were not pronounced",
            "without dash",
        ))
        if has_visual_separators and negated:
            flags.add("VISUAL_SEPARATOR_FALSE_POSITIVE")
        elif not negated:
            flags.add("SPOKEN_DASH_REVIEW")
    return sorted(flags)


def analyze_qualitative(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["model_tag"], row["item_id"])
        if key in seen:
            raise ValueError(
                f"duplicate item {row['item_id']} for {row['model_tag']}"
            )
        seen.add(key)
        labels = annotation_labels(row["notes"])
        flags = review_flags(row["script"], row["notes"])
        enriched = dict(row)
        enriched["failure_labels"] = labels
        enriched["review_flags"] = flags
        enriched["valid_votes"] = row["error_votes"] + row["pass_votes"]
        enriched["unanimous_error"] = (
            enriched["valid_votes"] > 0
            and row["error_votes"] == enriched["valid_votes"]
        )
        by_model[row["model_tag"]].append(enriched)

    providers: dict[str, Any] = {}
    evidence: list[dict[str, Any]] = []
    for model_tag, model_rows in sorted(by_model.items()):
        label_counts = {
            label: sum(
                label in row["failure_labels"] for row in model_rows
            )
            for label in FAILURE_LABELS
        }
        flag_counts = {
            flag: sum(flag in row["review_flags"] for row in model_rows)
            for flag in (
                "VISUAL_SEPARATOR_FALSE_POSITIVE",
                "SPOKEN_DASH_REVIEW",
            )
        }
        providers[model_tag] = {
            "clips_reviewed": len(model_rows),
            "valid_listener_votes": sum(
                row["valid_votes"] for row in model_rows
            ),
            "listener_error_votes": sum(
                row["error_votes"] for row in model_rows
            ),
            "clips_flagged_by_any_listener": sum(
                row["error_votes"] > 0 for row in model_rows
            ),
            "clips_flagged_by_listener_majority": sum(
                row["majority_error"] for row in model_rows
            ),
            "clips_flagged_unanimously": sum(
                row["unanimous_error"] for row in model_rows
            ),
            "failure_label_clip_counts": label_counts,
            "review_flag_clip_counts": flag_counts,
            "flagged_clips_without_structured_label": sum(
                row["error_votes"] > 0 and not row["failure_labels"]
                for row in model_rows
            ),
        }
        for row in model_rows:
            if row["error_votes"] == 0 and not row["notes"]:
                continue
            evidence.append({
                "model_tag": model_tag,
                "item_id": row["item_id"],
                "subcategory": row["subcategory"],
                "script": row["script"],
                "error_votes": row["error_votes"],
                "valid_votes": row["valid_votes"],
                "listener_consensus": (
                    "unanimous"
                    if row["unanimous_error"]
                    else "majority"
                    if row["majority_error"]
                    else "single-listener-or-split"
                ),
                "failure_labels": row["failure_labels"],
                "review_flags": row["review_flags"],
                "notes": row["notes"],
                "source": row["source"],
            })

    evidence.sort(
        key=lambda row: (
            row["model_tag"],
            -row["error_votes"],
            row["item_id"],
        )
    )
    return {
        "analysis_type": "qualitative_failure_review",
        "inferential_provider_claims_allowed": False,
        "interpretation": (
            "Vote counts show listener support for reviewing a clip. They are "
            "not hypothesis tests, confidence intervals, provider rankings, "
            "or winner claims."
        ),
        "failure_labels": list(FAILURE_LABELS),
        "failure_interpretation": {
            label: {
                "disposition": disposition,
                "reason": reason,
            }
            for label, (disposition, reason) in FAILURE_INTERPRETATION.items()
        },
        "not_functional_failures": [
            "accent",
            "pacing",
            "pitch",
            "voice quality",
            "pauses",
            "digit grouping when every digit remains clear and in order",
            "unspoken visual separator hyphens in spelled names",
        ],
        "providers": providers,
        "evidence_clips": evidence,
    }


def markdown_report(results: dict[str, Any]) -> str:
    lines = [
        "# AlphaBench qualitative failure report",
        "",
        results["interpretation"],
        "",
        "## How functional impact is judged",
        "",
        (
            "AlphaBench treats any missing, wrong, extra, repeated, "
            "reordered, truncated, or persistently ambiguous identifier "
            "character as a functional failure. It does not grade how the "
            "voice sounds."
        ),
        "",
        "| label | disposition | reason |",
        "|---|---|---|",
    ]
    for label in FAILURE_LABELS:
        interpretation = results["failure_interpretation"][label]
        lines.append(
            f"| {label} | {interpretation['disposition']} "
            f"| {interpretation['reason']} |"
        )
    lines.extend([
        "",
        (
            "Accent, pacing, pitch, pauses, grouping, voice quality, and "
            "unspoken visual separators are not functional failures when "
            "the required content remains clear exactly once and in order."
        ),
        "",
        "## Listener flags for evidence review",
        "",
        (
            "These counts help reviewers find repeated failure patterns. "
            "They do not rank providers."
        ),
        "",
        "| model | clips | valid votes | error votes | any flag | majority flag | unanimous flag | unlabelled flagged clips |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for model_tag, provider in sorted(results["providers"].items()):
        lines.append(
            f"| {model_tag} | {provider['clips_reviewed']} "
            f"| {provider['valid_listener_votes']} "
            f"| {provider['listener_error_votes']} "
            f"| {provider['clips_flagged_by_any_listener']} "
            f"| {provider['clips_flagged_by_listener_majority']} "
            f"| {provider['clips_flagged_unanimously']} "
            f"| {provider['flagged_clips_without_structured_label']} |"
        )

    lines.extend([
        "",
        "## Labelled failure patterns",
        "",
        (
            "Counts are clips with at least one matching annotation label. "
            "A clip can appear under more than one label."
        ),
        "",
        "| model | omission | substitution | insertion | repetition | reordering | early stop | slurred or ambiguous | other |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for model_tag, provider in sorted(results["providers"].items()):
        counts = provider["failure_label_clip_counts"]
        lines.append(
            f"| {model_tag} | {counts['OMISSION']} "
            f"| {counts['SUBSTITUTION']} | {counts['INSERTION']} "
            f"| {counts['REPETITION']} | {counts['REORDERING']} "
            f"| {counts['EARLY_STOP']} "
            f"| {counts['SLURRED_OR_AMBIGUOUS']} | {counts['OTHER']} |"
        )

    lines.extend([
        "",
        "## Task and input review flags",
        "",
        "| model | unspoken visual separator false positives | spoken dash reviews |",
        "|---|---:|---:|",
    ])
    for model_tag, provider in sorted(results["providers"].items()):
        flags = provider["review_flag_clip_counts"]
        lines.append(
            f"| {model_tag} "
            f"| {flags['VISUAL_SEPARATOR_FALSE_POSITIVE']} "
            f"| {flags['SPOKEN_DASH_REVIEW']} |"
        )

    lines.extend(["", "## Clip evidence", ""])
    for row in results["evidence_clips"]:
        labels = ", ".join(row["failure_labels"]) or "unlabelled"
        flags = ", ".join(row["review_flags"])
        flag_text = f" Review: {flags}." if flags else ""
        lines.append(
            f"- {row['model_tag']} / {row['item_id']} / "
            f"{row['subcategory']}: {row['error_votes']}/"
            f"{row['valid_votes']} error votes, {row['listener_consensus']}. "
            f"Labels: {labels}.{flag_text} Script: {row['script']}"
        )
        for note in row["notes"]:
            lines.append(f"  - {note}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stats-json", nargs="*", type=Path, default=[])
    parser.add_argument("--eval-ids", nargs="*", default=[])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("out/alphabench_qualitative"),
    )
    args = parser.parse_args()
    if not args.stats_json and not args.eval_ids:
        sys.exit("Pass --stats-json or --eval-ids.")

    corpus_families = load_corpus_families(args.corpus)
    corpus_subcategories = load_corpus_subcategories(args.corpus)
    corpus_diagnostics = load_corpus_diagnostics(args.corpus)
    payloads: list[tuple[str, Any]] = [
        (str(path), json.loads(path.read_text(encoding="utf-8")))
        for path in args.stats_json
    ]
    try:
        payloads.extend(load_eval_ids(args.eval_ids))
        rows = [
            row
            for source, payload in payloads
            for row in parse_source(
                payload,
                source=source,
                corpus_families=corpus_families,
                corpus_subcategories=corpus_subcategories,
                corpus_diagnostics=corpus_diagnostics,
            )
        ]
        results = analyze_qualitative(rows)
    except ValueError as exc:
        sys.exit(str(exc))

    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "alphabench_qualitative.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = markdown_report(results)
    (args.outdir / "alphabench_qualitative.md").write_text(
        report,
        encoding="utf-8",
    )
    print(report)


if __name__ == "__main__":
    main()
