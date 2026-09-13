"""Submit ContentBench five-point A/B evaluation to Podonos.

Pairs two provider manifests by corpus id and submits them as an A/B
(DOUBLE) comparison evaluation for general content narration quality.

Usage (from the repo root, after synth_demo.py):

    uv run python scripts/submit_contentbench_podonos.py \
        --manifest-a out/pilot_content/rime_coda_clementine__*/manifest.json \
        --manifest-b out/pilot_content/deepgram_aura2_thalia__*/manifest.json \
        --eval-name pilot_contentbench_rime_vs_deepgram_v3

Requires PODONOS_API_KEY in the environment.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import podonos
from podonos import File
from submission_common import (
    LISTENER_TASK_VERSION,
    create_or_resume_evaluator,
    ensure_matching_pair,
    item_tags,
    load_manifest,
    load_submission_state,
    resolve_state_dir,
    upload_state_path,
    write_submission_state,
)

CONTENTBENCH_AB_TEMPLATE = {'instructions': [{'type': 'DO',
                   'instruction': 'Wear headphones in a quiet place.',
                   'description': 'Please wear headphones for the entire session, and make '
                                  'sure you are in a quiet place where you can keep your '
                                  'attention on the audio.'},
                  {'type': 'DO',
                   'instruction': 'Listen to both clips completely before rating.',
                   'description': 'Both recordings are intended to convey the same text. Play '
                                  'each one all the way through at least once. Replaying is '
                                  'encouraged.'},
                  {'type': 'DONT',
                   'instruction': "Don't adjust the volume.",
                   'description': 'Please do not adjust the volume once it is set. Changing '
                                  'the volume level significantly affects the consistency of '
                                  'your task.'},
                  {'type': 'DONT',
                   'instruction': "Don't force a preference.",
                   'description': 'If the two clips genuinely sound equally good, use the '
                                  'middle of the scale. Forced preferences add noise.'}],
 'questions': [{'type': 'COMPARISON',
                'question': 'Which recording would you prefer for listening to this passage?',
                'description': 'Both recordings are intended to convey the same text. Imagine '
                               'listening to this passage as narration. Consider the delivery '
                               'as a whole: how easy it is to follow, how natural the speech '
                               'sounds, and how well the pacing and expression fit the '
                               'passage. Make one overall preference judgment.',
                'scale': 5,
                'related_model': 'ALL',
                'anchor_label': {'title': 'Content narration quality',
                                 'label_text': {'left': 'is much better',
                                                'right': 'is much better'}},
                'order': 0}]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest-a", dest="manifest_a", type=Path, required=True)
    p.add_argument("--manifest-b", dest="manifest_b", type=Path, required=True)
    p.add_argument(
        "--eval-name", required=True,
        help="unique evaluation name; also keys the local upload state",
    )
    p.add_argument("--description", default=(
        "ContentBench CMOS: general content narration quality comparison. "
        "Literature excerpts + YouTube-style narration."
    ))
    p.add_argument("--language", default="en-us")
    p.add_argument("--num-eval", type=int, default=7)
    p.add_argument("--campaign", default="pilot_contentbench_v3")
    p.add_argument("--auto-start", action="store_true",
                   help="start paid ratings after upload; default is a draft")
    p.add_argument("--state-dir", type=Path, default=Path("out/submissions"))
    p.add_argument("--max-upload-workers", type=int, default=4)
    p.add_argument("--verify-batch-size", type=int, default=50)
    args = p.parse_args()
    if args.num_eval < 1:
        p.error("--num-eval must be a positive integer")

    api_key = os.environ.get("PODONOS_API_KEY", "")
    if not api_key:
        sys.exit("Set PODONOS_API_KEY in the environment.")

    try:
        a_by_id = load_manifest(args.manifest_a)
        b_by_id = load_manifest(args.manifest_b)
        ids = ensure_matching_pair(a_by_id, b_by_id)
    except ValueError as exc:
        sys.exit(str(exc))
    a_tag = a_by_id[ids[0]]["model_tag"]
    b_tag = b_by_id[ids[0]]["model_tag"]
    if (a_tag.startswith("rime_")) == (b_tag.startswith("rime_")):
        sys.exit("ContentBench requires exactly one Rime manifest and one competitor manifest.")
    print(f"Pairing {len(ids)} clips: {a_tag} vs {b_tag}")

    state_dir = resolve_state_dir(args.state_dir)
    ledger_path = upload_state_path(state_dir, args.eval_name)
    existing_snapshot = load_submission_state(state_dir, args.eval_name)
    try:
        snapshot_path = write_submission_state(
            eval_name=args.eval_name,
            benchmark="contentbench",
            template=CONTENTBENCH_AB_TEMPLATE,
            task_version=LISTENER_TASK_VERSION,
            manifests=[args.manifest_a, args.manifest_b],
            num_eval=args.num_eval,
            auto_start=args.auto_start,
            campaign=args.campaign,
            language=args.language,
            ledger_path=ledger_path,
            state_dir=state_dir,
            status=(
                existing_snapshot.get("status", "prepared")
                if existing_snapshot
                else "prepared"
            ),
        )
    except ValueError as exc:
        sys.exit(str(exc))
    print(f"Upload state: {snapshot_path}")

    client = podonos.init(api_key=api_key)
    create_kwargs = {
        "json": CONTENTBENCH_AB_TEMPLATE,
        "name": args.eval_name,
        "desc": args.description,
        "custom_type": "DOUBLE",
        "lan": args.language,
        "num_eval": args.num_eval,
        "auto_start": args.auto_start,
        "max_upload_workers": args.max_upload_workers,
        "verify_batch_size": args.verify_batch_size,
    }
    try:
        evaluator, resumed = create_or_resume_evaluator(
            client,
            existing_snapshot=existing_snapshot,
            ledger_path=ledger_path,
            create_kwargs=create_kwargs,
        )
        evaluation_id = evaluator.get_evaluation_id()
        write_submission_state(
            eval_name=args.eval_name,
            benchmark="contentbench",
            template=CONTENTBENCH_AB_TEMPLATE,
            task_version=LISTENER_TASK_VERSION,
            manifests=[args.manifest_a, args.manifest_b],
            num_eval=args.num_eval,
            auto_start=args.auto_start,
            campaign=args.campaign,
            language=args.language,
            evaluation_id=evaluation_id,
            ledger_path=ledger_path,
            state_dir=state_dir,
            status="uploading",
        )
    except ValueError as exc:
        sys.exit(str(exc))
    print(f"{'Resuming' if resumed else 'Created'} evaluation id: {evaluation_id}")

    for id_ in ids:
        a, b = a_by_id[id_], b_by_id[id_]
        tags = item_tags(a, args.campaign, task_version=LISTENER_TASK_VERSION)
        evaluator.add_files(
            File(path=a["wav_path"], model_tag=a_tag, tags=tags, script=a["canonical_text"]),
            File(path=b["wav_path"], model_tag=b_tag, tags=tags, script=b["canonical_text"]),
        )
        print(f"  {id_}  {Path(a['wav_path']).name}  vs  {Path(b['wav_path']).name}")

    evaluator.close()
    print(f"\nSubmitted '{args.eval_name}': {len(ids)} pairs x {args.num_eval} raters "
          f"(auto_start={args.auto_start})")
    write_submission_state(
        eval_name=args.eval_name,
        benchmark="contentbench",
        template=CONTENTBENCH_AB_TEMPLATE,
        task_version=LISTENER_TASK_VERSION,
        manifests=[args.manifest_a, args.manifest_b],
        num_eval=args.num_eval,
        auto_start=args.auto_start,
        campaign=args.campaign,
        language=args.language,
        evaluation_id=evaluation_id,
        ledger_path=ledger_path,
        state_dir=state_dir,
        status="submitted",
    )
    print(f"Evaluation id: {evaluation_id}")


if __name__ == "__main__":
    main()
