"""Manifest loading and upload recovery helpers for Podonos."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_VERSION = "1.0.0"
LISTENER_TASK_VERSION = "1.0.0"
ALPHABENCH_TASK_VERSION = LISTENER_TASK_VERSION
_SAFE_EVAL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def resolve_state_dir(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def validate_eval_name(eval_name: str) -> str:
    if not _SAFE_EVAL_NAME.fullmatch(eval_name):
        raise ValueError(
            "--eval-name must use only letters, numbers, periods, underscores, "
            "and hyphens, and cannot begin with punctuation."
        )
    return eval_name


def submission_state_path(state_dir: Path, eval_name: str) -> Path:
    validate_eval_name(eval_name)
    return resolve_state_dir(state_dir) / f"{eval_name}.json"


def upload_state_path(state_dir: Path, eval_name: str) -> Path:
    validate_eval_name(eval_name)
    return resolve_state_dir(state_dir) / "upload_state" / f"{eval_name}.sqlite3"


def load_submission_state(state_dir: Path, eval_name: str) -> dict[str, Any] | None:
    path = submission_state_path(state_dir, eval_name)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Submission state must contain a JSON object: {path}")
    return value


def create_or_resume_evaluator(
    client: Any,
    *,
    existing_snapshot: dict[str, Any] | None,
    ledger_path: Path,
    create_kwargs: dict[str, Any],
) -> tuple[Any, bool]:
    """Create once, or resume the recorded evaluation from its upload ledger."""
    if existing_snapshot is None:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        evaluator = client.create_evaluator_from_template_json(
            **create_kwargs,
            use_loudness_normalization=False,
            resume_upload=True,
            upload_state_path=str(ledger_path),
        )
        return evaluator, False

    if existing_snapshot.get("status") == "submitted":
        raise ValueError(
            f"Evaluation {existing_snapshot.get('evaluation_id')} is already "
            "recorded as submitted. Refusing to upload it again."
        )
    evaluation_id = existing_snapshot.get("evaluation_id")
    if not evaluation_id:
        raise ValueError(
            "Submission state exists without an evaluation ID. Stop and reconcile "
            "the evaluation name with client.get_evaluation_list() before retrying."
        )
    recorded_ledger = existing_snapshot.get("podonos", {}).get(
        "upload_state_path"
    )
    if recorded_ledger and Path(recorded_ledger).resolve() != ledger_path.resolve():
        raise ValueError("The recorded Podonos upload ledger path changed.")
    if not ledger_path.is_file():
        raise ValueError(
            f"Evaluation {evaluation_id} is recorded without a usable upload "
            "ledger. Stop and reconcile it with client.get_evaluation_list()."
        )
    evaluator = client.resume_evaluator(
        evaluation_id=evaluation_id,
        upload_state_path=str(ledger_path),
        type=create_kwargs["custom_type"],
        lan=create_kwargs["lan"],
        num_eval=create_kwargs["num_eval"],
        use_loudness_normalization=False,
        auto_start=False,
        max_upload_workers=create_kwargs["max_upload_workers"],
        verify_batch_size=create_kwargs["verify_batch_size"],
    )
    return evaluator, True


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """Read clips for upload without requiring synthesis or collection records."""
    path = path.resolve()
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"manifest must be a non-empty JSON array: {path}")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"manifest rows must be JSON objects: {path}")
        for field in ("id", "canonical_text", "model_tag", "wav_path"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"manifest row needs a non-empty {field}: {path}")
        if row["id"] in by_id:
            raise ValueError(f"duplicate manifest id {row['id']}: {path}")
        wav_path = Path(row["wav_path"])
        if not wav_path.is_absolute():
            relative = path.parent / wav_path
            wav_path = relative if relative.is_file() else wav_path
        if not wav_path.is_file():
            raise ValueError(f"missing audio for {row['id']}: {wav_path}")
        by_id[row["id"]] = {**row, "wav_path": str(wav_path.resolve())}
    if len({row["model_tag"] for row in rows}) != 1:
        raise ValueError(f"manifest mixes model_tag values: {path}")
    return by_id


def ensure_matching_pair(
    a_by_id: dict[str, dict[str, Any]],
    b_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    if set(a_by_id) != set(b_by_id):
        mismatch = sorted(set(a_by_id) ^ set(b_by_id))
        raise ValueError(f"manifest id mismatch: {mismatch}")
    ids = sorted(a_by_id)
    for item_id in ids:
        if a_by_id[item_id]["canonical_text"] != b_by_id[item_id]["canonical_text"]:
            raise ValueError(f"canonical text mismatch for {item_id}")
    return ids


def item_tags(
    row: dict[str, Any],
    campaign: str,
    *,
    task_version: str = PROTOCOL_VERSION,
) -> list[str]:
    tags = list(row.get("tags", []))
    if row.get("subcategory"):
        tags.append(f"sub_{row['subcategory']}")
    if row.get("family_id"):
        tags.append(f"family_{row['family_id']}")
    return tags + [
        f"utt_{row['id']}",
        f"campaign_{campaign}",
        f"protocol_{task_version}",
    ]


def _manifest_snapshot(path: Path) -> dict[str, Any]:
    rows = load_manifest(path)
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "audio_sha256": {
            item_id: sha256_file(Path(row["wav_path"]))
            for item_id, row in sorted(rows.items())
        },
    }


def write_submission_state(
    *,
    eval_name: str,
    benchmark: str,
    template: dict[str, Any],
    manifests: list[Path],
    num_eval: int,
    auto_start: bool,
    campaign: str,
    language: str,
    selection: dict[str, Any] | None = None,
    evaluation_id: str | None = None,
    ledger_path: Path | None = None,
    state_dir: Path = REPO_ROOT / "out" / "submissions",
    status: str = "prepared",
    task_version: str = PROTOCOL_VERSION,
) -> Path:
    """Save enough local state to resume the same upload without creating a new job."""
    state_dir = resolve_state_dir(state_dir)
    path = submission_state_path(state_dir, eval_name)
    existing = load_submission_state(state_dir, eval_name) or {}
    if existing.get("evaluation_id") and evaluation_id not in (
        None,
        existing["evaluation_id"],
    ):
        raise ValueError("Refusing to replace an existing evaluation ID.")
    inputs = {
        "benchmark": benchmark,
        "language": language,
        "num_eval": num_eval,
        "auto_start": auto_start,
        "campaign": campaign,
        "task_version": task_version,
        "template_sha256": sha256_bytes(canonical_json(template)),
        "manifests": [_manifest_snapshot(path) for path in manifests],
        "selection": selection or {},
    }
    ledger = str(ledger_path.resolve()) if ledger_path else None
    if existing:
        changed = [key for key, value in inputs.items() if existing.get(key) != value]
        if existing.get("podonos", {}).get("upload_state_path") != ledger:
            changed.append("upload_state_path")
        if changed:
            raise ValueError(
                f"Cannot resume an upload with changed inputs: {', '.join(changed)}"
            )
    snapshot = {
        **inputs,
        "evaluation_name": eval_name,
        "evaluation_id": evaluation_id or existing.get("evaluation_id"),
        "status": status,
        "created_at_utc": existing.get("created_at_utc", datetime.now(UTC).isoformat()),
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "podonos": {
            "use_loudness_normalization": False,
            "upload_state_path": ledger,
            "resume_upload": True,
        },
    }
    atomic_write_json(path, snapshot)
    return path
