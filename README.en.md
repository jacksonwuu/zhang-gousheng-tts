# zhang-gousheng-tts

Turn a document into Chinese narration with **your own voice** and a fast,
punchy, short-pause news-explainer delivery inspired by the rhythm of
"Zhang Gousheng", powered by
[IndexTTS 2.5](https://github.com/index-tts/index-tts).

[中文](README.md) | English

> **This is not a voice clone of Zhang Gousheng.** Only rhythm, pauses,
> dynamics, and delivery are reproduced. `spk_audio_prompt` must be your own
> voice or a voice you are explicitly authorized to use. Do not impersonate
> real people or generate deceptive content.

## One-click for the user

Send the agent a document and say:

> Read this in my voice, with that fast Zhang Gousheng-style delivery.

The first time, the agent asks for two things only:

1. a clean 10-60 second sample of your own speech (video or audio);
2. approval for the one-time model download (about 8 GB).

After that, just send documents. The agent extracts text, splits it, renders
each chunk, joins the parts, encodes MP3, and returns the audio plus a report.
You never run commands or install Python packages.

Supported inputs: `txt`, `md`, `rst`, `csv`, `json`, `docx`, legacy `doc`,
`rtf`, text-based `pdf`, `html`, `epub`, `srt`, `vtt`. Scanned PDFs need OCR.

Outputs:

- `<name>.zhang-gousheng.wav` at 44.1 kHz / 24-bit
- `<name>.zhang-gousheng.mp3` at 192 kbps
- `<name>.zhang-gousheng.json` with duration, parameters, and timeline

By default they sit next to the source document; if that directory is
read-only, they go to `~/Documents/zhang-gousheng-tts/`.

## Portable skill

This is not tied to one runtime. Any agent that can read `SKILL.md` can use it;
`AGENTS.md` is the entry for runtimes that only discover `AGENTS.md`.

```text
Codex:        ~/.codex/skills/zhang-gousheng-tts
Claude Code:  ~/.claude/skills/zhang-gousheng-tts
Other agent:  any directory; ask the agent to read SKILL.md first
```

The single agent-facing entry is:

```bash
"$SKILL_DIR/scripts/zhang-tts" check
"$SKILL_DIR/scripts/zhang-tts" setup --root "$HOME/index-tts" --download-models --yes
"$SKILL_DIR/scripts/zhang-tts" configure --voice-source "/path/to/user-sample.mov"
"$SKILL_DIR/scripts/zhang-tts" make "/path/to/document.docx"
"$SKILL_DIR/scripts/zhang-tts" say "Text to read"
```

Do not hand these commands to the end user.

## Resource warning

Confirm with the user before installing:

| Resource | Requirement |
|---|---:|
| IndexTTS-2.5 checkpoints | about 8 GB |
| Python environment and caches | about 2-4 GB |
| Free disk during installation | at least 20 GB |
| RAM | 16 GB minimum, 32 GB preferred |
| CPU generation | roughly 5-8x real time |

`setup` clones IndexTTS when needed, installs WebUI dependencies with `uv`,
downloads the model, and runs a deep check. On macOS, do not use
`uv sync --all-extras`; it may resolve NVIDIA CUDA packages.

## Style reference is optional

Without a second style clip, the profile uses a measured emotion vector:

```text
emo_alpha = 0.35
duration_factor = 1.08
emo_vector = [0.08, 0.02, 0, 0, 0, 0, 0.05, 0.65]
```

With an authorized 10-15 second style clip:

```text
emo_alpha = 0.55
duration_factor = 1.10
```

The style clip controls emotion and rhythm only; the user's timbre is preserved.

## Per-section control

Put a directive on its own line; it applies until the next directive:

```text
[[emo_alpha=0.62 duration_factor=0.98]]
This section is more aggressive and faster.

[[emo_alpha=0.45 duration_factor=1.18]]
This section is calmer and slower.
```

Supported keys: `emo_alpha`, `duration_factor` (or `speed`), `temperature`,
`top_p`, `top_k`, `repetition_penalty`, and a space-separated 8-number
`emo_vector`.

## Privacy and licensing

Voice samples are biometric data. Keep references and generated audio private.
The repository does not include model weights, source videos, user voices, or
generated audio. IndexTTS and its weights are governed by their upstream
licenses. This repository's code and documentation are MIT licensed.

See [SKILL.md](SKILL.md) for the full agent contract, tuning table,
troubleshooting, and advanced batch use. See [README.md](README.md) for the full
Chinese guide.
