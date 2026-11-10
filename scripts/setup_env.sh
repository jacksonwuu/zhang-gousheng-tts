#!/usr/bin/env bash
set -euo pipefail

ROOT="${INDEXTTS_ROOT:-}"
MIRROR=""
DOWNLOAD_MODELS=0
CHECK_ONLY=0
ASSUME_YES=0

usage() {
  cat <<'EOF'
Usage:
  setup_env.sh [--root PATH] [--mirror aliyun|tuna] [--download-models] [--yes] [--check]

Examples:
  setup_env.sh --check
  setup_env.sh
  setup_env.sh --mirror aliyun
  setup_env.sh --download-models
  setup_env.sh --download-models --yes
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --mirror)
      MIRROR="$2"
      shift 2
      ;;
    --download-models)
      DOWNLOAD_MODELS=1
      shift
      ;;
    --check)
      CHECK_ONLY=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl-cache}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/numba-cache}"
for bin_dir in \
  "$HOME/.local/bin" \
  /opt/homebrew/bin \
  /usr/local/bin \
  "$HOME/miniforge3/bin" \
  "$HOME/miniconda3/bin" \
  "$HOME/opt/anaconda3/bin"; do
  if [[ -d "$bin_dir" ]]; then
    PATH="$bin_dir:$PATH"
  fi
done
export PATH

if [[ -z "$ROOT" ]]; then
  for candidate in \
    "$HOME/Desktop/repo/index-tts" \
    "$HOME/index-tts" \
    "$PWD/index-tts" \
    "$PWD"; do
    if [[ -f "$candidate/pyproject.toml" ]]; then
      ROOT="$candidate"
      break
    fi
  done
  ROOT="${ROOT:-$HOME/index-tts}"
fi

if [[ "$CHECK_ONLY" == "1" ]]; then
  python3 "$SCRIPT_DIR/check_env.py" --root "$ROOT" --deep
  exit $?
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is not installed." >&2
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "  # or: pip install -U uv" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 && [[ -z "${FFMPEG_BIN:-}" ]]; then
  echo "ERROR: ffmpeg is not installed." >&2
  echo "  macOS: brew install ffmpeg" >&2
  echo "  Debian/Ubuntu: sudo apt install ffmpeg" >&2
  echo "  Or set FFMPEG_BIN to the ffmpeg executable." >&2
  exit 1
fi

if [[ ! -f "$ROOT/pyproject.toml" ]]; then
  echo "ERROR: IndexTTS repository not found at: $ROOT" >&2
  echo "  git clone https://github.com/index-tts/index-tts.git" >&2
  echo "  export INDEXTTS_ROOT=/path/to/index-tts" >&2
  exit 1
fi

if [[ "$ASSUME_YES" != "1" ]]; then
  cat <<'EOF'
Resource requirements for IndexTTS:
  - IndexTTS-2.5 checkpoints: about 8 GB
  - Python environment and caches: about 2-4 GB
  - Reserve at least 20 GB free during installation
  - Recommended RAM: 16 GB minimum; 32 GB or more preferred
  - Model loading can temporarily use several GB of memory
  - CPU generation is roughly 5-8x real time; a 30-second clip may take minutes

Do not install on a nearly full or memory-constrained machine.
EOF
  required_gb="${INDEXTTS_MIN_FREE_GB:-20}"
  free_kb="$(df -Pk "$ROOT" | awk 'NR == 2 {print $4}')"
  if [[ -z "$free_kb" ]]; then
    echo "ERROR: could not determine free disk space for $ROOT" >&2
    exit 1
  fi
  free_gb=$((free_kb / 1024 / 1024))
  if (( free_gb < required_gb )); then
    echo "ERROR: only ${free_gb} GB free; installation needs ${required_gb} GB." >&2
    echo "  Free space or set INDEXTTS_MIN_FREE_GB to an explicit lower value." >&2
    exit 1
  fi
  if [[ ! -t 0 ]]; then
    echo "ERROR: installation needs explicit consent." >&2
    echo "  Tell the user about the disk, memory, and runtime costs first." >&2
    echo "  Then rerun with --yes after they approve." >&2
    exit 3
  fi
  printf "Continue with installation? [y/N] "
  read -r reply
  case "$reply" in
    y|Y|yes|YES) ;;
    *)
      echo "Installation cancelled."
      exit 1
      ;;
  esac
fi

cd "$ROOT"

echo ">> installing Python dependencies with uv"
SYNC_EXTRAS=(--extra webui)
case "$MIRROR" in
  "")
    uv sync "${SYNC_EXTRAS[@]}"
    ;;
  aliyun)
    uv sync "${SYNC_EXTRAS[@]}" --default-index "https://mirrors.aliyun.com/pypi/simple"
    ;;
  tuna)
    uv sync "${SYNC_EXTRAS[@]}" --default-index "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
    ;;
  *)
    echo "ERROR: unsupported mirror: $MIRROR" >&2
    exit 2
    ;;
esac

if [[ "$DOWNLOAD_MODELS" == "1" ]]; then
  if command -v hf >/dev/null 2>&1; then
    echo ">> downloading IndexTTS-2.5 via HuggingFace"
    hf download IndexTeam/IndexTTS-2.5 --local-dir=checkpoints || {
      echo "ERROR: model download failed; rerun to resume." >&2
      exit 1
    }
  elif command -v huggingface-cli >/dev/null 2>&1; then
    echo ">> downloading IndexTTS-2.5 via HuggingFace CLI"
    huggingface-cli download IndexTeam/IndexTTS-2.5 --local-dir checkpoints || {
      echo "ERROR: model download failed; rerun to resume." >&2
      exit 1
    }
  elif command -v modelscope >/dev/null 2>&1; then
    echo ">> downloading IndexTTS-2.5 via ModelScope"
    modelscope download --model IndexTeam/IndexTTS-2.5 --local_dir checkpoints || {
      echo "ERROR: model download failed; rerun to resume." >&2
      exit 1
    }
  else
    echo "ERROR: no model downloader found." >&2
    echo "  uv tool install huggingface-hub" >&2
    echo "  hf download IndexTeam/IndexTTS-2.5 --local-dir=checkpoints" >&2
    echo "  # or: uv tool install modelscope" >&2
    exit 1
  fi
fi

echo ">> running environment check"
python3 "$SCRIPT_DIR/check_env.py" --root "$ROOT" --deep
