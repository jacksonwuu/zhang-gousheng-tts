# Contributing

Contributions should preserve the project's core boundary:

- The user's voice supplies timbre.
- A separate, authorized reference supplies style and emotion.
- The project must not help impersonate a real person or generate deceptive
  content.

## Development

Run the lightweight tests from an environment that already has the IndexTTS
dependencies:

```bash
UV_CACHE_DIR=/tmp/uv-cache \
MPLCONFIGDIR=/tmp/mpl-cache \
NUMBA_CACHE_DIR=/tmp/numba-cache \
uv run --project "${INDEXTTS_ROOT:?set INDEXTTS_ROOT}" --frozen \
  python -m unittest discover -s tests -v
```

Validate the skill structure with your Codex `skill-creator` installation:

```bash
python3 "$HOME/.codex/skills/skill-creator/scripts/quick_validate.py" .
```

## Pull requests

- Keep changes focused and document new flags or failure modes.
- Add or update tests for parsing, path safety, and audio-window logic.
- Never commit voice samples, generated audio, model weights, credentials, or
  private paths.
- Explain any behavior that could affect consent, privacy, or public disclosure.
