#!/usr/bin/env python3
"""Generate speech with the user's voice plus a Zhang Gousheng-style reference."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import soundfile as sf
    from scipy.signal import butter, resample_poly, sosfilt
except ImportError as exc:
    raise SystemExit(
        "Missing audio dependencies. Run `cd $INDEXTTS_ROOT && uv sync --extra webui` "
        "and then `python3 $SKILL_DIR/scripts/check_env.py --deep`."
    ) from exc

from check_env import check_environment, default_indextts_root


os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl-cache")

ROOT = default_indextts_root()
DEFAULT_STYLE = Path(
    os.environ.get(
        "ZHANG_STYLE_REFERENCE",
        ROOT / "downloads/zhang_style_15s.wav",
    )
).expanduser()
INVOCATION_CWD = Path.cwd()


def absolute_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (INVOCATION_CWD / path).resolve()


def master_audio(input_path: Path, output_path: Path) -> None:
    audio, sample_rate = sf.read(input_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    highpass = butter(
        2, 60 / (sample_rate / 2), btype="highpass", output="sos"
    )
    audio = sosfilt(highpass, audio).astype(np.float32)

    chest = butter(
        2,
        [90 / (sample_rate / 2), 180 / (sample_rate / 2)],
        btype="bandpass",
        output="sos",
    )
    presence = butter(
        2,
        [2500 / (sample_rate / 2), 4500 / (sample_rate / 2)],
        btype="bandpass",
        output="sos",
    )
    audio = (
        audio
        + 0.04 * sosfilt(chest, audio)
        + 0.025 * sosfilt(presence, audio)
    ).astype(np.float32)

    fade = min(int(sample_rate * 0.01), audio.size // 2)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        audio[:fade] *= ramp
        audio[-fade:] *= ramp[::-1]

    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio *= 0.95 / peak

    target_rate = 44100
    if sample_rate != target_rate:
        ratio = Fraction(target_rate, sample_rate).limit_denominator()
        audio = resample_poly(audio, ratio.numerator, ratio.denominator)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, audio.astype(np.float32), target_rate, subtype="PCM_24")


def validate_generation_params(
    *,
    emo_alpha: float,
    duration_factor: float,
    temperature: float,
    top_p: float,
    top_k: int,
    repetition_penalty: float,
    max_text_tokens_per_segment: int,
    interval_silence: int,
    emo_vector: list[float] | None,
) -> None:
    if not 0.0 <= emo_alpha <= 1.0:
        raise ValueError("emo_alpha must be between 0 and 1")
    if not 0.25 <= duration_factor <= 3.0:
        raise ValueError("duration_factor must be between 0.25 and 3.0")
    if not 0.1 <= temperature <= 2.0:
        raise ValueError("temperature must be between 0.1 and 2.0")
    if not 0.0 < top_p <= 1.0:
        raise ValueError("top_p must be greater than 0 and at most 1")
    if not 1 <= top_k <= 1000:
        raise ValueError("top_k must be between 1 and 1000")
    if not 0.1 <= repetition_penalty <= 30.0:
        raise ValueError("repetition_penalty must be between 0.1 and 30")
    if not 1 <= max_text_tokens_per_segment <= 1000:
        raise ValueError(
            "max_text_tokens_per_segment must be between 1 and 1000"
        )
    if not 0 <= interval_silence <= 5000:
        raise ValueError("interval_silence must be between 0 and 5000 ms")
    if emo_vector is not None:
        if len(emo_vector) != 8:
            raise ValueError("emo_vector must contain exactly 8 numbers")
        if any(value < 0.0 or value > 1.0 for value in emo_vector):
            raise ValueError("emo_vector values must be between 0 and 1")


def inspect_reference(path: Path, label: str) -> None:
    try:
        info = sf.info(path)
    except Exception as exc:
        print(
            f"WARNING: {label} is not readable as WAV/FLAC: {exc}. "
            "Run prepare_reference.py first.",
            file=sys.stderr,
        )
        return

    duration = info.frames / info.samplerate if info.samplerate else 0.0
    if duration < 3:
        raise ValueError(
            f"{label} is only {duration:.1f}s; use a 5-15s clean speech clip"
        )
    if duration < 5:
        print(
            f"WARNING: {label} is only {duration:.1f}s; 10-15s is preferred.",
            file=sys.stderr,
        )
    if duration > 30:
        print(
            f"WARNING: {label} is {duration:.1f}s; IndexTTS may use only the "
            "beginning. Prefer a 10-15s window.",
            file=sys.stderr,
        )
    if info.channels > 1:
        print(
            f"WARNING: {label} has {info.channels} channels; mono is preferred.",
            file=sys.stderr,
        )
    if info.samplerate < 16000:
        print(
            f"WARNING: {label} is {info.samplerate} Hz; 16-44.1 kHz is preferred.",
            file=sys.stderr,
        )

    if duration <= 60:
        audio, _ = sf.read(path, dtype="float32", always_2d=True)
        clipped = float(np.mean(np.abs(audio) >= 0.999))
        if clipped > 0.001:
            print(
                f"WARNING: {label} contains clipped samples ({clipped:.1%}).",
                file=sys.stderr,
            )


def load_text(args: argparse.Namespace) -> tuple[str | None, list[dict[str, Any]]]:
    if args.text is not None:
        return args.text.strip(), []
    if args.text_file is not None:
        try:
            return args.text_file.read_text(encoding="utf-8").strip(), []
        except (OSError, UnicodeError) as exc:
            raise SystemExit(f"Could not read text file: {exc}") from exc
    if args.manifest is not None:
        items: list[dict[str, Any]] = []
        try:
            lines = args.manifest.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise SystemExit(f"Could not read manifest: {exc}") from exc
        for line_number, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"Invalid JSON on manifest line {line_number}: {exc}"
                ) from exc
            if not isinstance(item, dict):
                raise SystemExit(
                    f"Manifest line {line_number} must be a JSON object"
                )
            items.append(item)
        if not items:
            raise SystemExit("Manifest contains no usable items")
        return None, items
    raise SystemExit("Provide --text, --text-file, or --manifest")


def manifest_value(
    item: dict[str, Any],
    key: str,
    default: Any,
    cast: type,
    index: int,
) -> Any:
    value = item.get(key, default)
    try:
        return cast(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"Manifest item {index}: invalid {key}={value!r}"
        ) from exc


def safe_manifest_output(root: Path, name: Any, index: int) -> Path:
    if not isinstance(name, str) or not name.strip():
        raise SystemExit(f"Manifest item {index}: output must be a file name")
    relative = Path(name)
    if relative.is_absolute():
        raise SystemExit(
            f"Manifest item {index}: output must be relative to the output directory"
        )
    root_resolved = root.resolve()
    candidate = (root_resolved / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise SystemExit(
            f"Manifest item {index}: output escapes the output directory"
        ) from exc
    if candidate.suffix.lower() != ".wav":
        raise SystemExit(f"Manifest item {index}: output must end in .wav")
    return candidate


def manifest_vector(value: Any, index: int) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise SystemExit(f"Manifest item {index}: emo_vector must be a list")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"Manifest item {index}: emo_vector values must be numbers"
        ) from exc


def normalize_manifest(
    raw_items: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    if args.output.exists() and not args.output.is_dir():
        raise SystemExit(f"Batch output exists and is not a directory: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    normalized: list[dict[str, Any]] = []
    outputs: set[Path] = set()
    protected = {args.voice.resolve(), args.style_reference.resolve()}

    for index, item in enumerate(raw_items, 1):
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise SystemExit(f"Manifest item {index}: text must be a non-empty string")

        output = safe_manifest_output(
            args.output, item.get("output", f"line_{index:03d}.wav"), index
        )
        if output in outputs:
            raise SystemExit(
                f"Manifest item {index}: duplicate output path {output}"
            )
        if output in protected:
            raise SystemExit(
                f"Manifest item {index}: output would overwrite a reference file"
            )
        raw_output = output.with_name(output.stem + ".raw.wav")
        if not args.no_master and raw_output in protected:
            raise SystemExit(
                f"Manifest item {index}: intermediate WAV would overwrite a reference file"
            )
        outputs.add(output)

        emo_vector = manifest_vector(
            item.get("emo_vector", args.emo_vector), index
        )

        params = {
            "text": text.strip(),
            "output": output,
            "emo_alpha": manifest_value(
                item, "emo_alpha", args.emo_alpha, float, index
            ),
            "duration_factor": manifest_value(
                item, "duration_factor", args.duration_factor, float, index
            ),
            "temperature": manifest_value(
                item, "temperature", args.temperature, float, index
            ),
            "top_p": manifest_value(item, "top_p", args.top_p, float, index),
            "top_k": manifest_value(item, "top_k", args.top_k, int, index),
            "repetition_penalty": manifest_value(
                item,
                "repetition_penalty",
                args.repetition_penalty,
                float,
                index,
            ),
            "lang": str(item.get("lang", args.lang)).upper(),
            "emo_vector": emo_vector,
        }
        try:
            validate_generation_params(
                emo_alpha=params["emo_alpha"],
                duration_factor=params["duration_factor"],
                temperature=params["temperature"],
                top_p=params["top_p"],
                top_k=params["top_k"],
                repetition_penalty=params["repetition_penalty"],
                max_text_tokens_per_segment=args.max_text_tokens_per_segment,
                interval_silence=args.interval_silence,
                emo_vector=params["emo_vector"],
            )
        except ValueError as exc:
            raise SystemExit(f"Manifest item {index}: {exc}") from exc
        normalized.append(params)
    return normalized


def parse_emo_vector(value: str | None) -> list[float] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError("emo-vector must be a JSON list") from exc
    if not isinstance(parsed, list):
        raise argparse.ArgumentTypeError("emo-vector must be a JSON list")
    try:
        return [float(item) for item in parsed]
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            "emo-vector values must be numbers"
        ) from exc


def write_report(
    path: Path,
    results: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indextts_root": str(ROOT),
        "results": results,
        "failures": failures,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TTS with your own voice and a Zhang Gousheng-style reference."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--text-file", type=Path)
    source.add_argument("--manifest", type=Path)
    parser.add_argument("--voice", required=True, type=Path)
    parser.add_argument(
        "--style-reference",
        type=Path,
        default=DEFAULT_STYLE,
        help="10-15 second target-style clip used as emo_audio_prompt.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--lang", default="ZH")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--emo-alpha", type=float, default=0.55)
    parser.add_argument("--duration-factor", type=float, default=1.10)
    parser.add_argument("--temperature", type=float, default=0.86)
    parser.add_argument("--top-p", type=float, default=0.91)
    parser.add_argument("--top-k", type=int, default=45)
    parser.add_argument("--repetition-penalty", type=float, default=8.2)
    parser.add_argument(
        "--max-text-tokens-per-segment", type=int, default=300
    )
    parser.add_argument("--interval-silence", type=int, default=200)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--emo-vector",
        type=parse_emo_vector,
        default=None,
        help="Optional 8-number JSON emotion vector.",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="Keep the unmastered .raw.wav intermediate.",
    )
    parser.add_argument("--no-master", action="store_true")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue batch generation after an individual item fails.",
    )
    args = parser.parse_args()

    args.voice = absolute_path(args.voice)
    args.style_reference = absolute_path(args.style_reference)
    args.output = absolute_path(args.output)
    if args.report is not None:
        args.report = absolute_path(args.report)
    if args.text_file is not None:
        args.text_file = absolute_path(args.text_file)
    if args.manifest is not None:
        args.manifest = absolute_path(args.manifest)

    if not args.voice.exists():
        raise SystemExit(f"Voice reference not found: {args.voice}")
    if not args.style_reference.exists():
        raise SystemExit(
            "Style reference not found: "
            f"{args.style_reference}\n"
            "Prepare one with prepare_reference.py or pass --style-reference."
        )
    if args.voice.resolve() == args.style_reference.resolve():
        raise SystemExit(
            "Voice and style reference must be different files: "
            "voice supplies timbre; style supplies delivery."
        )
    protected_paths = {args.voice.resolve(), args.style_reference.resolve()}
    if args.report is not None and args.report.resolve() in protected_paths:
        raise SystemExit("--report would overwrite a reference file")
    if not (ROOT / "checkpoints").is_dir():
        raise SystemExit(
            f"IndexTTS checkpoints not found under {ROOT}. "
            "Set INDEXTTS_ROOT to the index-tts repository."
        )
    if not args.lang.strip():
        raise SystemExit("--lang cannot be empty")

    try:
        validate_generation_params(
            emo_alpha=args.emo_alpha,
            duration_factor=args.duration_factor,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            repetition_penalty=args.repetition_penalty,
            max_text_tokens_per_segment=args.max_text_tokens_per_segment,
            interval_silence=args.interval_silence,
            emo_vector=args.emo_vector,
        )
        inspect_reference(args.voice, "Voice reference")
        inspect_reference(args.style_reference, "Style reference")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    text, raw_manifest = load_text(args)
    if text is not None and not text:
        raise SystemExit("Text is empty")

    if text is not None:
        if args.output.suffix.lower() != ".wav":
            raise SystemExit("--output must end in .wav for single-text mode")
        if args.output.resolve() in {
            args.voice.resolve(),
            args.style_reference.resolve(),
        }:
            raise SystemExit("Output would overwrite a reference file")
        raw_output = args.output.with_name(args.output.stem + ".raw.wav")
        if not args.no_master and raw_output.resolve() in protected_paths:
            raise SystemExit(
                "Intermediate .raw.wav would overwrite a reference file"
            )
        jobs = [
            {
                "text": text,
                "output": args.output,
                "emo_alpha": args.emo_alpha,
                "duration_factor": args.duration_factor,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "top_k": args.top_k,
                "repetition_penalty": args.repetition_penalty,
                "lang": args.lang.upper(),
                "emo_vector": args.emo_vector,
            }
        ]
    else:
        jobs = normalize_manifest(raw_manifest, args)

    env_report = check_environment(ROOT, deep=False)
    env_errors = [
        item for item in env_report["checks"] if item["status"] == "error"
    ]
    if env_errors:
        print(json.dumps(env_report, ensure_ascii=False, indent=2))
        raise SystemExit(
            "Environment check failed. Run "
            f"{Path(__file__).with_name('setup_env.sh')} --check "
            "or fix the errors above."
        )

    if args.seed is not None:
        import torch

        torch.manual_seed(args.seed)

    os.chdir(ROOT)
    print(f">> loading IndexTTS-2.5 on {args.device}", flush=True)
    try:
        from indextts.infer_v2_5 import IndexTTS2
    except Exception as exc:
        raise SystemExit(
            "Could not import IndexTTS. Run "
            f"{Path(__file__).with_name('check_env.py')} --deep "
            f"and follow the fix suggestions.\n{type(exc).__name__}: {exc}"
        ) from exc

    tts = IndexTTS2(
        cfg_path=str(ROOT / "checkpoints/config.yaml"),
        model_dir=str(ROOT / "checkpoints"),
        device=args.device,
        use_qwen_emo=False,
    )
    model_version = getattr(tts, "model_version", None)

    def render(job: dict[str, Any]) -> dict[str, Any]:
        output_path: Path = job["output"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path = output_path
        if not args.no_master:
            raw_path = output_path.with_name(output_path.stem + ".raw.wav")

        tts.infer(
            spk_audio_prompt=str(args.voice),
            text=job["text"],
            lang=job["lang"],
            output_path=str(raw_path),
            emo_audio_prompt=str(args.style_reference),
            emo_alpha=job["emo_alpha"],
            emo_vector=job["emo_vector"],
            duration_factor=job["duration_factor"],
            max_text_tokens_per_segment=args.max_text_tokens_per_segment,
            interval_silence=args.interval_silence,
            text_normalization=True,
            temperature=job["temperature"],
            top_p=job["top_p"],
            top_k=job["top_k"],
            repetition_penalty=job["repetition_penalty"],
            verbose=False,
        )
        if not args.no_master:
            master_audio(raw_path, output_path)
            if not args.keep_raw:
                raw_path.unlink(missing_ok=True)

        audio, sample_rate = sf.read(output_path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        result = {
            "output": str(output_path),
            "text": job["text"],
            "duration_seconds": round(len(audio) / sample_rate, 2),
            "sample_rate": sample_rate,
            "peak": round(float(np.max(np.abs(audio))), 3),
            "parameters": {
                "model_version": model_version,
                "voice": str(args.voice),
                "style_reference": str(args.style_reference),
                "device": args.device,
                "lang": job["lang"],
                "emo_alpha": job["emo_alpha"],
                "emo_vector": job["emo_vector"],
                "duration_factor": job["duration_factor"],
                "temperature": job["temperature"],
                "top_p": job["top_p"],
                "top_k": job["top_k"],
                "repetition_penalty": job["repetition_penalty"],
                "max_text_tokens_per_segment": args.max_text_tokens_per_segment,
                "interval_silence": args.interval_silence,
                "seed": args.seed,
                "mastered": not args.no_master,
                "keep_raw": args.keep_raw,
            },
        }
        if args.keep_raw and not args.no_master:
            result["raw_output"] = str(raw_path)
        return result

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    total = len(jobs)
    for index, job in enumerate(jobs, 1):
        print(f">> generating {index}/{total}: {job['output']}", flush=True)
        try:
            results.append(render(job))
        except Exception as exc:
            failure = {
                "output": str(job["output"]),
                "text": job["text"][:120],
                "error": f"{type(exc).__name__}: {exc}",
            }
            failures.append(failure)
            print(f"ERROR {job['output']}: {failure['error']}", file=sys.stderr)
            if not args.continue_on_error:
                break

    if args.report is None and args.manifest is not None:
        args.report = args.output / "generation_report.json"
    if args.report is not None:
        write_report(args.report, results, failures)
        print(f">> report: {args.report}", flush=True)

    print(
        json.dumps(
            {"results": results, "failures": failures},
            ensure_ascii=False,
            indent=2,
        )
    )
    if not results:
        raise SystemExit("No audio was generated")
    if failures and not args.continue_on_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
