"""Optional, bounded local speech transcription for a text-only reasoning host.

The original audio remains the evidence. This module returns a derived transcript
with the original hash and model provenance; it never changes host ownership,
claims Body requests, or treats recognized words as integration instructions.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class LocalSttError(RuntimeError):
    """A bounded local transcription failure safe for an operational status."""


@dataclass(frozen=True)
class LocalSttConfig:
    model: str = "tiny.en"
    cache_directory: Path | None = None
    language: str | None = "en"
    cpu_threads: int = 4
    max_bytes: int = 8_000_000
    max_seconds: float = 30.0
    allow_download: bool = False


@dataclass(frozen=True)
class DecodedAudio:
    samples: Any
    duration_seconds: float


def decode_audio_bounded(payload: bytes, max_seconds: float) -> DecodedAudio:
    """Decode WebM and other ordinary audio without unbounded expansion."""
    try:
        import av
        import numpy as np
    except ImportError as exc:
        raise LocalSttError("Local audio decoding is not installed.") from exc
    chunks = []
    sample_count = 0
    rate = 16_000
    limit = int(max_seconds * rate)
    try:
        with av.open(io.BytesIO(payload), mode="r") as container:
            if not container.streams.audio:
                raise LocalSttError("The preserved artifact contains no audio stream.")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    sample_count += converted.samples
                    if sample_count > limit:
                        raise LocalSttError("Audio exceeds the local transcription duration limit.")
                    chunks.append(converted.to_ndarray().reshape(-1))
            for converted in resampler.resample(None):
                sample_count += converted.samples
                if sample_count > limit:
                    raise LocalSttError("Audio exceeds the local transcription duration limit.")
                chunks.append(converted.to_ndarray().reshape(-1))
    except LocalSttError:
        raise
    except Exception as exc:
        raise LocalSttError("The preserved audio could not be decoded locally.") from exc
    if not sample_count:
        raise LocalSttError("The preserved artifact contains no decodable audio samples.")
    samples = np.concatenate(chunks).astype(np.float32) / 32768.0
    return DecodedAudio(samples=samples, duration_seconds=sample_count / rate)


class LocalAudioTranscriber:
    """Reuse one CPU model for successive preserved, bounded Body clips."""

    def __init__(
        self, config: LocalSttConfig, *, model: Any = None,
        decoder: Callable[[bytes, float], DecodedAudio] = decode_audio_bounded,
    ) -> None:
        if config.max_bytes < 1 or not 0 < config.max_seconds <= 30 or config.cpu_threads < 1:
            raise ValueError("Invalid local transcription bounds")
        self.config, self._model, self._decoder = config, model, decoder

    def prepare(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise LocalSttError("Install the local-speech optional dependency first.") from exc
        try:
            self._model = WhisperModel(
                self.config.model, device="cpu", compute_type="int8",
                cpu_threads=self.config.cpu_threads,
                download_root=(str(self.config.cache_directory)
                               if self.config.cache_directory is not None else None),
                local_files_only=not self.config.allow_download,
            )
        except Exception as exc:
            raise LocalSttError("The configured local speech model is not ready.") from exc

    def transcribe(
        self, payload: bytes, *, source_sha256: str, captured_at: str,
        media_type: str = "audio/webm",
    ) -> dict[str, Any]:
        if not isinstance(payload, bytes) or not payload or len(payload) > self.config.max_bytes:
            raise LocalSttError("Audio is empty or exceeds the local byte limit.")
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != source_sha256:
            raise LocalSttError("Audio does not match its preserved evidence hash.")
        if not isinstance(captured_at, str) or not captured_at.strip():
            raise LocalSttError("The original audio capture time is required.")
        if not isinstance(media_type, str) or not media_type.startswith("audio/"):
            raise LocalSttError("Only preserved audio artifacts can be transcribed locally.")
        decoded = self._decoder(payload, self.config.max_seconds)
        if not math.isfinite(decoded.duration_seconds) or not 0 < decoded.duration_seconds <= self.config.max_seconds:
            raise LocalSttError("Audio exceeds the local transcription duration limit.")
        self.prepare()
        try:
            segments, info = self._model.transcribe(
                decoded.samples, language=self.config.language, beam_size=1,
                best_of=1, temperature=0, vad_filter=True,
                condition_on_previous_text=False,
                vad_parameters={"min_speech_duration_ms": 200},
            )
            result_segments = []
            for segment in segments:
                text = segment.text.strip()
                if not text:
                    continue
                result_segments.append({
                    "start": float(segment.start), "end": float(segment.end),
                    "text": text, "avg_logprob": float(segment.avg_logprob),
                    "no_speech_probability": float(segment.no_speech_prob),
                })
        except Exception as exc:
            raise LocalSttError("Local speech recognition failed for the preserved clip.") from exc
        text = " ".join(segment["text"] for segment in result_segments)
        return {
            "status": "transcribed" if text else "no_speech",
            "text": text,
            "evidence": {
                "sha256": actual_hash, "captured_at": captured_at,
                "media_type": media_type, "byte_length": len(payload),
            },
            "transcription": {
                "engine": "faster-whisper", "model": self.config.model,
                "device": "cpu", "compute_type": "int8",
                "language": info.language,
                "language_probability": float(info.language_probability),
                "duration_seconds": decoded.duration_seconds,
                "segments": result_segments,
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--captured-at")
    parser.add_argument("--media-type", default="audio/webm")
    parser.add_argument("--model", default="tiny.en")
    parser.add_argument("--cache-directory", type=Path)
    parser.add_argument("--prepare", action="store_true",
                        help="Explicitly allow downloading the configured public speech model.")
    args = parser.parse_args()
    transcriber = LocalAudioTranscriber(LocalSttConfig(
        model=args.model, cache_directory=args.cache_directory, allow_download=args.prepare,
    ))
    if args.prepare:
        transcriber.prepare()
        print(json.dumps({"status": "ready", "model": args.model, "device": "cpu"}))
        if args.audio is None:
            return
    if args.audio is None or args.sha256 is None or args.captured_at is None:
        parser.error("--audio, --sha256 and --captured-at are required for transcription")
    if args.audio.stat().st_size > transcriber.config.max_bytes:
        raise LocalSttError("Audio exceeds the local byte limit.")
    print(json.dumps(transcriber.transcribe(
        args.audio.read_bytes(), source_sha256=args.sha256,
        captured_at=args.captured_at, media_type=args.media_type,
    ), ensure_ascii=False))


if __name__ == "__main__":
    main()
