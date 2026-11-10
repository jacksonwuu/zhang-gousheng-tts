---
name: zhang-gousheng-tts
description: Generate Chinese narration with the user's own voice and a Zhang Gousheng-style rhythm using IndexTTS 2.5. Use this skill whenever the user asks to clone or reuse their own voice, turn a video/audio sample into a 10-15 second voice reference, generate TTS with a "张狗剩" or fast news-explainer style, batch-produce narration, or tune IndexTTS emotion, speed, and punch. Trigger even when the user does not explicitly say "skill"; if the task involves IndexTTS voice cloning or Zhang Gousheng-style delivery, use this skill first.
---

# Zhang Gousheng TTS

Turn the user's own voice into a fast, punchy, slightly wry news-explainer delivery. The user's voice supplies timbre; a separate style reference supplies rhythm and emotion. Do not confuse the two.

## Non-negotiable rules

- `spk_audio_prompt` must be the user's own voice or a voice they are authorized to clone.
- `emo_audio_prompt` is only a style/emotion reference. Never use the target style speaker as `spk_audio_prompt`.
- Do not impersonate a real person or generate deceptive content. For public output, confirm voice and style-reference rights.
- If the user provides a video, prefer extracting a clean 10-15 second speech window instead of feeding the whole video to IndexTTS.

## What this skill does

1. Extracts a clean reference clip from the user's video/audio.
2. Extracts or accepts a 10-15 second target-style clip.
3. Runs IndexTTS 2.5 with:
   - `spk_audio_prompt` = user's voice
   - `emo_audio_prompt` = Zhang Gousheng-style reference
   - `emo_alpha` = how strongly the style pushes the delivery
4. Masters the result to a 44.1 kHz / 24-bit WAV.
5. Measures duration, F0, pauses, dynamics, and optionally LUFS/LRA.

## Step 0: check the environment

Always run this before preparing references or generating audio:

```bash
export SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/zhang-gousheng-tts}"
python3 "$SKILL_DIR/scripts/check_env.py" \
  --deep
```

If it reports `NOT READY`, fix the listed items or run the guided installer:

Before running any installation or model download, tell the user:

- IndexTTS-2.5 checkpoints take about `8 GB`.
- The Python environment and caches take another `2-4 GB`; reserve at least `20 GB` free during installation.
- `16 GB` RAM is the practical minimum; `32 GB` or more is preferred.
- Loading the model temporarily uses several GB of memory.
- CPU generation is roughly `5-8x` real time, so a 30-second clip can take several minutes.

Get explicit approval before installing or downloading models. The installer
requires `--yes` after that approval:

```bash
"$SKILL_DIR/scripts/setup_env.sh" \
  --root "$INDEXTTS_ROOT"

# First-time install including model download, only after user approval:
"$SKILL_DIR/scripts/setup_env.sh" \
  --root "$INDEXTTS_ROOT" \
  --download-models \
  --yes
```

The check covers Python, `uv`, `ffmpeg`, the IndexTTS repository, critical
checkpoint files, `.venv`, disk space, memory, and a real import of the
inference module. Do not install IndexTTS with system `pip`; use `uv`.

## Environment

The scripts auto-detect a nearby `index-tts` checkout. If yours is elsewhere,
set it explicitly:

```bash
export INDEXTTS_ROOT="/path/to/index-tts"
export FFMPEG_BIN="/opt/homebrew/bin/ffmpeg"   # optional
export ZHANG_STYLE_REFERENCE="/path/to/style-reference.wav"  # optional
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl-cache}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/numba-cache}"
```

Run generation and analysis from the IndexTTS repository so `uv` can provide the model environment. See `references/installation.md` for macOS, Linux, Windows/WSL2, mirrors, and sandbox permission fixes.

## Quick start

Set paths:

```bash
# Use the root printed by check_env.py; override if necessary.
export INDEXTTS_ROOT="${INDEXTTS_ROOT:-$HOME/index-tts}"
export SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/zhang-gousheng-tts}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/numba-cache}"
cd "$INDEXTTS_ROOT"
```

### 1. Prepare the user's voice reference

```bash
uv run --frozen python "$SKILL_DIR/scripts/prepare_reference.py" \
  --input "/path/to/user-video.mov" \
  --output "outputs/voice_samples/zhang_style_test/user_voice_15s.wav"
```

The script converts the video to mono audio, finds the densest 15-second speech window, removes DC offset, normalizes the peak, and writes a 44.1 kHz / 24-bit WAV.

Auto-selection is based on loudness, not speech recognition. Background music,
multiple speakers, or heavy reverb can fool it. Audition the result; when the
source contains music or several voices, pass `--start` with a known clean
section. The script reports the selected time window, speech ratio, clipping,
and source peak.

### 2. Prepare the style reference

Use a 10-15 second clip of the target style. If the source is a longer file, the same script can extract a clean window:

```bash
uv run --frozen python "$SKILL_DIR/scripts/prepare_reference.py" \
  --input "/path/to/style-source.wav" \
  --output "/tmp/zhang_style_15s.wav"
```

For the first 15 seconds specifically:

```bash
uv run --frozen python "$SKILL_DIR/scripts/prepare_reference.py" \
  --input "/path/to/style-source.wav" \
  --output "/tmp/zhang_style_15s.wav" \
  --start 0
```

### 3. Generate TTS

```bash
uv run --frozen python "$SKILL_DIR/scripts/generate.py" \
  --text "很多人以为，声音克隆就是把一段录音丢给 AI，然后按下生成，完了。真不是。" \
  --voice "outputs/voice_samples/zhang_style_test/user_voice_15s.wav" \
  --style-reference "/tmp/zhang_style_15s.wav" \
  --output "outputs/voice_samples/zhang_style_test/demo.wav" \
  --report "outputs/voice_samples/zhang_style_test/demo.json"
```

The mastered WAV is written at 44.1 kHz / 24-bit. The intermediate
`.raw.wav` is deleted after successful mastering; pass `--keep-raw` when
debugging. The report records every parameter needed to reproduce the result.

### 4. Measure the result

```bash
uv run --frozen python "$SKILL_DIR/scripts/analyze_audio.py" \
  "outputs/voice_samples/zhang_style_test/demo.wav" \
  --text "很多人以为，声音克隆就是把一段录音丢给 AI，然后按下生成，完了。真不是。" \
  --loudnorm
```

Pass `--text` or `--text-file` to estimate spoken units per minute. Pitch
metrics are reported as `null` when the clip contains no detectable voicing.

Target ranges for this style:

- speech rate: `300-320` Chinese characters/minute
- F0: close to the user's own reference, not the target speaker's absolute pitch
- short pauses: many `200-500ms`, few over `500ms`
- dynamics: higher RMS variation than a flat read

## Recommended parameters

Defaults are tuned for the user's voice plus the Zhang Gousheng-style reference:

```text
emo_alpha = 0.55
duration_factor = 1.10
temperature = 0.86
top_p = 0.91
top_k = 45
repetition_penalty = 8.2
max_text_tokens_per_segment = 300
interval_silence = 200
```

Meaning:

- `emo_alpha` controls how much the style reference pushes the delivery.
- `duration_factor > 1` slows speech; `< 1` speeds it up.
- Higher `temperature` adds variation but can hurt pronunciation.
- Higher `repetition_penalty` reduces repeated or stuck sounds.

### Tuning table

| Symptom | First adjustment |
|---|---|
| Voice sounds too much like the style reference | lower `emo_alpha` to `0.35-0.45` |
| Delivery is flat or too polite | raise `emo_alpha` to `0.55-0.65` |
| Too fast / rushed | raise `duration_factor` to `1.15-1.25` |
| Too slow / loses punch | lower `duration_factor` to `0.95-1.05` |
| Pronunciation is unstable | lower `temperature` to `0.80-0.84` |
| Repeated or stuck syllables | raise `repetition_penalty` slightly |
| Long text drifts | split at punctuation into 1-3 sentence chunks |

Do not pitch-shift the output to force the target speaker's F0. That breaks the user's timbre. Adjust `emo_alpha` and regenerate instead.

## Batch generation

Use JSONL when generating multiple lines. Each line can override the defaults:

```json
{"text":"第一段旁白。","output":"001.wav","emo_alpha":0.55,"duration_factor":1.10}
{"text":"第二段更冲一点。","output":"002.wav","emo_alpha":0.62,"duration_factor":0.98}
{"text":"第三段收稳。","output":"003.wav","emo_alpha":0.48,"duration_factor":1.12,"emo_vector":[0.08,0.02,0,0,0,0,0.05,0.65]}
```

```bash
uv run --frozen python "$SKILL_DIR/scripts/generate.py" \
  --manifest "/path/to/manifest.jsonl" \
  --voice "outputs/voice_samples/zhang_style_test/user_voice_15s.wav" \
  --style-reference "/tmp/zhang_style_15s.wav" \
  --output "outputs/voice_samples/zhang_style_batch" \
  --continue-on-error
```

The model is loaded once for the whole manifest. `generation_report.json` is
written into the output directory and records successful outputs, per-line
parameters, and failures. Output paths are constrained to the batch directory.
Without `--continue-on-error`, the batch stops at the first failed line.

## Privacy and cleanup

Voice samples are biometric data. Keep them local unless the user explicitly
chooses a service that requires uploading them. Do not place raw voice samples,
private scripts, or generated narration in public repositories.

- Store references under `outputs/voice_samples/` or another private folder.
- The project `.gitignore` excludes `outputs/` and `downloads/`.
- Delete rejected takes and old references when they are no longer needed.
- Ask before reusing a sample for a different person, project, or public release.

To reclaim installation space without deleting source code:

```text
index-tts/checkpoints/   ~8 GB
index-tts/.venv/         ~2 GB
index-tts/outputs/       depends on retained takes
```

## Text rules

- Keep one breath group to `8-14` Chinese characters.
- Put a comma or period before the word you want emphasized.
- Use a short standalone sentence for a punchline: `真不是。`
- Avoid long written-style clauses; prefer spoken hooks such as `完了`, `说白了`, `你记住`.
- Mark English abbreviations with pronunciation hints, for example `<AI|EY2 . AY1>`.

## Reference document

Read `references/zhang_gousheng.md` when you need:

- measured F0, pause, speed, LUFS, and LRA values
- the full tuning history
- the difference between the vector baseline and emotion-reference route
- known failure modes

Read `references/installation.md` when the environment check fails or you need to install IndexTTS on a new machine.

## Troubleshooting

**`IndexTTS checkpoints not found`**
Set `INDEXTTS_ROOT` to the repository that contains `checkpoints/config.yaml`.

**`ffmpeg not found`**
Install ffmpeg or set `FFMPEG_BIN` to its executable.

**`Operation not permitted` from uv**
Use writable caches:

```bash
export UV_CACHE_DIR=/tmp/uv-cache
export MPLCONFIGDIR=/tmp/mpl-cache
export NUMBA_CACHE_DIR=/tmp/numba-cache
```

**`cannot cache function ... no locator available`**
Numba cannot write beside the installed package. Set:

```bash
export NUMBA_CACHE_DIR=/tmp/numba-cache
```

**Python dependency import fails**
Run:

```bash
cd "$INDEXTTS_ROOT"
uv sync --extra webui
python3 "$SKILL_DIR/scripts/check_env.py" --deep
```

**MPS/CUDA errors**
Use `--device cpu`. On this machine, CPU is the reliable path.

**Output is too long**
The model adds phrase-final lengthening. Use slightly faster `duration_factor`, trim pauses in the text, or generate shorter chunks.

**Output is too short**
Raise `duration_factor`, add punctuation, or split a long clause into two shorter ones with a period.

**Style reference is noisy**
Use `prepare_reference.py` with a clean 10-15 second window, or ask the user for a dry clip without music and reverb.

## Files

```text
zhang-gousheng-tts/
├── README.md                  # project entry and resource warning
├── .gitignore
├── SKILL.md
├── scripts/
│   ├── check_env.py           # preflight: commands, models, deps, disk
│   ├── setup_env.sh           # guided uv sync + optional model download
│   ├── prepare_reference.py   # video/audio -> 15s reference WAV
│   ├── generate.py            # IndexTTS generation + mastering
│   └── analyze_audio.py       # F0, pauses, dynamics, loudness
├── references/
│   ├── zhang_gousheng.md      # measured style profile
│   └── installation.md        # install/troubleshooting by OS
├── tests/
│   └── test_scripts.py        # path, parameter, and reference-selection tests
└── evals/
    └── evals.json             # realistic test prompts
```
