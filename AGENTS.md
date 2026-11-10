# Agent Entry

This repository is a portable skill. Read `SKILL.md` first; it is the source of
truth for behavior, safety, parameters, and troubleshooting. This file exists
for runtimes that discover `AGENTS.md` but not `SKILL.md`.

## Operating contract

- The end user provides a document (or pasted text) and, once, a clean sample
  of their own voice.
- Never ask the user to run commands, install packages, edit JSON, or manage
  reference files.
- Run `scripts/zhang-tts` yourself. Return the final audio file, its duration,
  and the report path. Do not paste installation or generation logs.
- Before the first model download, explain the cost (about 8 GB of checkpoints,
  2-4 GB of environment/caches, 20 GB free disk during install, 16 GB RAM
  minimum) and wait for explicit approval.
- Use only the user's own voice or a voice they are explicitly authorized to
  clone. A style reference must never become the voice identity.

## One-click flow

1. `scripts/zhang-tts check`
2. If not ready: get approval, then
   `scripts/zhang-tts setup --root "$HOME/index-tts" --download-models --yes`
3. First time only:
   `scripts/zhang-tts configure --voice-source "/path/to/user-sample.mov"`
4. Every job:
   `scripts/zhang-tts make "/path/to/document.docx"`
5. Reply with the returned WAV/MP3 path and duration.

The style reference is optional. Without it, the profile uses a measured
Zhang Gousheng-style emotion vector. With it, the user still keeps their own
timbre.

## Output

The script prints a JSON summary. Use its `outputs.wav`, `outputs.mp3`,
`duration_seconds`, and `report` fields. The default output is next to the
source document, named `<name>.zhang-gousheng.wav` / `.mp3` / `.json`.

## Safety

Voice samples are biometric data. Do not commit them, upload them to public
services, or reuse them for another person. Do not produce deceptive
impersonations. Scanned PDFs need OCR; do not claim success on an empty
extraction.

See `SKILL.md` for per-section emotion directives, parameter tuning, supported
formats, and troubleshooting.
