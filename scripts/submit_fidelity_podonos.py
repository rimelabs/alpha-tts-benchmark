"""Submit AlphaBench whole-script reading-error evaluation to Podonos.

Each clip is evaluated on its own (custom_type=SINGLE) with two questions:

  1. NON_SCORED binary judgment on the complete canonical script.
  2. ANNOTATION text-region feedback for reading errors.

The task implements PROTOCOL.md. Usage:

    uv run python scripts/submit_fidelity_podonos.py \
        --manifests out/fidelity_pilot/*/manifest.json \
        --eval-name alphabench_five_providers

Requires PODONOS_API_KEY in the environment.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

import podonos
from podonos import File
from submission_common import (
    ALPHABENCH_TASK_VERSION,
    create_or_resume_evaluator,
    item_tags,
    load_manifest,
    load_submission_state,
    resolve_state_dir,
    upload_state_path,
    write_submission_state,
)

FIDELITY_TEMPLATE = {'instructions': [{'type': 'DO',
                   'instruction': 'Wear headphones in a quiet place.',
                   'description': 'Please wear headphones for the entire session, and make '
                                  'sure you are in a quiet place where you can keep your '
                                  'attention on the audio.'},
                  {'type': 'DO',
                   'instruction': 'Check the complete script.',
                   'description': 'Read the complete displayed script, listen to the complete '
                                  'clip, and follow along. Replay difficult words, letters, '
                                  'numbers, names, or entities before answering. In a '
                                  'spelling such as P-H-I-L-L-I-P, the hyphens are visual '
                                  'separators. The voice should say the letters, not the word '
                                  'dash.'},
                  {'type': 'DONT',
                   'instruction': "Don't judge the voice, judge the content.",
                   'description': 'Accent, pacing, pitch, and speaking style are not reading '
                                  'errors. A pause, grouped digits, or an unspoken visual '
                                  'separator is not an error when every required character is '
                                  'clear exactly once and in order. Mark missing, extra, '
                                  'wrong, repeated, reordered, truncated, or ambiguous '
                                  'content.'}],
 'questions': [{'type': 'NON_SCORED',
                'question': 'Does this recording contain a reading error compared with the '
                            'displayed script?',
                'description': 'Select Reading error if any required word, letter, number, '
                               'name, or other entity is missing, added, wrong, repeated, out '
                               'of order, cut off, or unclear. Select No reading error if all '
                               'required content is conveyed correctly and unambiguously.',
                'allow_multiple': False,
                'options': [{'label_text': 'No reading error'},
                            {'label_text': 'Reading error'}],
                'order': 0}],
 'annotations': [{'type': 'ANNOTATION',
                  'question': 'If you marked Reading error, highlight what was read '
                              'incorrectly.',
                  'description': 'Highlight the affected script region. Start the note with '
                                 'one or more labels: [OMISSION], [SUBSTITUTION], '
                                 '[INSERTION], [REPETITION], [REORDERING], [EARLY_STOP], '
                                 '[SLURRED_OR_AMBIGUOUS], or [OTHER]. Then write the expected '
                                 'and heard content. If there was no functional reading '
                                 "error, write 'none'.",
                  'order': 1}]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifests", nargs="+", required=True,
                   help="manifest.json paths or globs (each clip is submitted individually)")
    p.add_argument("--eval-name", required=True,
                   help="unique evaluation name; also keys the local upload state")
    p.add_argument("--description", default=(
        "AlphaBench whole-script reading-error evaluation under PROTOCOL.md. "
        "The complete canonical script is displayed with each provider-blind clip."
    ))
    p.add_argument("--category", default="",
                   help="optional category filter; empty submits the complete manifest")
    p.add_argument("--language", default="en-us")
    p.add_argument("--num-eval", type=int, default=3,
                   help="judgments per clip")
    p.add_argument("--campaign", default="fidelity_pilot_v1")
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

    paths = sorted({Path(m) for pattern in args.manifests for m in glob.glob(pattern)})
    if not paths:
        sys.exit(f"No manifests matched: {args.manifests}")
    rows = []
    for path in paths:
        manifest = load_manifest(path)
        for row in manifest.values():
            if not args.category or row.get("category") == args.category:
                rows.append(row)
    if not rows:
        sys.exit(f"No rows of category {args.category!r} in {len(paths)} manifests")
    rows.sort(key=lambda r: (r["model_tag"], r["id"]))
    keys = {(r["model_tag"], r["id"]) for r in rows}
    if len(keys) != len(rows):
        sys.exit("Duplicate model_tag/item pairs across manifests.")
    n_models = len({r["model_tag"] for r in rows})
    print(f"Submitting {len(rows)} clips from {n_models} model(s), {args.num_eval} raters each")

    state_dir = resolve_state_dir(args.state_dir)
    ledger_path = upload_state_path(state_dir, args.eval_name)
    existing_snapshot = load_submission_state(state_dir, args.eval_name)
    try:
        snapshot_path = write_submission_state(
            eval_name=args.eval_name,
            benchmark="alphabench",
            template=FIDELITY_TEMPLATE,
            manifests=paths,
            num_eval=args.num_eval,
            auto_start=args.auto_start,
            campaign=args.campaign,
            language=args.language,
            selection={"category": args.category},
            ledger_path=ledger_path,
            state_dir=state_dir,
            status=(
                existing_snapshot.get("status", "prepared")
                if existing_snapshot
                else "prepared"
            ),
            task_version=ALPHABENCH_TASK_VERSION,
        )
    except ValueError as exc:
        sys.exit(str(exc))
    print(f"Upload state: {snapshot_path}")

    client = podonos.init(api_key=api_key)
    create_kwargs = {
        "json": FIDELITY_TEMPLATE,
        "name": args.eval_name,
        "desc": args.description,
        "custom_type": "SINGLE",
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
            benchmark="alphabench",
            template=FIDELITY_TEMPLATE,
            manifests=paths,
            num_eval=args.num_eval,
            auto_start=args.auto_start,
            campaign=args.campaign,
            language=args.language,
            selection={"category": args.category},
            evaluation_id=evaluation_id,
            ledger_path=ledger_path,
            state_dir=state_dir,
            status="uploading",
            task_version=ALPHABENCH_TASK_VERSION,
        )
    except ValueError as exc:
        sys.exit(str(exc))
    print(f"{'Resuming' if resumed else 'Created'} evaluation id: {evaluation_id}")

    for r in rows:
        tags = item_tags(
            r,
            args.campaign,
            task_version=ALPHABENCH_TASK_VERSION,
        )
        evaluator.add_file(File(
            path=r["wav_path"],
            model_tag=r["model_tag"],
            tags=tags,
            script=r["canonical_text"],
        ))
        print(f"  {r['model_tag']}  {r['id']}  {r['canonical_text'][:60]}")

    evaluator.close()
    print(f"\nSubmitted '{args.eval_name}': {len(rows)} clips x {args.num_eval} raters "
          f"(auto_start={args.auto_start})")
    write_submission_state(
        eval_name=args.eval_name,
        benchmark="alphabench",
        template=FIDELITY_TEMPLATE,
        manifests=paths,
        num_eval=args.num_eval,
        auto_start=args.auto_start,
        campaign=args.campaign,
        language=args.language,
        selection={"category": args.category},
        evaluation_id=evaluation_id,
        ledger_path=ledger_path,
        state_dir=state_dir,
        status="submitted",
        task_version=ALPHABENCH_TASK_VERSION,
    )
    print(f"Evaluation id: {evaluation_id}")


if __name__ == "__main__":
    main()
