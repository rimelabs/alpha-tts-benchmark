from __future__ import annotations

import json
import struct
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from submission_common import (
    create_or_resume_evaluator,
    ensure_matching_pair,
    load_manifest,
    load_submission_state,
    upload_state_path,
    write_submission_state,
)
from synth_demo import pcm_to_wav_bytes, recover_or_reuse_wav


class ListenerTaskTest(unittest.TestCase):
    def test_submitted_templates_match_tasks_and_protocol(self) -> None:
        from submit_fidelity_podonos import FIDELITY_TEMPLATE
        from submit_supportbench_podonos import CMOS_AB_TEMPLATE
        from submit_contentbench_podonos import CONTENTBENCH_AB_TEMPLATE
        from submission_common import LISTENER_TASK_VERSION, ALPHABENCH_TASK_VERSION

        registration = json.loads(
            (REPO_ROOT / "configs/listener_tasks.json").read_text()
        )
        protocol = (REPO_ROOT / "PROTOCOL.md").read_text()
        self.assertEqual(registration["task_version"], LISTENER_TASK_VERSION)
        self.assertEqual(ALPHABENCH_TASK_VERSION, LISTENER_TASK_VERSION)
        for benchmark, template in {
            "AlphaBench": FIDELITY_TEMPLATE,
            "SupportBench": CMOS_AB_TEMPLATE,
            "ContentBench": CONTENTBENCH_AB_TEMPLATE,
        }.items():
            with self.subTest(benchmark=benchmark):
                self.assertEqual(registration["templates"][benchmark], template)
                question = template["questions"][0]
                self.assertIn(question["question"], protocol)
                self.assertIn(question["description"], protocol)
                if benchmark != "AlphaBench":
                    self.assertEqual(question["scale"], 5)
                    self.assertEqual(len(template["instructions"]), 4)
                    self.assertNotIn("Penalize reading errors", json.dumps(template))


class FakeEvaluator:
    def __init__(self) -> None:
        self.files = []
        self.closed = False

    def get_evaluation_id(self):
        return "evaluation-123"

    def add_file(self, file):
        self.files.append(file)

    def add_files(self, *files):
        self.files.extend(files)

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self) -> None:
        self.created: dict | None = None
        self.resumed: dict | None = None
        self.evaluator = FakeEvaluator()

    def create_evaluator_from_template_json(self, **kwargs):
        self.created = kwargs
        return self.evaluator

    def resume_evaluator(self, **kwargs):
        self.resumed = kwargs
        return self.evaluator


class SubmissionRecoveryTest(unittest.TestCase):
    def test_new_evaluation_disables_processing_and_records_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "upload.sqlite3"
            client = FakeClient()
            evaluator, resumed = create_or_resume_evaluator(
                client,
                existing_snapshot=None,
                ledger_path=ledger,
                create_kwargs={
                    "custom_type": "DOUBLE",
                    "lan": "en-us",
                    "num_eval": 7,
                    "max_upload_workers": 4,
                    "verify_batch_size": 50,
                },
            )
            self.assertIs(evaluator, client.evaluator)
            self.assertFalse(resumed)
            self.assertEqual(client.created["upload_state_path"], str(ledger))
            self.assertTrue(client.created["resume_upload"])
            self.assertFalse(client.created["use_loudness_normalization"])

    def test_interrupted_evaluation_resumes_same_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "upload.sqlite3"
            ledger.write_bytes(b"ledger")
            client = FakeClient()
            snapshot = {
                "status": "uploading",
                "evaluation_id": "evaluation-123",
                "podonos": {"upload_state_path": str(ledger)},
            }
            evaluator, resumed = create_or_resume_evaluator(
                client,
                existing_snapshot=snapshot,
                ledger_path=ledger,
                create_kwargs={
                    "custom_type": "DOUBLE",
                    "lan": "en-us",
                    "num_eval": 7,
                    "max_upload_workers": 4,
                    "verify_batch_size": 50,
                },
            )
            self.assertIs(evaluator, client.evaluator)
            self.assertTrue(resumed)
            self.assertEqual(client.resumed["evaluation_id"], "evaluation-123")
            self.assertEqual(client.resumed["type"], "DOUBLE")
            self.assertEqual(client.resumed["num_eval"], 7)
            self.assertIsNone(client.created)
            self.assertFalse(client.resumed["use_loudness_normalization"])

    def test_recorded_evaluation_without_ledger_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "missing.sqlite3"
            with self.assertRaisesRegex(ValueError, "without a usable upload ledger"):
                create_or_resume_evaluator(
                    FakeClient(),
                    existing_snapshot={
                        "status": "uploading",
                        "evaluation_id": "evaluation-123",
                        "podonos": {"upload_state_path": str(ledger)},
                    },
                    ledger_path=ledger,
                    create_kwargs={
                        "max_upload_workers": 4,
                        "verify_batch_size": 50,
                    },
                )

    def test_orphaned_wav_is_removed_before_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "orphan.wav"
            wav_path.write_bytes(b"orphan")
            reusable = recover_or_reuse_wav(
                wav_path,
                None,
                reuse_verified=True,
            )
            self.assertFalse(reusable)
            self.assertFalse(wav_path.exists())


def write_manifest(directory: Path, model_tag: str = "rime_coda_clementine") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    wav_path = directory / "item.wav"
    wav_path.write_bytes(pcm_to_wav_bytes(struct.pack("<hhhh", 0, 1, -1, 0), 24_000))
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps([{
        "id": "item-1",
        "canonical_text": "Test.",
        "wav_path": "item.wav",
        "model_tag": model_tag,
    }]), encoding="utf-8")
    return manifest_path


class ManifestValidationTest(unittest.TestCase):
    def test_manifest_loads_without_generation_or_collection_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = write_manifest(directory)
            row = load_manifest(path)["item-1"]
            self.assertEqual(row["wav_path"], str((directory / "item.wav").resolve()))
            self.assertFalse((directory / "run.json").exists())
            # Historical metadata does not certify or prevent an upload.
            rows = json.loads(path.read_text())
            rows[0].update({
                "protocol_version": "earlier-task",
                "audio_processing": {"mode": "raw"},
            })
            path.write_text(json.dumps(rows))
            self.assertEqual(load_manifest(path)["item-1"]["canonical_text"], "Test.")

    def test_missing_audio_and_duplicate_ids_still_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manifest(Path(tmp))
            rows = json.loads(path.read_text())
            path.write_text(json.dumps(rows + rows))
            with self.assertRaisesRegex(ValueError, "duplicate manifest id"):
                load_manifest(path)
            path.write_text(json.dumps(rows))
            path.with_name("item.wav").unlink()
            with self.assertRaisesRegex(ValueError, "missing audio"):
                load_manifest(path)

    def test_pairing_uses_item_ids_and_spoken_content(self) -> None:
        a = {"id": "item-1", "canonical_text": "Test.", "protocol_version": "old"}
        b = {"id": "item-1", "canonical_text": "Test."}
        self.assertEqual(ensure_matching_pair({"item-1": a}, {"item-1": b}), ["item-1"])
        b["canonical_text"] = "Different."
        with self.assertRaisesRegex(ValueError, "canonical text mismatch"):
            ensure_matching_pair({"item-1": a}, {"item-1": b})
        with self.assertRaisesRegex(ValueError, "manifest id mismatch"):
            ensure_matching_pair({"item-1": a}, {"item-2": b})

    def test_resume_rejects_changed_audio_without_a_provenance_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest = write_manifest(directory)
            state_dir = directory / "state"
            kwargs = dict(
                eval_name="example", benchmark="alphabench", template={"questions": []},
                manifests=[manifest], num_eval=2, auto_start=False,
                campaign="test", language="en-us", state_dir=state_dir,
                ledger_path=upload_state_path(state_dir, "example"),
            )
            write_submission_state(**kwargs)
            write_submission_state(**kwargs, evaluation_id="evaluation-123", status="uploading")
            state = load_submission_state(state_dir, "example")
            self.assertEqual(state["evaluation_id"], "evaluation-123")
            self.assertNotIn("approvals", state)
            self.assertNotIn("budget_authorization", state)
            with self.assertRaisesRegex(ValueError, "changed inputs: selection"):
                write_submission_state(**kwargs, selection={"category": "different"})
            manifest.with_name("item.wav").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed inputs: manifests"):
                write_submission_state(**kwargs)


class SubmissionCommandTest(unittest.TestCase):
    def test_all_benchmarks_submit_minimal_manifests_without_staged_plans(self) -> None:
        import submit_contentbench_podonos as content
        import submit_fidelity_podonos as alpha
        import submit_supportbench_podonos as support

        for module in (alpha, support, content):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                a = write_manifest(directory / "a")
                b = write_manifest(directory / "b", model_tag="other_voice")
                args = [module.__name__, "--eval-name", "example", "--num-eval", "2",
                        "--auto-start", "--state-dir", str(directory / "state")]
                if module is alpha:
                    args += ["--manifests", str(a)]
                else:
                    args += ["--manifest-a", str(a), "--manifest-b", str(b)]
                client = FakeClient()
                with patch.dict("os.environ", {"PODONOS_API_KEY": "test"}), \
                     patch.object(module.podonos, "init", return_value=client), \
                     patch.object(sys, "argv", args), redirect_stdout(StringIO()):
                    module.main()
                self.assertEqual(client.created["num_eval"], 2)
                self.assertTrue(client.created["auto_start"])
                self.assertTrue(client.evaluator.closed)
                self.assertEqual(len(client.evaluator.files), 1 if module is alpha else 2)
                state = load_submission_state(directory / "state", "example")
                self.assertEqual(state["status"], "submitted")
                self.assertEqual(state["evaluation_id"], "evaluation-123")


if __name__ == "__main__":
    unittest.main()
