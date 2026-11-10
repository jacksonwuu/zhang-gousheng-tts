# Installation and Environment

The skill has two separate environments:

1. The skill project: Markdown + Python scripts in a checkout such as
   `~/code/zhang-gousheng-tts`. The global skill directory should link to this
   project so Codex can discover it.
2. The IndexTTS runtime: a cloned `index-tts` repository with `uv`, `.venv`, and IndexTTS-2.5 checkpoints.

Do not install IndexTTS into the system Python. Use `uv`.

Set writable tool caches before checking or generating:

```bash
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl-cache}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/numba-cache}"
```

`NUMBA_CACHE_DIR` is required when Codex or another sandbox prevents writes to
`.venv/lib/.../__pycache__`. Without it, importing `IndexTTS2` can fail with
`cannot cache function ... no locator available`.

## Before installing

Tell the user the resource cost and get explicit approval before running the
installer or downloading models:

- IndexTTS-2.5 checkpoints: about `8 GB`
- Python environment and caches: about `2-4 GB`
- Free disk space to reserve during install: at least `20 GB`
- RAM: `16 GB` practical minimum; `32 GB` or more preferred
- Model load can temporarily use several GB of memory
- CPU generation is roughly `5-8x` real time

The installer refuses non-interactive installation unless `--yes` is passed.
Only pass `--yes` after the user has approved the disk, memory, and runtime cost.
It also checks free disk space and refuses to continue below `20 GB` unless
`INDEXTTS_MIN_FREE_GB` is explicitly lowered.

## Model integrity and resume

The critical checkpoint files include the GPT model, semantic codec, S2Mel,
BigVGAN, CAM++, wav2vec2-BERT, tokenizer vocabulary, emotion matrices, and
wav2vec statistics. The environment check verifies presence and a conservative
minimum size, so a truncated download is reported as incomplete.

Model downloads are resumable. If the network fails, run the same download
command again instead of deleting `checkpoints/`. The installer always attempts
the download when `--download-models` is passed, even if `config.yaml` already
exists; this allows a partial checkpoint directory to repair itself.

## One-command check

```bash
export SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/zhang-gousheng-tts}"
python3 "$SKILL_DIR/scripts/check_env.py" \
  --deep
```

Or:

```bash
"$SKILL_DIR/scripts/setup_env.sh" --check
```

The check validates:

- Python 3.10+
- `uv`
- `ffmpeg` / `ffprobe`
- IndexTTS repository and `checkpoints/`
- critical model files and minimum plausible sizes
- `.venv`
- writable `outputs/`
- free disk space
- memory
- Python imports plus a real `indextts.infer_v2_5.IndexTTS2` import in deep mode

## macOS from scratch

```bash
brew install ffmpeg git
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/index-tts/index-tts.git
cd index-tts
export INDEXTTS_ROOT="$PWD"

uv sync --extra webui
uv tool install huggingface-hub
hf download IndexTeam/IndexTTS-2.5 --local-dir=checkpoints
```

If `hf` is not on `PATH` after `uv tool install`, follow the path hint printed by `uv tool`.

Then:

```bash
python3 "$SKILL_DIR/scripts/check_env.py" \
  --deep
```

## Linux from scratch

```bash
sudo apt update
sudo apt install -y ffmpeg git curl
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/index-tts/index-tts.git
cd index-tts
export INDEXTTS_ROOT="$PWD"

uv sync --extra webui
uv tool install huggingface-hub
hf download IndexTeam/IndexTTS-2.5 --local-dir=checkpoints
```

On a CPU-only Linux machine, use `--device cpu`. For CUDA acceleration, install
the optional extras explicitly after checking that the NVIDIA driver and CUDA
toolkit match the PyTorch build:

```bash
uv sync --extra webui --extra deepspeed --extra accel --extra torch-compile
```

## Windows

WSL2 is the least painful option. Install ffmpeg, git, uv and clone the repository inside WSL2, then run the same commands as Linux.

Native Windows may work for CPU inference, but DeepSpeed and some audio libraries are more fragile. Install only the WebUI extra:

```bash
uv sync --extra webui
```

## Slow downloads in China

Use a PyPI mirror:

```bash
uv sync --extra webui --default-index "https://mirrors.aliyun.com/pypi/simple"
# or
uv sync --extra webui --default-index "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
```

Use a HuggingFace mirror:

```bash
export HF_ENDPOINT="https://hf-mirror.com"
```

Or download models with ModelScope:

```bash
uv tool install modelscope
modelscope download --model IndexTeam/IndexTTS-2.5 --local_dir checkpoints
```

## Sandbox / permission errors

If `uv` reports `Operation not permitted` while creating a cache file, point its caches at a writable directory:

```bash
export UV_CACHE_DIR=/tmp/uv-cache
export MPLCONFIGDIR=/tmp/mpl-cache
```

This is common in Codex sandboxes and CI containers. The `check_env.py` deep check sets these defaults for its own subprocesses.

## Disk and model size

The IndexTTS-2.5 checkpoint directory is roughly 8 GB. The project environment
adds about 2 GB. Reserve at least 20 GB free during installation for downloads,
temporary files, and generated WAVs.

Use at least 16 GB RAM. 32 GB or more is preferable because model loading and
generation can temporarily use several GB. CPU inference is much slower than
real time.

To reclaim space, remove `.venv/` and rerun `uv sync` when needed, or delete
`checkpoints/` if the models will not be used. Generated takes are under the
IndexTTS repository's `outputs/` directory. Do not delete source files merely to
free space.

## Common failures

**`uv: command not found`**
Install uv and restart the shell:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**`ffmpeg not found`**

```bash
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Debian/Ubuntu
```

**`IndexTTS checkpoints not found`**
Set `INDEXTTS_ROOT` to the repository that contains `checkpoints/config.yaml`, or download the models into `checkpoints/`.

**MPS is available but inference fails**
Use CPU:

```bash
uv run --frozen python "$SKILL_DIR/scripts/generate.py" ... --device cpu
```

**`cannot cache function ... no locator available`**
Set a writable Numba cache and rerun:

```bash
export NUMBA_CACHE_DIR=/tmp/numba-cache
```

**Reference auto-selection picked music or another speaker**
The selector uses loudness, not speech recognition. It reports the chosen
window, speech ratio, clipping, and peak. Listen to the result and rerun with
`--start` when the source has music, multiple speakers, or long reverb.

**Generation is slow**
CPU inference is roughly 5–8x real time on this machine. A 30-second clip can take several minutes. This is expected.

**Model import fails**
Run the deep check:

```bash
python3 "$SKILL_DIR/scripts/check_env.py" --deep
```

Then run `uv sync --extra webui` in `INDEXTTS_ROOT`.
