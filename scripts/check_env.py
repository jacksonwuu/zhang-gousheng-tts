#!/usr/bin/env python3
"""Preflight check for the zhang-gousheng-tts skill.

This script uses only the Python standard library so it can run before the
IndexTTS virtual environment is ready.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


CORE_FILES = {
    "pyproject.toml": 1_000,
    "checkpoints/config.yaml": 1_000,
    "checkpoints/feat1.pt": 20_000,
    "checkpoints/feat2.pt": 100_000,
    "checkpoints/gpt.pth": 3_000_000_000,
    "checkpoints/s2mel.pth": 300_000_000,
    "checkpoints/codec.pth": 500_000_000,
    "checkpoints/pinyin.vocab": 5_000,
    "checkpoints/multilingual_zh_ja_yue_char_del.tiktoken": 500_000,
    "checkpoints/wav2vec2bert_stats.pt": 5_000,
    "checkpoints/hf_cache/bigvgan/bigvgan_generator.pt": 400_000_000,
    "checkpoints/hf_cache/bigvgan/config.json": 500,
    "checkpoints/hf_cache/campplus_cn_common.bin": 20_000_000,
    "checkpoints/hf_cache/semantic_codec_model.safetensors": 150_000_000,
    "checkpoints/hf_cache/w2v-bert-2.0/config.json": 500,
    "checkpoints/hf_cache/w2v-bert-2.0/model.safetensors": 2_000_000_000,
    "checkpoints/hf_cache/w2v-bert-2.0/preprocessor_config.json": 100,
}

OPTIONAL_FILES = {
    "checkpoints/qwen0.6bemo4-merge/config.json": 500,
    "checkpoints/qwen0.6bemo4-merge/model.safetensors": 500_000_000,
    "checkpoints/qwen0.6bemo4-merge/tokenizer.json": 1_000_000,
    "checkpoints/qwen0.6bemo4-merge/tokenizer_config.json": 1_000,
}


def default_indextts_root() -> Path:
    configured = os.environ.get("INDEXTTS_ROOT")
    if configured:
        return Path(configured).expanduser()
    candidates = [
        Path.home() / "Desktop/repo/index-tts",
        Path.home() / "index-tts",
        Path.cwd() / "index-tts",
        Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.home() / "index-tts"


def which(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    candidates = [
        Path.home() / ".local/bin" / name,
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
        Path.home() / "miniforge3/bin" / name,
        Path.home() / "miniconda3/bin" / name,
        Path.home() / "opt/anaconda3/bin" / name,
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def version_line(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0] if text else None


def parse_version(text: str | None) -> tuple[int, int] | None:
    match = re.search(r"(\d+)\.(\d+)", text or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def total_memory_gb() -> float | None:
    try:
        return (
            os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        ) / (1024**3)
    except (AttributeError, OSError, ValueError):
        return None


def check_environment(root: Path, deep: bool = False) -> dict:
    checks: list[dict] = []
    subprocess_env = os.environ.copy()
    subprocess_env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
    subprocess_env.setdefault("MPLCONFIGDIR", "/tmp/mpl-cache")
    subprocess_env.setdefault("NUMBA_CACHE_DIR", "/tmp/numba-cache")

    def add(
        name: str,
        status: str,
        detail: str,
        fix: str | None = None,
    ) -> None:
        checks.append(
            {
                "name": name,
                "status": status,
                "detail": detail,
                "fix": fix,
            }
        )

    uv = os.environ.get("UV_BIN") or which("uv")
    if uv:
        add("uv", "ok", version_line([uv, "--version"]) or uv)
    else:
        add(
            "uv",
            "error",
            "uv not found",
            "Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` "
            "or `pip install -U uv`.",
        )

    project_python = root / (
        ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"
    )
    project_version = None
    if project_python.exists():
        project_version = parse_version(
            version_line([str(project_python), "--version"])
        )
        if project_version and project_version >= (3, 10):
            add(
                "project_python",
                "ok",
                version_line([str(project_python), "--version"]) or str(project_python),
            )
        else:
            add(
                "project_python",
                "error",
                f"project Python is {project_version or 'unknown'}; need 3.10+",
                "Remove/recreate `.venv` or run `uv sync --extra webui`.",
            )
    else:
        add(
            "project_python",
            "warning",
            "project .venv Python not found",
            "Run `cd <INDEXTTS_ROOT> && uv sync --extra webui`.",
        )

    launcher_python = platform.python_version()
    if sys.version_info >= (3, 10):
        add("launcher_python", "ok", f"Python {launcher_python}")
    elif project_version and project_version >= (3, 10):
        add(
            "launcher_python",
            "ok",
            f"launcher Python {launcher_python}; project Python "
            f"{project_version[0]}.{project_version[1]} is used",
        )
    elif uv:
        add(
            "launcher_python",
            "warning",
            f"launcher Python {launcher_python} is below 3.10; "
            "the project .venv should provide 3.10+",
            "Run `uv sync --extra webui`; the check will use .venv Python.",
        )
    else:
        add(
            "launcher_python",
            "error",
            f"Python {launcher_python}; need 3.10+",
            "Install Python 3.11/3.12, or let `uv sync` install it.",
        )

    ffmpeg = os.environ.get("FFMPEG_BIN") or which("ffmpeg")
    if ffmpeg:
        add("ffmpeg", "ok", version_line([ffmpeg, "-version"]) or ffmpeg)
    else:
        add(
            "ffmpeg",
            "error",
            "ffmpeg not found",
            "macOS: `brew install ffmpeg`; Debian/Ubuntu: "
            "`sudo apt install ffmpeg`; or set `FFMPEG_BIN`.",
        )

    ffprobe = which("ffprobe")
    if ffprobe:
        add("ffprobe", "ok", version_line([ffprobe, "-version"]) or ffprobe)
    else:
        add(
            "ffprobe",
            "warning",
            "ffprobe not found; ffmpeg can still work for most inputs",
            "Install ffmpeg/ffprobe together.",
        )

    if not root.exists():
        add(
            "indextts_root",
            "error",
            f"IndexTTS repository not found: {root}",
            "Set `INDEXTTS_ROOT` or clone "
            "`https://github.com/index-tts/index-tts.git`.",
        )
        return {
            "root": str(root),
            "ok": False,
            "checks": checks,
        }

    add("indextts_root", "ok", str(root))

    for relative, minimum_size in CORE_FILES.items():
        path = root / relative
        if path.exists():
            size = path.stat().st_size
            if size < minimum_size:
                add(
                    f"file:{relative}",
                    "error",
                    f"suspiciously small: {size} bytes",
                    "The download is incomplete or corrupt. Re-run the model download.",
                )
            else:
                add(f"file:{relative}", "ok", f"{size} bytes")
        else:
            fix = (
                "Download IndexTTS-2.5 models: "
                "`uv tool install huggingface-hub && "
                "hf download IndexTeam/IndexTTS-2.5 --local-dir=checkpoints`."
            )
            add(f"file:{relative}", "error", "missing", fix)

    for relative, minimum_size in OPTIONAL_FILES.items():
        path = root / relative
        if path.exists() and path.stat().st_size >= minimum_size:
            add(f"optional:{relative}", "ok", "present")
        else:
            add(
                f"optional:{relative}",
                "warning",
                "missing or incomplete",
                "Only needed for QwenEmotion; re-download the full checkpoint.",
            )

    checkpoints = root / "checkpoints"
    if checkpoints.exists():
        installed_bytes = sum(
            path.stat().st_size
            for path in checkpoints.rglob("*")
            if path.is_file()
        )
        add("model_storage", "ok", f"{installed_bytes / (1024**3):.1f} GB installed")

    venv = root / ".venv"
    if venv.exists():
        add("venv", "ok", str(venv))
    else:
        add(
            "venv",
            "warning",
            ".venv not found",
            "Run `cd <INDEXTTS_ROOT> && uv sync --extra webui`.",
        )

    outputs = root / "outputs"
    if outputs.exists():
        if os.access(outputs, os.W_OK):
            add("outputs", "ok", str(outputs))
        else:
            add(
                "outputs",
                "warning",
                "outputs exists but is not writable from this process",
                "Write to /tmp or run the command outside the sandbox.",
            )
    elif root.exists() and os.access(root, os.W_OK):
        add(
            "outputs",
            "warning",
            "outputs directory is missing; it can be created on demand",
            None,
        )
    else:
        add(
            "outputs",
            "warning",
            "outputs is not writable from this process; a sandbox may be blocking writes",
            "Write to /tmp or run the command outside the sandbox.",
        )

    if root.exists():
        free_gb = shutil.disk_usage(root).free / (1024**3)
        status = "ok" if free_gb >= 20 else "warning"
        add(
            "disk_space",
            status,
            f"{free_gb:.1f} GB free; installation needs about 20 GB",
            None
            if status == "ok"
            else "Free at least 20 GB before installing models and dependencies.",
        )

    memory_gb = total_memory_gb()
    if memory_gb is not None:
        status = "ok" if memory_gb >= 16 else "warning"
        add(
            "memory",
            status,
            f"{memory_gb:.0f} GB RAM",
            None
            if status == "ok"
            else "16 GB RAM is the practical minimum; CPU inference may be slow.",
        )

    if deep:
        if uv:
            code = (
                "import numpy, scipy, soundfile, librosa, torch; "
                "print('python deps ok')"
            )
            try:
                result = subprocess.run(
                    [uv, "run", "--frozen", "python", "-c", code],
                    cwd=root,
                    env=subprocess_env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                if result.returncode == 0:
                    add("python_deps", "ok", result.stdout.strip())
                else:
                    add(
                        "python_deps",
                        "error",
                        (result.stderr or result.stdout).strip()[-800:],
                        "Run `cd <INDEXTTS_ROOT> && uv sync --extra webui`.",
                    )
            except subprocess.TimeoutExpired:
                add("python_deps", "error", "dependency check timed out")
        else:
            add("python_deps", "error", "cannot check without uv")

        if uv:
            code = (
                "import indextts; "
                "from indextts.infer_v2_5 import IndexTTS2; "
                "print('indextts inference import ok:', indextts.__file__)"
            )
            try:
                with tempfile.TemporaryDirectory(
                    prefix="indextts-import-"
                ) as temp_dir:
                    result = subprocess.run(
                        [
                            uv,
                            "run",
                            "--project",
                            str(root),
                            "--frozen",
                            "python",
                            "-c",
                            code,
                        ],
                        cwd=temp_dir,
                        env=subprocess_env,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                    )
                if result.returncode == 0:
                    add("indextts_import", "ok", result.stdout.strip())
                else:
                    add(
                        "indextts_import",
                        "error",
                        (result.stderr or result.stdout).strip()[-800:],
                        "Run `uv sync --extra webui` and set INDEXTTS_ROOT correctly.",
                    )
            except subprocess.TimeoutExpired:
                add("indextts_import", "error", "import check timed out")

    errors = [item for item in checks if item["status"] == "error"]
    warnings = [item for item in checks if item["status"] == "warning"]
    return {
        "root": str(root),
        "ok": not errors,
        "errors": len(errors),
        "warnings": len(warnings),
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the TTS skill environment.")
    parser.add_argument(
        "--root",
        type=Path,
        default=default_indextts_root(),
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Also import Python dependencies and indextts inside uv.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = check_environment(args.root, deep=args.deep)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"IndexTTS root: {report['root']}")
        for item in report["checks"]:
            marker = {"ok": "OK", "warning": "WARN", "error": "ERROR"}[
                item["status"]
            ]
            print(f"[{marker}] {item['name']}: {item['detail']}")
            if item.get("fix"):
                print(f"       fix: {item['fix']}")
        print(
            f"\nResult: {'READY' if report['ok'] else 'NOT READY'} "
            f"({report['errors']} errors, {report['warnings']} warnings)"
        )

    raise SystemExit(0 if report["ok"] else 2)


if __name__ == "__main__":
    main()
