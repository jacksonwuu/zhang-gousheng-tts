#!/usr/bin/env python3
"""Create or update the one-click voice profile.

The user's voice reference is required. A style reference is optional: without
it the profile uses the measured Zhang Gousheng-style emotion vector, so a new
user only has to provide one clean voice sample.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from check_env import default_indextts_root, default_profile_path


SCRIPT_DIR = Path(__file__).resolve().parent

COMMON_DEFAULTS: dict[str, Any] = {
    "lang": "ZH",
    "device": "cpu",
    "max_text_tokens_per_segment": 300,
    "interval_silence": 200,
    "chunk_chars": 500,
    "pause_ms": 250,
    "format": "both",
}

VECTOR_DEFAULTS: dict[str, Any] = {
    "style_mode": "vector",
    "emo_alpha": 0.35,
    "duration_factor": 1.08,
    "temperature": 0.85,
    "top_p": 0.90,
    "top_k": 40,
    "repetition_penalty": 8.5,
    "emo_vector": [0.08, 0.02, 0, 0, 0, 0, 0.05, 0.65],
}

REFERENCE_DEFAULTS: dict[str, Any] = {
    "style_mode": "reference",
    "emo_alpha": 0.55,
    "duration_factor": 1.10,
    "temperature": 0.86,
    "top_p": 0.91,
    "top_k": 45,
    "repetition_penalty": 8.2,
    "emo_vector": None,
}


def extract_reference(
    source: Path,
    output: Path,
    start: float | None,
    start_option: str,
) -> None:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "prepare_reference.py"),
        "--input",
        str(source),
        "--output",
        str(output),
        "--duration",
        "15",
    ]
    if start is not None:
        command.extend(["--start", str(start)])
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"Could not prepare reference audio from {source}. "
            f"Choose a cleaner section with {start_option}."
        )


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure one-click voice and optional style references."
    )
    parser.add_argument("--voice-source", required=True, type=Path)
    parser.add_argument(
        "--style-source",
        type=Path,
        help="Optional 10-60 second authorized style clip. Omit to use the "
        "built-in Zhang Gousheng-style emotion vector.",
    )
    parser.add_argument("--voice-start", type=float)
    parser.add_argument("--style-start", type=float)
    parser.add_argument("--indextts-root", type=Path)
    parser.add_argument("--profile", type=Path, default=default_profile_path())
    parser.add_argument("--lang", default=COMMON_DEFAULTS["lang"])
    parser.add_argument("--device", default=COMMON_DEFAULTS["device"])
    parser.add_argument("--emo-alpha", type=float)
    parser.add_argument("--duration-factor", type=float)
    args = parser.parse_args()

    root = (
        args.indextts_root.expanduser().resolve()
        if args.indextts_root
        else default_indextts_root()
    )
    if not (root / "pyproject.toml").is_file():
        raise SystemExit(f"IndexTTS checkout not found at {root}. Set INDEXTTS_ROOT.")

    voice_source = args.voice_source.expanduser().resolve()
    style_source = (
        args.style_source.expanduser().resolve() if args.style_source else None
    )
    if not voice_source.is_file():
        raise SystemExit(f"Voice source not found: {voice_source}")
    if style_source and not style_source.is_file():
        raise SystemExit(f"Style source not found: {style_source}")
    if style_source and voice_source == style_source:
        raise SystemExit("Voice and style sources must be different files")
    if args.style_start is not None and style_source is None:
        raise SystemExit("--style-start requires --style-source")

    profile_path = args.profile.expanduser().resolve()
    profile_dir = profile_path.parent
    profile_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(profile_dir, 0o700)
    except OSError:
        pass

    voice_path = profile_dir / "voice_15s.wav"
    extract_reference(
        voice_source, voice_path, args.voice_start, "--voice-start"
    )
    try:
        os.chmod(voice_path, 0o600)
    except OSError:
        pass

    style_path: Path | None = None
    if style_source:
        style_path = profile_dir / "style_15s.wav"
        extract_reference(
            style_source, style_path, args.style_start, "--style-start"
        )
        try:
            os.chmod(style_path, 0o600)
        except OSError:
            pass
        mode_defaults = REFERENCE_DEFAULTS
    else:
        mode_defaults = VECTOR_DEFAULTS

    existing = load_existing(profile_path)
    profile: dict[str, Any] = {
        **COMMON_DEFAULTS,
        **mode_defaults,
        **existing,
        "voice": str(voice_path),
        "style_reference": str(style_path) if style_path else None,
        "style_mode": "reference" if style_path else "vector",
        "indextts_root": str(root),
        "lang": args.lang.upper(),
        "device": args.device,
    }
    if args.emo_alpha is not None:
        profile["emo_alpha"] = args.emo_alpha
    if args.duration_factor is not None:
        profile["duration_factor"] = args.duration_factor
    if style_path:
        profile["emo_vector"] = None
    elif not profile.get("emo_vector"):
        profile["emo_vector"] = VECTOR_DEFAULTS["emo_vector"]

    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(profile_path, 0o600)
    except OSError:
        pass
    print(
        json.dumps(
            {
                "profile": str(profile_path),
                "indextts_root": str(root),
                "voice": str(voice_path),
                "style_reference": str(style_path) if style_path else None,
                "style_mode": profile["style_mode"],
                "status": "ready",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
