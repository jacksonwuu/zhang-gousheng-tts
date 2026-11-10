#!/usr/bin/env python3
"""Extract a clean 10-15 second speech window from a video or audio file."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

try:
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
except ImportError as exc:
    raise SystemExit(
        "Missing audio dependencies. Run `cd $INDEXTTS_ROOT && uv sync --extra webui` "
        "and then `python3 $SKILL_DIR/scripts/check_env.py --deep`."
    ) from exc


def find_ffmpeg() -> str:
    configured = os.environ.get("FFMPEG_BIN")
    if configured:
        if Path(configured).is_file() and os.access(configured, os.X_OK):
            return configured
        raise SystemExit(
            f"FFMPEG_BIN is not an executable file: {configured}"
        )
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = [
        Path("/opt/homebrew/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path.home() / "miniforge3/bin/ffmpeg",
        Path.home() / "miniconda3/bin/ffmpeg",
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise SystemExit(
        "ffmpeg not found. Install ffmpeg or set FFMPEG_BIN to its executable path."
    )


def extract_audio(input_path: Path, output_path: Path) -> None:
    cmd = [
        find_ffmpeg(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-1000:]
        raise SystemExit(f"ffmpeg could not decode {input_path}:\n{detail}")


def frame_rms(
    audio: np.ndarray,
    frame: int,
    hop: int,
) -> np.ndarray:
    if audio.size < frame:
        return np.array(
            [float(np.sqrt(np.mean(audio.astype(np.float64) ** 2) + 1e-12))],
            dtype=np.float32,
        )
    squared = np.square(audio.astype(np.float64))
    cumulative = np.concatenate(([0.0], np.cumsum(squared)))
    starts = np.arange(0, audio.size - frame + 1, hop)
    ends = starts + frame
    means = (cumulative[ends] - cumulative[starts]) / frame
    return np.sqrt(np.maximum(means, 1e-12)).astype(np.float32)


def speech_mask(rms: np.ndarray) -> np.ndarray:
    db = 20.0 * np.log10(np.maximum(rms, 1e-8))
    if db.size == 0 or float(np.max(db)) < -80.0:
        return np.zeros(db.shape, dtype=bool)
    return db > (float(np.max(db)) - 35.0)


def select_window(audio: np.ndarray, sample_rate: int, duration: float) -> tuple[int, int, float]:
    frame = max(1, int(sample_rate * 0.02))
    hop = frame
    if audio.size < frame:
        rms = frame_rms(audio, frame, hop)
        return 0, audio.size, float(speech_mask(rms).mean())

    rms = frame_rms(audio, frame, hop)
    speech = speech_mask(rms)

    window_samples = min(audio.size, max(frame, int(sample_rate * duration)))
    window_frames = max(1, window_samples // hop)
    if window_frames >= speech.size:
        return 0, audio.size, float(speech.mean())

    cumulative = np.concatenate(([0], np.cumsum(speech, dtype=np.int64)))
    starts = np.arange(0, speech.size - window_frames + 1)
    ratios = (
        cumulative[starts + window_frames] - cumulative[starts]
    ) / float(window_frames)
    best = int(starts[int(np.argmax(ratios))])
    start_sample = best * hop
    end_sample = min(audio.size, start_sample + window_samples)
    return start_sample, end_sample, float(np.max(ratios))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a clean 10-15 second reference clip from video/audio."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument(
        "--start",
        type=float,
        default=None,
        help="Exact start time in seconds. Omit to auto-select the densest speech window.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")
    if args.duration < 5 or args.duration > 30:
        raise SystemExit("--duration must be between 5 and 30 seconds")
    if args.start is not None and args.start < 0:
        raise SystemExit("--start cannot be negative")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ref-audio-") as tmp:
        temp_wav = Path(tmp) / "audio_16k.wav"
        extract_audio(args.input, temp_wav)
        audio, sample_rate = sf.read(temp_wav, dtype="float32")
        if audio.size == 0:
            raise SystemExit("The input contains no audio samples")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        if args.start is not None:
            start = max(0, int(args.start * sample_rate))
            end = min(audio.size, start + int(args.duration * sample_rate))
            if start >= audio.size or end - start < int(sample_rate * 2):
                raise SystemExit(
                    f"--start {args.start}s leaves no usable audio in the input"
                )
            frame = max(1, int(sample_rate * 0.02))
            selected_rms = frame_rms(audio[start:end], frame, frame)
            speech_ratio = float(speech_mask(selected_rms).mean())
        else:
            start, end, speech_ratio = select_window(
                audio, sample_rate, args.duration
            )
            if speech_ratio < 0.15:
                raise SystemExit(
                    "Could not find a speech-dense window. "
                    "Pass --start with a known clean section."
                )

        clip = audio[start:end].copy()
        if clip.size == 0:
            raise SystemExit("Selected reference window is empty")
        clip_duration = clip.size / sample_rate
        if clip_duration < 3:
            raise SystemExit(
                f"Selected audio is only {clip_duration:.1f}s; "
                "use at least a 5-second speech sample."
            )
        if clip_duration < 5:
            print(
                f"WARNING: selected audio is only {clip_duration:.1f}s; "
                "10-15s is preferred.",
                file=sys.stderr,
            )
        clipping_ratio = float(np.mean(np.abs(clip) >= 0.999))
        source_peak = float(np.max(np.abs(clip)))
        source_peak_db = (
            20.0 * np.log10(source_peak) if source_peak > 0 else float("-inf")
        )
        clip -= float(np.mean(clip))
        peak = float(np.max(np.abs(clip)))
        if peak > 0:
            clip *= 0.95 / peak

        fade = min(int(sample_rate * 0.01), clip.size // 2)
        if fade > 0:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            clip[:fade] *= ramp
            clip[-fade:] *= ramp[::-1]

        ratio = Fraction(44100, sample_rate).limit_denominator()
        clip = resample_poly(clip, ratio.numerator, ratio.denominator).astype(
            np.float32
        )
        sf.write(args.output, clip, 44100, subtype="PCM_24")

    info = {
        "input": str(args.input),
        "output": str(args.output),
        "selection_start_seconds": round(start / sample_rate, 2),
        "selection_end_seconds": round(end / sample_rate, 2),
        "duration_seconds": round(len(clip) / 44100, 2),
        "sample_rate": 44100,
        "speech_ratio": round(speech_ratio, 3),
        "clipping_ratio": round(clipping_ratio, 5),
        "source_peak_dbfs": (
            round(source_peak_db, 1)
            if np.isfinite(source_peak_db)
            else "-inf"
        ),
        "peak": round(float(np.max(np.abs(clip))), 3),
    }
    if speech_ratio < 0.35:
        print(
            "WARNING: selected window contains a lot of silence or background. "
            "Check the clip before cloning.",
            file=sys.stderr,
        )
    if clipping_ratio > 0.001:
        print(
            "WARNING: source audio has clipped samples; this can distort the clone.",
            file=sys.stderr,
        )
    if source_peak_db < -30:
        print(
            "WARNING: source audio is very quiet; check the recording gain.",
            file=sys.stderr,
        )
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
