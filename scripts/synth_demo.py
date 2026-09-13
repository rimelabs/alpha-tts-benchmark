"""Synthesize corpus audio with provider-conditioned input.

Reads a corpus manifest (default data/supportbench.jsonl), renders
provider-conditioned input per PROTOCOL.md via corpus/render.py,
synthesizes at 24kHz mono 16-bit WAV, and writes per-provider manifests
for the scripts/submit_*_podonos.py submission scripts.

Usage (from the repo root):

    uv run python scripts/synth_demo.py --corpus data/pilot_alphabench.jsonl \
        --providers rime --rime-speaker clementine --outdir out/pilot_alpha

Requires the selected provider's API key in the environment
(RIME_API_KEY, ELEVENLABS_API_KEY, DEEPGRAM_API_KEY, CARTESIA_API_KEY,
OPENAI_API_KEY, or GEMINI_API_KEY).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from corpus.render import render_text
from scripts.submission_common import (
    PROTOCOL_VERSION,
    atomic_write_json,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

RIME_TTS_URL = "https://users.rime.ai/v1/rime-tts"
ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVEN_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
GOOGLE_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"
CARTESIA_TTS_URL = "https://api.cartesia.ai/tts/bytes"
CARTESIA_API_VERSION = "2026-03-01"
OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO_ROOT / "data" / "supportbench.jsonl"

# --limit subset quotas mirror the supportbench stratification (rows / 20).
DEMO_SHARE = {
    "support_dialogue": 18,
    "dates_times": 6,
    "phone_numbers": 5,
    "amounts_units": 4,
    "addresses_contact": 3,
    "short_responses": 2,
}

RETRYABLE = (429, 500, 502, 503, 504)
_CURRENT_ATTEMPTS: list[dict[str, Any]] | None = None


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def atomic_write_bytes(path: Path, value: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


def recover_or_reuse_wav(
    wav_path: Path,
    previous: dict[str, Any] | None,
    *,
    reuse_verified: bool,
) -> bool:
    """Return True for a reusable row; remove an orphaned WAV on resume."""
    if not wav_path.exists():
        return False
    if not reuse_verified:
        raise ValueError(
            f"{wav_path} already exists. Refusing silent reuse. Pass "
            "--reuse-verified to continue with matching existing audio."
        )
    if previous is None:
        wav_path.unlink()
        return False
    return True


def write_synthesis_checkpoint(
    *,
    manifest_path: Path,
    run_path: Path,
    manifest: list[dict[str, Any]],
    run_record: dict[str, Any],
    status: str,
) -> None:
    atomic_write_json(manifest_path, manifest)
    run_record["status"] = status
    run_record["items_completed"] = len(manifest)
    run_record["manifest_sha256"] = sha256_file(manifest_path)
    run_record["updated_at_utc"] = datetime.now(UTC).isoformat()
    atomic_write_json(run_path, run_record)


def ffmpeg_version() -> str:
    result = subprocess.run(
        ["ffmpeg", "-version"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()[0]


def wav_info(value: bytes) -> dict[str, int | float]:
    with wave.open(io.BytesIO(value), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.getnframes()
    if channels != 1 or sample_width != 2:
        raise RuntimeError(
            f"Expected mono 16-bit WAV, got channels={channels}, "
            f"sample_width={sample_width}"
        )
    return {
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate_hz": sample_rate,
        "frames": frames,
        "duration_seconds": frames / sample_rate,
    }


def _loudnorm_json(stderr: str) -> dict[str, str]:
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError(f"ffmpeg loudnorm returned no JSON: {stderr[-1000:]}")
    return json.loads(stderr[start : end + 1])


def _measure_loudness(
    wav_path: Path,
    *,
    target_lufs: float,
    true_peak_db: float,
) -> dict[str, str]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(wav_path),
        "-af",
        f"loudnorm=I={target_lufs}:TP={true_peak_db}:LRA=7:print_format=json",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return _loudnorm_json(result.stderr)


def normalize_loudness(
    wav_bytes: bytes,
    *,
    sample_rate: int,
    target_lufs: float,
    true_peak_db: float,
) -> tuple[bytes, dict[str, Any]]:
    """Apply deterministic linear gain, constrained by the true-peak ceiling."""
    with tempfile.TemporaryDirectory(prefix="rime-benchmark-loudness-") as tmp:
        source = Path(tmp) / "source.wav"
        target = Path(tmp) / "target.wav"
        source.write_bytes(wav_bytes)
        measured = _measure_loudness(
            source,
            target_lufs=target_lufs,
            true_peak_db=true_peak_db,
        )
        required = {
            "input_i",
            "input_tp",
            "input_lra",
            "input_thresh",
            "target_offset",
        }
        if required - set(measured):
            raise RuntimeError(f"Incomplete loudness measurement: {measured}")
        input_lufs = float(measured["input_i"])
        input_true_peak = float(measured["input_tp"])
        if not math.isfinite(input_lufs) or not math.isfinite(input_true_peak):
            raise RuntimeError(
                "Non-finite input loudness measurement: "
                f"input_i={measured['input_i']}, input_tp={measured['input_tp']}"
            )
        loudness_safety_margin_db = 0.02
        calibrated_target_lufs = target_lufs - loudness_safety_margin_db
        requested_gain_db = calibrated_target_lufs - input_lufs
        peak_safety_margin_db = 0.05
        ceiling_gain_db = true_peak_db - input_true_peak - peak_safety_margin_db
        applied_gain_db = min(requested_gain_db, ceiling_gain_db)
        ceiling_limited = applied_gain_db < requested_gain_db - 1e-9
        calibration_steps: list[dict[str, Any]] = []
        command: list[str] = []
        output: dict[str, str] = {}
        output_lufs = float("nan")
        output_true_peak = float("nan")
        for attempt in range(1, 5):
            filter_value = f"volume={applied_gain_db:.6f}dB"
            command = [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-y",
                "-i",
                str(source),
                "-af",
                filter_value,
                "-ar",
                str(sample_rate),
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(target),
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            output = _measure_loudness(
                target,
                target_lufs=target_lufs,
                true_peak_db=true_peak_db,
            )
            output_lufs = float(output["input_i"])
            output_true_peak = float(output["input_tp"])
            if not math.isfinite(output_lufs) or not math.isfinite(output_true_peak):
                raise RuntimeError(
                    "Non-finite output loudness measurement: "
                    f"input_i={output['input_i']}, input_tp={output['input_tp']}"
                )
            calibration_steps.append(
                {
                    "attempt": attempt,
                    "gain_db": applied_gain_db,
                    "output_lufs": output_lufs,
                    "output_true_peak_db": output_true_peak,
                }
            )
            peak_ok = output_true_peak <= true_peak_db + 0.02
            if ceiling_limited:
                if peak_ok and output_lufs <= target_lufs + 0.02:
                    break
            elif peak_ok and abs(output_lufs - calibrated_target_lufs) <= 0.05:
                break
            corrected_gain_db = applied_gain_db + (
                calibrated_target_lufs - output_lufs
            )
            if output_true_peak > true_peak_db:
                corrected_gain_db -= output_true_peak - true_peak_db
            applied_gain_db = min(corrected_gain_db, ceiling_gain_db)
            ceiling_limited = applied_gain_db >= ceiling_gain_db - 1e-9
        measurement_tolerance_db = 0.02
        loudness_tolerance_db = 0.15
        if output_true_peak > true_peak_db + measurement_tolerance_db:
            raise RuntimeError(
                f"Linear gain exceeded the true-peak ceiling: {output_true_peak} dBTP"
            )
        if output_lufs > target_lufs + loudness_tolerance_db:
            raise RuntimeError(
                f"Linear gain exceeded the loudness target: {output_lufs} LUFS"
            )
        if not ceiling_limited and abs(
            output_lufs - calibrated_target_lufs
        ) > loudness_tolerance_db:
            raise RuntimeError(
                "Linear gain missed the loudness target without the peak ceiling binding: "
                f"{output_lufs} LUFS"
            )
        final_bytes = target.read_bytes()
        wav_info(final_bytes)
        return final_bytes, {
            "mode": "level-matched",
            "method": "ceiling-constrained-linear-gain",
            "target_lufs": target_lufs,
            "true_peak_ceiling_db": true_peak_db,
            "requested_gain_db": requested_gain_db,
            "ceiling_gain_db": ceiling_gain_db,
            "peak_safety_margin_db": peak_safety_margin_db,
            "loudness_safety_margin_db": loudness_safety_margin_db,
            "applied_gain_db": applied_gain_db,
            "ceiling_limited": ceiling_limited,
            "calibration_steps": calibration_steps,
            "first_pass": measured,
            "second_pass": {
                "normalization_type": "linear",
                "output_i": output["input_i"],
                "output_tp": output["input_tp"],
                "output_lra": output["input_lra"],
                "output_thresh": output["input_thresh"],
            },
            "ffmpeg_command": command,
        }


def pcm_to_wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _post_with_retries(request_fn, retries: int = 3) -> httpx.Response:
    for attempt in range(1, retries + 1):
        record: dict[str, Any] = {
            "attempt": attempt,
            "started_at_utc": datetime.now(UTC).isoformat(),
        }
        try:
            r = request_fn()
            r.raise_for_status()
            record.update({
                "outcome": "transport_success",
                "http_status": r.status_code,
                "response_id": (
                    r.headers.get("x-request-id")
                    or r.headers.get("request-id")
                    or r.headers.get("dg-request-id")
                ),
                "retained": False,
            })
            if _CURRENT_ATTEMPTS is not None:
                _CURRENT_ATTEMPTS.append(record)
            return r
        except httpx.HTTPStatusError as e:
            record.update({
                "outcome": "http_error",
                "http_status": e.response.status_code,
                "response_id": (
                    e.response.headers.get("x-request-id")
                    or e.response.headers.get("request-id")
                    or e.response.headers.get("dg-request-id")
                ),
                "error": str(e),
                "retained": False,
            })
            if _CURRENT_ATTEMPTS is not None:
                _CURRENT_ATTEMPTS.append(record)
            if e.response.status_code in RETRYABLE and attempt < retries:
                # Rate limits (429) need much longer waits than transient 5xx —
                # e.g. Gemini free tier suggests ~60s.
                wait = max(2**attempt, 45) if e.response.status_code == 429 else 2**attempt
                log.warning("HTTP %d, retrying in %ds …", e.response.status_code, wait)
                time.sleep(wait)
            else:
                raise
        except httpx.RequestError as exc:
            record.update({
                "outcome": "request_error",
                "error": str(exc),
                "retained": False,
            })
            if _CURRENT_ATTEMPTS is not None:
                _CURRENT_ATTEMPTS.append(record)
            if attempt < retries:
                time.sleep(2**attempt)
            else:
                raise
    raise RuntimeError("unreachable")


def synth_rime(*, text: str, speaker: str, model_id: str, api_key: str,
               sample_rate: int) -> bytes:
    payload = {"speaker": speaker, "text": text, "modelId": model_id, "samplingRate": sample_rate}
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "audio/wav", "Content-Type": "application/json"}
    r = _post_with_retries(lambda: httpx.post(RIME_TTS_URL, headers=headers, json=payload, timeout=120))
    if not r.content.startswith(b"RIFF"):
        raise RuntimeError(f"Rime response is not WAV: {r.content[:200]!r}")
    # The streamed container carries a placeholder length header; rewrap.
    return rewrap_wav(r.content, sample_rate)


def synth_eleven(*, text: str, voice_id: str, model_id: str, api_key: str, sample_rate: int,
                 stability: float, similarity_boost: float, normalization: str = "on") -> bytes:
    # apply_text_normalization is off by default on Flash 2.5 (latency);
    # 'on' is the provider's best config for numeral-heavy text and matches
    # provider-conditioned input rendering in corpus/render.py.
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {"stability": stability, "similarity_boost": similarity_boost},
        "apply_text_normalization": normalization,
    }
    url = ELEVEN_TTS_URL.format(voice_id=voice_id)
    params = {"output_format": f"pcm_{sample_rate}"}
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    r = _post_with_retries(lambda: httpx.post(url, headers=headers, params=params, json=payload, timeout=120))
    return pcm_to_wav_bytes(r.content, sample_rate)


def synth_google(*, text: str, voice: str, model_id: str, api_key: str, sample_rate: int) -> bytes:
    """Gemini TTS via the Interactions API. Returns 24kHz mono 16-bit WAV.

    gemini-3.1-flash-tts-preview has no SSML/say-as support, so input text
    should already be conditioned with the plain-text spelling standard.
    """
    import base64

    payload = {
        "model": model_id,
        "input": text,
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    # Free tier allows 10 requests/min for this model; pace to ~9/min.
    time.sleep(6.5)
    r = _post_with_retries(lambda: httpx.post(GOOGLE_INTERACTIONS_URL, headers=headers, json=payload, timeout=120), retries=5)
    body = r.json()
    # Audio arrives in steps[].content[] parts with mime_type audio/l16
    # (raw 16-bit PCM, base64). An optional ;rate= mime param overrides
    # the sample rate.
    for step in body.get("steps", []):
        for part in step.get("content", []):
            mime = part.get("mime_type", "")
            if mime.startswith("audio/") and part.get("data"):
                pcm = base64.b64decode(part["data"])
                rate = sample_rate
                for param in mime.split(";")[1:]:
                    k, _, v = param.strip().partition("=")
                    if k == "rate" and v.isdigit():
                        rate = int(v)
                return pcm_to_wav_bytes(pcm, rate)
    raise RuntimeError(f"Google response has no audio part; status={body.get('status')}, keys={list(body)}")


def synth_deepgram(*, text: str, voice_model: str, api_key: str, sample_rate: int) -> bytes:
    """Deepgram Aura-2. Raw linear16 requested (container=none) and wrapped
    to WAV locally — Deepgram's streamed WAV container carries a placeholder
    length header that audio validators reject. No SSML support, so input
    should already use the plain-text spelling standard.
    """
    params = {
        "model": voice_model,
        "encoding": "linear16",
        "sample_rate": sample_rate,
        "container": "none",
    }
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
    r = _post_with_retries(lambda: httpx.post(
        DEEPGRAM_SPEAK_URL, headers=headers, params=params, json={"text": text}, timeout=120))
    return pcm_to_wav_bytes(r.content, sample_rate)


def rewrap_wav(content: bytes, sample_rate: int) -> bytes:
    """Extract PCM from a (possibly streamed) WAV container and rewrap it
    with a correct length header. Streamed containers (Cartesia, Deepgram)
    carry placeholder sizes that audio validators reject.
    """
    i = content.find(b"data")
    if i < 0:
        raise RuntimeError("WAV container has no data chunk")
    return pcm_to_wav_bytes(content[i + 8:], sample_rate)


def synth_cartesia(*, text: str, voice_id: str, model_id: str, api_key: str, sample_rate: int) -> bytes:
    """Cartesia sonic-3 via /tts/bytes. The returned WAV container is
    streamed with a placeholder length header, so the PCM is rewrapped.
    No SSML support, so input should already use the plain-text standard.
    """
    payload = {
        "model_id": model_id,
        "transcript": text,
        "voice": {"mode": "id", "id": voice_id},
        "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": sample_rate},
        "language": "en",
    }
    headers = {
        "Cartesia-Version": CARTESIA_API_VERSION,
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    r = _post_with_retries(lambda: httpx.post(CARTESIA_TTS_URL, headers=headers, json=payload, timeout=120))
    if not r.content.startswith(b"RIFF"):
        raise RuntimeError(f"Cartesia response is not WAV: {r.content[:200]!r}")
    return rewrap_wav(r.content, sample_rate)


def synth_openai(*, text: str, voice: str, model_id: str, api_key: str, sample_rate: int) -> bytes:
    """OpenAI speech endpoint with response_format=pcm (24kHz mono 16-bit),
    wrapped to WAV locally. gpt-4o-mini-tts has no SSML support (steering is
    via an instructions prompt), so input should already use the plain-text
    spelling standard.
    """
    payload = {"model": model_id, "voice": voice, "input": text, "response_format": "pcm"}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = _post_with_retries(lambda: httpx.post(OPENAI_SPEECH_URL, headers=headers, json=payload, timeout=120))
    return pcm_to_wav_bytes(r.content, sample_rate)


def resolve_eleven_voice_name(voice_id: str, api_key: str) -> str | None:
    """Voice name for the model tag, or None if the key can't list voices."""
    r = httpx.get(ELEVEN_VOICES_URL, headers={"xi-api-key": api_key}, timeout=30)
    if r.status_code == 401 and "missing_permissions" in r.text:
        log.warning("API key lacks voices_read; using voice-id-based model tag")
        return None
    r.raise_for_status()
    for v in r.json().get("voices", []):
        if v["voice_id"] == voice_id:
            return v["name"]
    sys.exit(
        f"Voice {voice_id} is not in this ElevenLabs account's voice list.\n"
        "Voice-library voices must be added to 'My Voices' in the ElevenLabs app "
        "before they can be used via the API."
    )


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower()) or "voice"


def load_corpus(limit: int | None, seed: int, corpus: Path = DEFAULT_CORPUS,
                category: str | None = None) -> list[dict]:
    rows = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines()]
    if category:
        rows = [r for r in rows if r["category"] == category]
        if limit is not None:
            rows = random.Random(f"{seed}-{category}").sample(rows, limit)
            rows.sort(key=lambda r: r["id"])
        return rows
    if limit is None:
        return rows
    if set(DEMO_SHARE) != {r["category"] for r in rows}:
        sys.exit("corpus categories changed; update DEMO_SHARE")
    scale = limit / sum(DEMO_SHARE.values())
    picked: list[dict] = []
    for cat, share in DEMO_SHARE.items():
        quota = max(1, round(share * scale))
        pool = [r for r in rows if r["category"] == cat]
        picked.extend(random.Random(f"{seed}-{cat}").sample(pool, quota))
    picked.sort(key=lambda r: r["id"])
    return picked[:limit]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--limit", type=int, default=None, help="stratified subset size (default: all pairs)")
    p.add_argument("--seed", type=int, default=20260806)
    p.add_argument("--rime-speaker", default="clementine")
    p.add_argument("--rime-model", default="coda")
    p.add_argument("--eleven-voice-id", default="vCHG6sKIqAbXWNNm5vpY")
    p.add_argument("--eleven-model", default="eleven_flash_v2_5")
    p.add_argument("--google-voice", default="Despina")
    p.add_argument("--google-model", default="gemini-3.1-flash-tts-preview")
    p.add_argument("--deepgram-model", default="aura-2",
                   help="Deepgram TTS model family, e.g. aura-2")
    p.add_argument("--deepgram-speaker", default="thalia",
                   help="Aura voice name, e.g. thalia (combined as <model>-<speaker>-en)")
    p.add_argument("--cartesia-voice-id", default="e07c00bc-4134-4eae-9ea4-1a55fb45746b",
                   help="Cartesia voice id (default: the configured Sonic-3 voice)")
    p.add_argument("--cartesia-voice-name", default="default",
                   help="human name for the voice, used in the model tag")
    p.add_argument("--cartesia-model", default="sonic-3")
    p.add_argument("--openai-voice", default="coral")
    p.add_argument("--openai-model", default="gpt-4o-mini-tts")
    p.add_argument("--stability", type=float, default=0.5)
    p.add_argument("--similarity-boost", type=float, default=0.75)
    p.add_argument("--eleven-normalization", choices=["on", "off", "auto"], default="on")
    p.add_argument("--sample-rate", type=int, default=24000)
    p.add_argument(
        "--audio-mode",
        choices=["level-matched", "raw"],
        default="level-matched",
        help="apply linear loudness matching, or retain raw audio",
    )
    p.add_argument("--target-lufs", type=float, default=-23.0)
    p.add_argument("--true-peak-db", type=float, default=-1.0)
    p.add_argument(
        "--reuse-verified",
        action="store_true",
        help="reuse only files whose input, configuration, and audio hashes match",
    )
    p.add_argument("--outdir", type=Path, default=REPO_ROOT / "out")
    p.add_argument("--providers", choices=["both", "rime", "eleven", "google", "deepgram", "cartesia", "openai"],
                   default="both", help="'both' = rime + eleven; or a single provider by name")
    p.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS,
                   help="manifest to synthesize from (e.g. data/fidelity_corpus.jsonl)")
    p.add_argument("--category", default=None,
                   help="restrict to one category (simple seeded sample instead of stratified)")
    p.add_argument("--ids", default=None,
                   help="comma-separated corpus ids to synthesize exactly (overrides --limit/--category)")
    args = p.parse_args()
    rime_key = os.environ.get("RIME_API_KEY", "")
    eleven_key = os.environ.get("ELEVENLABS_API_KEY", "")
    google_key = os.environ.get("GEMINI_API_KEY", "")
    want_rime = args.providers in ("both", "rime")
    want_eleven = args.providers in ("both", "eleven")
    want_google = args.providers == "google"
    want_deepgram = args.providers == "deepgram"
    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if want_rime and not rime_key:
        sys.exit("Set RIME_API_KEY in the environment.")
    if want_eleven and not eleven_key:
        sys.exit("Set ELEVENLABS_API_KEY in the environment.")
    if want_google and not google_key:
        sys.exit("Set GEMINI_API_KEY in the environment (create one at aistudio.google.com/apikey).")
    if want_deepgram and not deepgram_key:
        sys.exit("Set DEEPGRAM_API_KEY in the environment.")
    want_cartesia = args.providers == "cartesia"
    cartesia_key = os.environ.get("CARTESIA_API_KEY", "")
    if want_cartesia and not cartesia_key:
        sys.exit("Set CARTESIA_API_KEY in the environment.")
    want_openai = args.providers == "openai"
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if want_openai and not openai_key:
        sys.exit("Set OPENAI_API_KEY in the environment.")

    rime_tag = f"rime_{args.rime_model}_{args.rime_speaker}"
    eleven_tag = None
    if want_eleven:
        voice_name = resolve_eleven_voice_name(args.eleven_voice_id, eleven_key)
        eleven_tag = f"elevenlabs_flash25_{slugify(voice_name) if voice_name else args.eleven_voice_id[:8].lower()}"
        log.info("eleven voice %r -> tag %s", voice_name, eleven_tag)
    log.info("model tags: %s vs %s", rime_tag, eleven_tag or "(eleven skipped)")

    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",") if i.strip()}
        rows = [r for r in load_corpus(None, args.seed, corpus=args.corpus) if r["id"] in wanted]
        missing = wanted - {r["id"] for r in rows}
        if missing:
            sys.exit(f"ids not found in {args.corpus}: {sorted(missing)}")
    else:
        rows = load_corpus(args.limit, args.seed, corpus=args.corpus, category=args.category)
    total = sum(1 for _ in args.corpus.read_text(encoding="utf-8").splitlines())
    log.info("corpus has %d rows; synthesizing %d", total, len(rows))

    providers = []
    if want_rime:
        providers.append((
            rime_tag,
            "rime",
            {
                "provider": "rime",
                "endpoint": RIME_TTS_URL,
                "model": args.rime_model,
                "voice": args.rime_speaker,
                "sample_rate": args.sample_rate,
            },
            lambda text: synth_rime(
                text=text, speaker=args.rime_speaker, model_id=args.rime_model,
                api_key=rime_key, sample_rate=args.sample_rate),
        ))
    if want_eleven:
        providers.append((
            eleven_tag,
            "elevenlabs",
            {
                "provider": "elevenlabs",
                "endpoint": ELEVEN_TTS_URL,
                "model": args.eleven_model,
                "voice_id": args.eleven_voice_id,
                "stability": args.stability,
                "similarity_boost": args.similarity_boost,
                "apply_text_normalization": args.eleven_normalization,
                "sample_rate": args.sample_rate,
            },
            lambda text: synth_eleven(
                text=text, voice_id=args.eleven_voice_id, model_id=args.eleven_model,
                api_key=eleven_key, sample_rate=args.sample_rate,
                stability=args.stability, similarity_boost=args.similarity_boost,
                normalization=args.eleven_normalization),
        ))
    if want_google:
        # e.g. gemini-3.1-flash-tts-preview -> google_flash31_despina
        version = "".join(c for c in args.google_model.split("flash")[0] if c.isdigit())
        google_tag = f"google_flash{version}_{args.google_voice.lower()}"
        providers.append((
            google_tag,
            "plaintext",
            {
                "provider": "google",
                "endpoint": GOOGLE_INTERACTIONS_URL,
                "model": args.google_model,
                "voice": args.google_voice,
                "sample_rate": args.sample_rate,
            },
            lambda text: synth_google(
                text=text, voice=args.google_voice, model_id=args.google_model,
                api_key=google_key, sample_rate=args.sample_rate),
        ))
    if want_deepgram:
        # The benchmark is en-US only, so the language suffix is fixed.
        deepgram_voice_model = f"{args.deepgram_model}-{args.deepgram_speaker}-en"
        deepgram_tag = f"deepgram_{args.deepgram_model.replace('-', '')}_{args.deepgram_speaker}"
        # Deepgram-specific conditioning: comma-joined characters for mixed
        # codes, literal hyphens for pre-spelled names (see corpus/render.py).
        providers.append((
            deepgram_tag,
            "deepgram",
            {
                "provider": "deepgram",
                "endpoint": DEEPGRAM_SPEAK_URL,
                "model": deepgram_voice_model,
                "sample_rate": args.sample_rate,
                "encoding": "linear16",
            },
            lambda text: synth_deepgram(
                text=text, voice_model=deepgram_voice_model,
                api_key=deepgram_key, sample_rate=args.sample_rate),
        ))
    if want_cartesia:
        # Cartesia respects <spell> just like Rime respects spell(): its
        # provider-specific conditioned input (corpus/render.py "cartesia").
        cartesia_tag = f"cartesia_{args.cartesia_model.replace('-', '')}_{slugify(args.cartesia_voice_name)}"
        providers.append((
            cartesia_tag,
            "cartesia",
            {
                "provider": "cartesia",
                "endpoint": CARTESIA_TTS_URL,
                "api_version": CARTESIA_API_VERSION,
                "model": args.cartesia_model,
                "voice_id": args.cartesia_voice_id,
                "voice_name": args.cartesia_voice_name,
                "language": "en",
                "sample_rate": args.sample_rate,
            },
            lambda text: synth_cartesia(
                text=text, voice_id=args.cartesia_voice_id, model_id=args.cartesia_model,
                api_key=cartesia_key, sample_rate=args.sample_rate),
        ))
    if want_openai:
        # e.g. gpt-4o-mini-tts -> openai_4ominitts_coral
        openai_tag = f"openai_{slugify(args.openai_model.removeprefix('gpt-'))}_{args.openai_voice.lower()}"
        providers.append((
            openai_tag,
            "plaintext",
            {
                "provider": "openai",
                "endpoint": OPENAI_SPEECH_URL,
                "model": args.openai_model,
                "voice": args.openai_voice,
                "response_format": "pcm",
                "sample_rate": args.sample_rate,
            },
            lambda text: synth_openai(
                text=text, voice=args.openai_voice, model_id=args.openai_model,
                api_key=openai_key, sample_rate=args.sample_rate),
        ))

    corpus_sha256 = sha256_file(args.corpus)
    for tag, style, provider_config, synth in providers:
        provider_config_sha256 = canonical_sha256(provider_config)
        run_config = {
            "provider": provider_config,
            "render_style": style,
            "audio": {
                "mode": args.audio_mode,
                "target_lufs": args.target_lufs,
                "true_peak_db": args.true_peak_db,
                "sample_rate": args.sample_rate,
                "channels": 1,
                "sample_width_bytes": 2,
                "ffmpeg_version": (
                    ffmpeg_version()
                    if args.audio_mode == "level-matched"
                    else "not_used"
                ),
            },
            "seed": "not_supported",
        }
        config_sha256 = canonical_sha256(run_config)
        outdir = args.outdir / f"{tag}__{config_sha256[:12]}"
        outdir.mkdir(parents=True, exist_ok=True)
        run_path = outdir / "run.json"
        manifest_path = outdir / "manifest.json"
        existing_rows: dict[str, dict[str, Any]] = {}
        if run_path.exists():
            existing_run = json.loads(run_path.read_text(encoding="utf-8"))
            if (
                existing_run.get("config_sha256") != config_sha256
                or existing_run.get("corpus_sha256") != corpus_sha256
                or existing_run.get("provider_config_sha256")
                != provider_config_sha256
            ):
                sys.exit(
                    f"{outdir} belongs to a different configuration or corpus. "
                    "Use a clean output directory."
                )
        elif any(outdir.iterdir()):
            sys.exit(
                f"{outdir} is non-empty but has no run.json. "
                "Use an output directory with a matching synthesis checkpoint."
            )
        if manifest_path.exists():
            existing_rows = {
                row["id"]: row
                for row in json.loads(manifest_path.read_text(encoding="utf-8"))
            }

        run_record = {
            "schema_version": 1,
            "protocol_version": PROTOCOL_VERSION,
            "status": "in_progress",
            "created_at_utc": (
                existing_run.get("created_at_utc", datetime.now(UTC).isoformat())
                if run_path.exists()
                else datetime.now(UTC).isoformat()
            ),
            "corpus_path": str(args.corpus),
            "corpus_sha256": corpus_sha256,
            "config": run_config,
            "config_sha256": config_sha256,
            "provider_config_sha256": provider_config_sha256,
            "model_tag": tag,
        }
        atomic_write_json(run_path, run_record)

        manifest = []
        for i, row in enumerate(rows, start=1):
            rendered = render_text(row["text"], row["spell_spans"], style)
            wav_path = outdir / f"{row['id']}.wav"
            input_sha256 = sha256_bytes(rendered.encode("utf-8"))
            previous = existing_rows.get(row["id"])
            orphaned_wav = wav_path.exists() and previous is None
            try:
                can_reuse = recover_or_reuse_wav(
                    wav_path,
                    previous,
                    reuse_verified=args.reuse_verified,
                )
            except ValueError as exc:
                sys.exit(str(exc))
            if can_reuse:
                assert previous is not None
                expected = {
                    "input_sha256": input_sha256,
                    "config_sha256": config_sha256,
                    "corpus_sha256": corpus_sha256,
                }
                mismatched = [
                    key for key, value in expected.items()
                    if previous.get(key) != value
                ]
                if mismatched:
                    sys.exit(
                        f"Cannot reuse {wav_path}; mismatched fields: {mismatched}"
                    )
                actual_hash = sha256_file(wav_path)
                if actual_hash != previous.get("audio_sha256"):
                    sys.exit(f"Cannot reuse {wav_path}; audio hash changed.")
                manifest.append(previous)
                write_synthesis_checkpoint(
                    manifest_path=manifest_path,
                    run_path=run_path,
                    manifest=manifest,
                    run_record=run_record,
                    status="in_progress",
                )
                log.info("[%s] reused verified %d/%d %s", tag, i, len(rows), row["id"])
                continue
            if orphaned_wav and args.reuse_verified:
                log.warning(
                    "[%s] regenerating %s because its WAV had no manifest row",
                    tag,
                    row["id"],
                )

            request_attempts: list[dict[str, Any]] = []
            global _CURRENT_ATTEMPTS
            _CURRENT_ATTEMPTS = request_attempts
            try:
                for validation_attempt in range(1, 4):
                    attempt_start = len(request_attempts)
                    try:
                        raw_bytes = synth(rendered)
                        raw_info = wav_info(raw_bytes)
                        if raw_info["sample_rate_hz"] != args.sample_rate:
                            raise RuntimeError(
                                f"Provider returned {raw_info['sample_rate_hz']} Hz, "
                                f"expected {args.sample_rate} Hz"
                            )
                        if args.audio_mode == "level-matched":
                            final_bytes, audio_processing = normalize_loudness(
                                raw_bytes,
                                sample_rate=args.sample_rate,
                                target_lufs=args.target_lufs,
                                true_peak_db=args.true_peak_db,
                            )
                        else:
                            final_bytes = raw_bytes
                            audio_processing = {"mode": "raw"}
                        final_info = wav_info(final_bytes)
                    except (RuntimeError, wave.Error) as exc:
                        new_attempts = request_attempts[attempt_start:]
                        transport_successes = [
                            attempt
                            for attempt in new_attempts
                            if attempt["outcome"] == "transport_success"
                        ]
                        if transport_successes:
                            transport_successes[-1]["outcome"] = "invalid_audio"
                            transport_successes[-1]["validation_error"] = str(exc)
                        if transport_successes and validation_attempt < 3:
                            log.warning(
                                "[%s] invalid audio for %s; retrying request",
                                tag,
                                row["id"],
                            )
                            continue
                        raise
                    break
                successful = [
                    attempt
                    for attempt in request_attempts
                    if attempt["outcome"] == "transport_success"
                ]
                if successful:
                    successful[-1]["outcome"] = "retained_valid_audio"
                    successful[-1]["retained"] = True
            except Exception as exc:
                if request_attempts:
                    request_attempts[-1]["validation_error"] = str(exc)
                raise
            finally:
                _CURRENT_ATTEMPTS = None

            atomic_write_bytes(wav_path, final_bytes)
            log.info("[%s] %d/%d %s", tag, i, len(rows), row["id"])
            manifest.append({
                "id": row["id"],
                "family_id": row["family_id"],
                "template_id": row.get("template_id"),
                "category": row["category"],
                "subcategory": row["subcategory"],
                "canonical_text": row["text"],
                "rendered_text": rendered,
                "input_sha256": input_sha256,
                "wav_path": str(wav_path),
                "audio_sha256": sha256_bytes(final_bytes),
                "raw_audio_sha256": sha256_bytes(raw_bytes),
                "audio_bytes": len(final_bytes),
                "audio_info": final_info,
                "raw_audio_info": raw_info,
                "audio_processing": audio_processing,
                "config_sha256": config_sha256,
                "corpus_sha256": corpus_sha256,
                "provider_config_sha256": provider_config_sha256,
                "protocol_version": PROTOCOL_VERSION,
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "request_attempts": request_attempts,
                "model_tag": tag,
                "tags": row.get("tags", []),
            })
            write_synthesis_checkpoint(
                manifest_path=manifest_path,
                run_path=run_path,
                manifest=manifest,
                run_record=run_record,
                status="in_progress",
            )
        run_record["completed_at_utc"] = datetime.now(UTC).isoformat()
        run_record["items"] = len(manifest)
        write_synthesis_checkpoint(
            manifest_path=manifest_path,
            run_path=run_path,
            manifest=manifest,
            run_record=run_record,
            status="complete",
        )
        log.info("[%s] wrote %d clips + manifest.json", tag, len(manifest))

    # Demonstrative examples per tag: show where conditioning differs.
    example = next((r for r in rows if r["spell_spans"]), None)
    plain = next((r for r in rows if not r["spell_spans"]), None)
    print("\n=== rendered input examples ===")
    for tag, style, _, _ in providers:
        print(f"\n[{tag}]")
        if example:
            print(f"  alphanumeric : {render_text(example['text'], example['spell_spans'], style)}")
        if plain:
            print(f"  other        : {render_text(plain['text'], plain['spell_spans'], style)}")
    if example:
        print(f"\ncanonical (shown to raters): {example['text']}")


if __name__ == "__main__":
    main()
