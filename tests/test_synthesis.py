from __future__ import annotations

import math
import json
import shutil
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from synth_demo import (
    normalize_loudness,
    pcm_to_wav_bytes,
    sha256_bytes,
    wav_info,
)


class SynthesisTest(unittest.TestCase):
    def test_custom_settings_synthesize_without_registration(self) -> None:
        import synth_demo

        wav = pcm_to_wav_bytes(struct.pack("<hhhh", 0, 1, -1, 0), 24_000)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            row = json.loads((REPO_ROOT / "data/supportbench.jsonl").read_text().splitlines()[0])
            corpus = directory / "supportbench.jsonl"
            corpus.write_text(json.dumps(row) + "\n")
            args = ["synth_demo", "--corpus", str(corpus), "--providers", "rime",
                    "--rime-model", "test-model", "--rime-speaker", "test-voice",
                    "--audio-mode", "raw", "--outdir", str(directory / "audio")]
            with patch.dict("os.environ", {"RIME_API_KEY": "test"}), \
                 patch.object(sys, "argv", args), \
                 patch.object(synth_demo, "synth_rime", return_value=wav) as synth, \
                 redirect_stdout(StringIO()):
                synth_demo.main()
            synth.assert_called_once()
            self.assertEqual(synth.call_args.kwargs["model_id"], "test-model")
            self.assertEqual(synth.call_args.kwargs["speaker"], "test-voice")
            manifests = list((directory / "audio").glob("*/manifest.json"))
            self.assertEqual(len(manifests), 1)
            manifest = json.loads(manifests[0].read_text())
            self.assertEqual(Path(manifest[0]["wav_path"]).read_bytes(), wav)
            run = json.loads(manifests[0].with_name("run.json").read_text())
            self.assertEqual(run["status"], "complete")
            self.assertNotIn("registration", run["config"])

    def test_wav_metadata_and_hash_are_stable(self) -> None:
        pcm = struct.pack("<hhhh", 0, 1, -1, 0)
        wav = pcm_to_wav_bytes(pcm, 24_000)
        info = wav_info(wav)
        self.assertEqual(info["sample_rate_hz"], 24_000)
        self.assertEqual(info["channels"], 1)
        self.assertEqual(sha256_bytes(wav), sha256_bytes(wav))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_loudness_normalization_stays_linear(self) -> None:
        sample_rate = 24_000
        samples = [
            int(400 * math.sin(2 * math.pi * 440 * index / sample_rate))
            for index in range(sample_rate)
        ]
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        wav = pcm_to_wav_bytes(pcm, sample_rate)
        normalized, metadata = normalize_loudness(
            wav,
            sample_rate=sample_rate,
            target_lufs=-23.0,
            true_peak_db=-1.0,
        )
        self.assertEqual(
            metadata["second_pass"]["normalization_type"].lower(),
            "linear",
        )
        self.assertEqual(
            metadata["method"],
            "ceiling-constrained-linear-gain",
        )
        self.assertFalse(metadata["ceiling_limited"])
        self.assertEqual(wav_info(normalized)["sample_rate_hz"], sample_rate)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_loudness_normalization_respects_peak_ceiling_without_limiting(self) -> None:
        sample_rate = 24_000
        samples = [
            int(100 * math.sin(2 * math.pi * 440 * index / sample_rate))
            for index in range(sample_rate)
        ]
        samples[sample_rate // 2] = 30_000
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        wav = pcm_to_wav_bytes(pcm, sample_rate)
        normalized, metadata = normalize_loudness(
            wav,
            sample_rate=sample_rate,
            target_lufs=-23.0,
            true_peak_db=-1.0,
        )
        self.assertTrue(metadata["ceiling_limited"])
        self.assertLessEqual(float(metadata["second_pass"]["output_tp"]), -0.98)
        self.assertLessEqual(float(metadata["second_pass"]["output_i"]), -22.85)
        self.assertEqual(wav_info(normalized)["sample_rate_hz"], sample_rate)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_loudness_normalization_rejects_silence(self) -> None:
        sample_rate = 24_000
        pcm = struct.pack(f"<{sample_rate}h", *([0] * sample_rate))
        wav = pcm_to_wav_bytes(pcm, sample_rate)
        with self.assertRaisesRegex(
            RuntimeError,
            "Non-finite input loudness measurement",
        ):
            normalize_loudness(
                wav,
                sample_rate=sample_rate,
                target_lufs=-23.0,
                true_peak_db=-1.0,
            )


if __name__ == "__main__":
    unittest.main()
