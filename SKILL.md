---
name: zhang-gousheng-tts
description: One-click Chinese narration with the user's own voice and a Zhang Gousheng-style fast, punchy delivery. Use whenever the user provides a document, script, article, subtitle file, or raw text and wants it read aloud, cloned in their own voice, turned into audio, batch-produced, or delivered with a "张狗剩" news-explainer rhythm. Also use for IndexTTS voice cloning, reference extraction, emotion/speed tuning, or document-to-audio jobs, even when the user does not say "skill".
---

# Zhang Gousheng TTS

Turn a document into a finished narration file. The user's voice supplies
timbre; an optional style reference supplies rhythm and emotion. The default
style is a measured emotion-vector baseline inspired by Zhang Gousheng-style
news delivery, not an impersonation of that person.

This directory is a portable skill: any agent that can read `SKILL.md` and run
files can use it. It is not tied to Codex, Claude Code, or any single runtime.

## Agent contract

You are the operator. The user should only have to:

1. provide a document, or paste text;
2. once, provide a clean sample of their own voice;
3. approve the one-time model download.

Never ask the user to run terminal commands, edit JSON, install packages, or
manage reference files. Run `scripts/zhang-tts` yourself and hand back the final
audio. Do not paste installation logs or command tutorials into the reply.

The default job is:

```text
document in -> finished WAV/MP3 + short report out
```

Resolve paths from the directory containing this file, not from a hard-coded
skill directory:

```bash
SKILL_DIR="$(cd "$(dirname "<this-file>")" && pwd)"
```

If the runtime supports `SKILL.md`, load this file. If it only supports
`AGENTS.md`, that file points here. If it supports neither, give the agent the
repository path and tell it to read this file first.

## Non-negotiable rules

- `spk_audio_prompt` must be the user's own voice or a voice they are
  explicitly authorized to clone.
- A style reference is only an emotion/rhythm reference. Never use the style
  speaker as the voice identity.
- Do not impersonate a real person or generate deceptive content. Confirm
  rights before public release.
- Voice samples, documents, and generated audio are private. Keep them local
  and out of public repositories.

## Step 1: check the environment

Run:

```bash
"$SKILL_DIR/scripts/zhang-tts" check
```

If it reports `READY`, continue. If not, tell the user the resource cost and
ask for approval before installing.

| Resource | Cost |
|---|---:|
| IndexTTS-2.5 checkpoints | about 8 GB |
| Python environment and caches | about 2-4 GB |
| Free disk during installation | at least 20 GB |
| RAM | 16 GB minimum, 32 GB preferred |
| Model load | several GB temporarily |
| CPU generation | roughly 5-8x real time |

State this clearly and wait for a yes. Then run the one-click installer:

```bash
"$SKILL_DIR/scripts/zhang-tts" setup \
  --root "$HOME/index-tts" \
  --download-models \
  --yes
```

The wrapper clones IndexTTS if the checkout is missing, installs the WebUI
dependencies with `uv`, downloads the model, and re-runs the deep check. Do not
use `--all-extras`; it can pull NVIDIA CUDA packages on macOS.

## Step 2: create the voice profile once

Ask for a clean 10-60 second sample of the user's own speech. A video or audio
file is fine. Avoid background music, multiple speakers, and heavy reverb.

```bash
"$SKILL_DIR/scripts/zhang-tts" configure \
  --voice-source "/path/to/user-sample.mov"
```

This extracts a 15-second reference, stores it under
`~/.config/zhang-gousheng-tts/`, and writes a reusable `profile.json`.

The style reference is optional. Without it, the profile uses the built-in
measured emotion vector, so the user does not need to provide a second clip.
If the user supplies an authorized style sample:

```bash
"$SKILL_DIR/scripts/zhang-tts" configure \
  --voice-source "/path/to/user-sample.mov" \
  --style-source "/path/to/authorized-style-sample.wav"
```

If automatic window selection picks music or another speaker, audition the
result and re-run with `--voice-start SECONDS` or `--style-start SECONDS`.

Do not reuse one person's profile for another person without asking.

## Step 3: the one-click job

The user supplies a document. Run:

```bash
"$SKILL_DIR/scripts/zhang-tts" make "/path/to/document.docx"
```

Short text can go through:

```bash
"$SKILL_DIR/scripts/zhang-tts" say "要读出来的文本"
```

The script:

1. extracts text from the document;
2. cleans Markdown/HTML/subtitle markup;
3. splits the text into safe chunks (about 500 Chinese characters);
4. renders each chunk with the user's voice and the profile style;
5. inserts a short pause between chunks;
6. joins the parts and writes a 44.1 kHz / 24-bit WAV;
7. encodes a 192 kbps MP3 when `ffmpeg` is available;
8. writes a JSON report with duration, parameters, and a timeline;
9. deletes temporary parts unless `--keep-parts` is passed.

Supported inputs: `txt`, `md`, `rst`, `csv`, `json`, `docx`, legacy `doc`,
`rtf` (macOS `textutil`), `pdf` (text-based), `html`, `epub`, `srt`, `vtt`.
Scanned PDFs need OCR first. PDF input automatically uses a temporary `pypdf`
environment; do not modify the IndexTTS lock file.

### What to return to the user

Read the JSON printed by `make` and reply with:

- the final audio file path, preferably as an inline player;
- duration in seconds;
- one sentence about the style/parameters used;
- the report path.

Do not return the whole log. Do not ask the user to open a terminal.

## Per-section emotion and speed

Put a directive on its own line. It applies to everything after it until the
next directive:

```text
[[emo_alpha=0.62 duration_factor=0.98]]
这一段更冲，语速快一点。

[[emo_alpha=0.45 duration_factor=1.18]]
这一段收稳，停顿放长一点。
```

Supported keys: `emo_alpha`, `duration_factor` (also `speed`), `temperature`,
`top_p`, `top_k`, `repetition_penalty`. For a raw emotion vector, use
space-separated numbers:

```text
[[emo_vector=0.08 0.02 0 0 0 0 0.05 0.65]]
```

The eight values are `happy, angry, sad, afraid, disgusted, melancholic,
surprised, calm`. A per-section vector takes precedence over the profile style
reference inside IndexTTS. For most jobs, prefer tuning `emo_alpha` and
`duration_factor` first.

## Recommended parameters

The profile selects one of two routes.

Vector route (no second style clip):

```text
style_mode = vector
emo_alpha = 0.35
duration_factor = 1.08
emo_vector = [0.08, 0.02, 0, 0, 0, 0, 0.05, 0.65]
temperature = 0.85
top_p = 0.90
top_k = 40
repetition_penalty = 8.5
```

Reference route (authorized 10-15 second style clip):

```text
style_mode = reference
emo_alpha = 0.55
duration_factor = 1.10
temperature = 0.86
top_p = 0.91
top_k = 45
repetition_penalty = 8.2
```

Common defaults: `max_text_tokens_per_segment=300`, `interval_silence=200`,
`chunk_chars=500`, `pause_ms=250`.

| Symptom | First adjustment |
|---|---|
| Voice sounds too much like the style clip | lower `emo_alpha` to 0.35-0.45 |
| Delivery is flat or too polite | raise `emo_alpha` to 0.55-0.65 |
| Too fast / rushed | raise `duration_factor` to 1.15-1.25 |
| Too slow / loses punch | lower `duration_factor` to 0.95-1.05 |
| Pronunciation is unstable | lower `temperature` to 0.80-0.84 |
| Repeated or stuck syllables | raise `repetition_penalty` slightly |
| Long text drifts | shorten chunks or add punctuation |

Do not pitch-shift the output to force the target speaker's F0. That breaks the
user's timbre. Adjust `emo_alpha` and regenerate instead.

## Text rules

- Keep one breath group to 8-14 Chinese characters.
- Put a comma or period before the word to emphasize.
- Use a short standalone sentence for a punchline: `真不是。`
- Prefer spoken hooks such as `完了`, `说白了`, `你记住`.
- Mark English abbreviations with pronunciation hints, for example
  `<AI|EY2 . AY1>`.

## Batch and advanced use

For many independent lines, `scripts/generate.py --manifest` loads the model
once and accepts per-line overrides. This is an agent/maintainer tool; the
normal user path remains `zhang-tts make`.

For a single finished file with automatic chunking and per-section directives,
use `make`. For a folder of separate clips driven by a JSONL manifest, use
`generate.py`.

## Privacy and cleanup

Voice samples are biometric data. Keep them local.

- The profile lives under `~/.config/zhang-gousheng-tts/` with `0700`/`0600`
  permissions when the OS allows it.
- The repository `.gitignore` excludes audio, video, `outputs/`, `downloads/`,
  checkpoints, and virtual environments.
- Delete rejected takes and old references when they are no longer needed.
- Ask before reusing a sample for a different person, project, or public
  release.

Space can be reclaimed without deleting source code:

```text
index-tts/checkpoints/   ~8 GB
index-tts/.venv/         ~2 GB
index-tts/outputs/       depends on retained takes
```

## Troubleshooting

**`IndexTTS checkout not found`**
Run `zhang-tts setup --root /path/to/index-tts --download-models --yes` after
the user approves the download.

**`ffmpeg not found`**
Install ffmpeg or set `FFMPEG_BIN`. Without it, `make` writes WAV only.

**`Operation not permitted` from uv**
Use writable caches:

```bash
export UV_CACHE_DIR=/tmp/uv-cache
export MPLCONFIGDIR=/tmp/mpl-cache
export NUMBA_CACHE_DIR=/tmp/numba-cache
```

**`cannot cache function ... no locator available`**
Set `NUMBA_CACHE_DIR=/tmp/numba-cache`.

**PDF support error**
Run through `scripts/zhang-tts make`; it adds `pypdf` in a temporary `uv`
environment. A scanned PDF still needs OCR.

**MPS/CUDA errors**
Use `--device cpu`. On Apple Silicon, CPU is the reliable path.

**Output is too long or too short**
Adjust `duration_factor`, punctuation, or chunk size. The model adds
phrase-final lengthening.

**Style reference is noisy**
Re-extract with a clean 10-15 second window, or omit the style reference and
use the vector baseline.

## Files

```text
zhang-gousheng-tts/
├── SKILL.md                    # this contract
├── AGENTS.md                   # entry for agents without skill support
├── README.md                   # user and maintainer guide
├── scripts/
│   ├── zhang-tts               # one-click agent entry
│   ├── check_env.py            # preflight: commands, models, deps, disk
│   ├── setup_env.sh            # guided clone/uv sync/model download
│   ├── configure_profile.py    # voice + optional style -> profile.json
│   ├── prepare_reference.py    # video/audio -> 15s reference WAV
│   ├── make_audio.py           # document -> final WAV/MP3 + report
│   ├── generate.py             # IndexTTS generation + mastering
│   └── analyze_audio.py        # F0, pauses, dynamics, loudness
├── references/
│   ├── zhang_gousheng.md       # measured style profile
│   └── installation.md         # install/troubleshooting by OS
├── tests/
│   └── test_scripts.py
└── evals/
    └── evals.json
```

Read `references/zhang_gousheng.md` for measured F0, pause, speed, LUFS, and
the tuning history. Read `references/installation.md` when a new machine needs
manual repair or a non-macOS install.
