# zhang-gousheng-tts

Chinese narration with **your own voice** and a fast, punchy, short-pause
news-explainer delivery inspired by the rhythm of "Zhang Gousheng", powered by
[IndexTTS 2.5](https://github.com/index-tts/index-tts).

[中文](README.md) | English

> **This is not a voice clone of Zhang Gousheng.** The project reproduces only
> rhythm, pauses, dynamics, and delivery. `spk_audio_prompt` must be your own
> voice or a voice you are explicitly authorized to use. Do not impersonate real
> people or generate deceptive content.

## Features

- Extract a clean 5–15 second speech reference from video or audio
- Combine your own timbre with a separate emotion/style reference
- Tune `emo_alpha`, duration, sampling, repetition penalty, and emotion vectors
- Batch-generate from JSONL with per-line parameter overrides
- Persist complete generation reports for reproducibility
- Analyze F0, pauses, dynamics, spectral centroid, and LUFS/LRA
- Validate disk, memory, checkpoint completeness, and inference imports

## Resource warning

Ask the user for confirmation before installing:

| Resource | Requirement |
|---|---:|
| IndexTTS-2.5 checkpoints | about 8 GB |
| Python environment and caches | about 2–4 GB |
| Free disk during installation | at least 20 GB |
| RAM | 16 GB practical minimum, 32 GB preferred |
| CPU generation | roughly 5–8× real time |

The installer refuses non-interactive installation unless `--yes` is passed and
stops when free disk is below 20 GB.

## Install

```bash
git clone https://github.com/jacksonwuu/zhang-gousheng-tts.git \
  "$HOME/code/zhang-gousheng-tts"
mkdir -p "$HOME/.codex/skills"
ln -sfn "$HOME/code/zhang-gousheng-tts" \
  "$HOME/.codex/skills/zhang-gousheng-tts"

git clone https://github.com/index-tts/index-tts.git "$HOME/index-tts"

export INDEXTTS_ROOT="$HOME/index-tts"
export SKILL_DIR="$HOME/.codex/skills/zhang-gousheng-tts"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl-cache}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/numba-cache}"

"$SKILL_DIR/scripts/setup_env.sh" \
  --root "$INDEXTTS_ROOT" \
  --download-models \
  --yes
```

On macOS, use `uv sync --extra webui`; do not use `--all-extras` because it may
resolve NVIDIA CUDA packages.

## Usage

```bash
cd "$INDEXTTS_ROOT"

uv run --frozen python "$SKILL_DIR/scripts/prepare_reference.py" \
  --input "/path/to/user-video.mov" \
  --output "outputs/voice_samples/user_voice_15s.wav"

uv run --frozen python "$SKILL_DIR/scripts/prepare_reference.py" \
  --input "/path/to/authorized-style-source.wav" \
  --output "/tmp/zhang_style_15s.wav"

uv run --frozen python "$SKILL_DIR/scripts/generate.py" \
  --text "This is a Chinese TTS test." \
  --voice "outputs/voice_samples/user_voice_15s.wav" \
  --style-reference "/tmp/zhang_style_15s.wav" \
  --output "outputs/voice_samples/demo.wav" \
  --report "outputs/voice_samples/demo.json" \
  --lang ZH
```

The intermediate `.raw.wav` is removed after successful mastering. Use
`--keep-raw` for debugging. Batch mode reads JSONL, loads the model once, accepts
per-line overrides, and writes `generation_report.json`.

See [README.md](README.md) for the full Chinese guide, parameter table, privacy
notes, and troubleshooting.

## Privacy and licensing

Voice samples are biometric data. Keep references and generated audio private.
The repository does not include model weights, source videos, user voices, or
generated audio. IndexTTS and its weights are governed by their upstream
licenses. This repository's code and documentation are MIT licensed.
