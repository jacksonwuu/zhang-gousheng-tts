#!/usr/bin/env python3
"""Measure duration, pitch, pauses, dynamics, and optional loudness."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")

try:
    import librosa
    import numpy as np
    import soundfile as sf
except ImportError as exc:
    raise SystemExit(
        "Missing audio analysis dependencies. Run "
        "`cd $INDEXTTS_ROOT && uv sync --extra webui` and then "
        "`python3 $SKILL_DIR/scripts/check_env.py --deep`."
    ) from exc


def find_ffmpeg() -> str | None:
    configured = os.environ.get("FFMPEG_BIN")
    if configured:
        path = Path(configured)
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in (
        Path("/opt/homebrew/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path.home() / "miniforge3/bin/ffmpeg",
        Path.home() / "miniconda3/bin/ffmpeg",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def finite_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if np.isfinite(parsed) else None


def loudnorm(path: Path) -> dict | None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return None
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    match = re.search(r'\{[^{}]*"input_i"[^{}]*\}', result.stderr, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return {
        "integrated_lufs": finite_float(data["input_i"]),
        "true_peak_dbtp": finite_float(data["input_tp"]),
        "lra_lu": finite_float(data["input_lra"]),
    }


def spoken_units(text: str) -> int:
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]+", text))
    numbers = len(re.findall(r"\d+(?:\.\d+)?", text))
    return cjk + latin + numbers


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a speech WAV file.")
    parser.add_argument("input", type=Path)
    text_source = parser.add_mutually_exclusive_group()
    text_source.add_argument(
        "--text",
        help="Original text, used to estimate speaking rate.",
    )
    text_source.add_argument(
        "--text-file",
        type=Path,
        help="UTF-8 text file used to estimate speaking rate.",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--loudnorm", action="store_true")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")
    try:
        audio, sample_rate = sf.read(args.input, dtype="float32")
    except Exception as exc:
        raise SystemExit(f"Could not read audio: {args.input}: {exc}") from exc
    if audio.size == 0:
        raise SystemExit("Input contains no audio samples")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    voiced = np.array([])
    if audio.size >= 2048:
        f0, _, _ = librosa.pyin(
            audio,
            fmin=70,
            fmax=400,
            sr=sample_rate,
            frame_length=2048,
            hop_length=256,
        )
        voiced = f0[np.isfinite(f0)]

    rms = librosa.feature.rms(
        y=audio, frame_length=2048, hop_length=256
    )[0]
    rms_db = 20.0 * np.log10(np.maximum(rms, 1e-8))
    pause = rms_db < (float(np.max(rms_db)) - 40.0)
    changes = np.diff(np.r_[False, pause, False].astype(int))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    pauses = (ends - starts) * 256 / sample_rate

    centroid = librosa.feature.spectral_centroid(
        y=audio, sr=sample_rate, n_fft=2048, hop_length=256
    )[0]

    result = {
        "file": str(args.input),
        "duration_seconds": round(len(audio) / sample_rate, 2),
        "sample_rate": sample_rate,
        "peak": round(float(np.max(np.abs(audio))), 3),
        "f0_median_hz": (
            round(float(np.median(voiced)), 1) if voiced.size else None
        ),
        "f0_p10_hz": (
            round(float(np.percentile(voiced, 10)), 1) if voiced.size else None
        ),
        "f0_p90_hz": (
            round(float(np.percentile(voiced, 90)), 1) if voiced.size else None
        ),
        "f0_std_hz": (
            round(float(np.std(voiced)), 1) if voiced.size else None
        ),
        "rms_db_std": round(float(np.std(rms_db)), 1),
        "pause_ratio": round(float(pause.mean()), 3),
        "pauses_over_200ms": int((pauses > 0.2).sum()),
        "pauses_over_500ms": int((pauses > 0.5).sum()),
        "spectral_centroid_hz": round(float(np.median(centroid)), 0),
    }
    text = args.text
    if args.text_file is not None:
        try:
            text = args.text_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"Could not read text file: {exc}") from exc
    if text is not None:
        units = spoken_units(text)
        result["spoken_units"] = units
        result["units_per_minute"] = (
            round(units / (len(audio) / sample_rate) * 60, 1)
            if len(audio) and sample_rate
            else None
        )
    if args.loudnorm:
        result["loudness"] = loudnorm(args.input)

    if not voiced.size:
        print(
            "WARNING: no voiced pitch frames detected; pitch metrics are null.",
            file=sys.stderr,
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
