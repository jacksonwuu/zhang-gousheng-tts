#!/usr/bin/env python3
"""Document in, finished narration out.

This is the one-click entry used by the agent. The user supplies a document;
the script extracts the text, splits it into safe chunks, applies optional
per-section delivery directives, renders every chunk with IndexTTS, joins the
parts, encodes MP3, and writes a reproducibility report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np
import soundfile as sf

from check_env import default_indextts_root, default_profile_path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ROOT = default_indextts_root()


class DocumentError(RuntimeError):
    pass


class TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        elif tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def read_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            document = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise DocumentError(f"Invalid DOCX file: {path}") from exc
    root = ElementTree.fromstring(document)
    namespace = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    }
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(
            node.text or "" for node in paragraph.findall(".//w:t", namespace)
        ).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def read_legacy_word(path: Path) -> str:
    textutil = shutil.which("textutil")
    if textutil is None and Path("/usr/bin/textutil").is_file():
        textutil = "/usr/bin/textutil"
    if textutil is None:
        raise DocumentError(
            "Legacy .doc/.rtf files need macOS textutil. "
            "Convert the document to .docx, .pdf, .md, or .txt first."
        )
    result = subprocess.run(
        [textutil, "-convert", "txt", "-stdout", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-800:]
        raise DocumentError(f"Could not convert {path} with textutil:\n{detail}")
    return result.stdout


def read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentError(
            "PDF support needs pypdf. Run the document through "
            "`scripts/zhang-tts make`, which installs pypdf temporarily."
        ) from exc
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise DocumentError(f"Could not read PDF: {path}: {exc}") from exc
    pages = []
    for index, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise DocumentError(f"Could not extract PDF page {index}: {exc}") from exc
        if text.strip():
            pages.append(text)
    if not pages:
        raise DocumentError(
            "No text found in the PDF. It is probably a scanned image; "
            "run OCR first or provide a text-based document."
        )
    return "\n\n".join(pages)


def read_html(path: Path) -> str:
    parser = TextHTMLParser()
    parser.feed(read_text(path))
    return parser.text()


def read_epub(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = sorted(
                name
                for name in archive.namelist()
                if name.lower().endswith((".xhtml", ".html", ".htm"))
            )
            if not names:
                raise DocumentError(f"EPUB contains no readable HTML: {path}")
            pages = []
            for name in names:
                parser = TextHTMLParser()
                parser.feed(archive.read(name).decode("utf-8", errors="replace"))
                page = parser.text().strip()
                if page:
                    pages.append(page)
    except zipfile.BadZipFile as exc:
        raise DocumentError(f"Invalid EPUB file: {path}") from exc
    return "\n\n".join(pages)


def read_subtitles(path: Path) -> str:
    lines = []
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.upper() == "WEBVTT":
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        if re.search(r"-->\s*", stripped):
            continue
        if stripped.startswith(("NOTE ", "STYLE ", "REGION ")):
            continue
        if not lines or lines[-1] != stripped:
            lines.append(stripped)
    return "\n".join(lines)


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix in {".doc", ".rtf"}:
        return read_legacy_word(path)
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix in {".html", ".htm"}:
        return read_html(path)
    if suffix == ".epub":
        return read_epub(path)
    if suffix in {".srt", ".vtt"}:
        return read_subtitles(path)
    if suffix in {
        ".txt",
        ".md",
        ".markdown",
        ".rst",
        ".csv",
        ".text",
        ".json",
    }:
        return read_text(path)
    raise DocumentError(
        f"Unsupported document type: {suffix or '(no extension)'}. "
        "Supported: txt, md, docx, doc, rtf, pdf, html, epub, srt, vtt."
    )


def clean_text(text: str) -> str:
    directives: list[str] = []

    def stash(match: re.Match[str]) -> str:
        directives.append(match.group(1).strip())
        return f"\n\n@@ZG{len(directives) - 1}@@\n\n"

    text = re.sub(
        r"(?m)^\s*(\[\[[^\n]+\]\])\s*$",
        stash,
        text,
    )
    text = "".join(
        unicodedata.normalize("NFKC", char)
        if 0x2E80 <= ord(char) <= 0x2FDF
        or 0xF900 <= ord(char) <= 0xFAFF
        else char
        for char in text
    )
    text = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\xa0", " ")
    )
    text = re.sub(r"```.*?```", "\n", text, flags=re.S)
    text = re.sub(r"<[^>\n]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.M)
    text = re.sub(r"[*_`~]{1,3}", "", text)
    text = re.sub(r"\|", " ", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    paragraphs = []
    current = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    cleaned = "\n\n".join(paragraphs).strip()
    for index, directive in enumerate(directives):
        cleaned = cleaned.replace(
            f"@@ZG{index}@@", f"\n\n{directive}\n\n"
        )
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def split_long_text(text: str, limit: int) -> list[str]:
    pieces = re.split(r"(?<=[。！？!?；;，,：:])", text)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if len(current) + len(piece) <= limit:
            current += piece
            continue
        if current:
            chunks.append(current)
        while len(piece) > limit:
            cut = piece.rfind("，", 0, limit)
            if cut < limit // 2:
                cut = limit
            chunks.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        current = piece
    if current:
        chunks.append(current)
    return chunks


def make_parts(text: str, limit: int) -> list[str]:
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        if not paragraph:
            continue
        units.extend(split_long_text(paragraph, limit))

    parts: list[str] = []
    current = ""
    for unit in units:
        separator = "\n" if current else ""
        if current and len(current) + len(unit) + len(separator) > limit:
            parts.append(current)
            current = unit
        else:
            current += separator + unit
    if current:
        parts.append(current)
    return [part for part in parts if part.strip()]


DIRECTIVE_RE = re.compile(r"^\s*\[\[(.+?)\]\]\s*$")
PARAM_CASTS = {
    "emo_alpha": float,
    "duration_factor": float,
    "temperature": float,
    "top_p": float,
    "top_k": int,
    "repetition_penalty": float,
}


def parse_directive(body: str) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    body = body.strip()
    matches = list(
        re.finditer(r"(?:^|[\s,;]+)([A-Za-z_]+)\s*=", body)
    )
    if not matches:
        raise DocumentError(
            f"Invalid delivery directive `[[{body}]]`; use key=value."
        )
    if body[: matches[0].start()].strip(" ,;"):
        raise DocumentError(
            f"Invalid delivery directive `[[{body}]]`; use key=value."
        )
    for index, match in enumerate(matches):
        key = match.group(1).lower()
        value_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(body)
        )
        value = body[match.end() : value_end].strip(" ,;")
        if not value:
            raise DocumentError(
                f"Missing value for `{key}` in `[[{body}]]`."
            )
        if key == "speed":
            key = "duration_factor"
        if key == "emo_vector":
            try:
                if value.startswith("["):
                    parsed = json.loads(value)
                    vector = [float(number) for number in parsed]
                else:
                    vector = [
                        float(number)
                        for number in value.replace(";", " ").split()
                    ]
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise DocumentError(
                    "emo_vector must be 8 space-separated numbers"
                ) from exc
            if len(vector) != 8 or any(number < 0 or number > 1 for number in vector):
                raise DocumentError(
                    "emo_vector must contain 8 numbers between 0 and 1"
                )
            overrides[key] = vector
            continue
        cast = PARAM_CASTS.get(key)
        if cast is None:
            raise DocumentError(
                f"Unknown delivery directive `{key}`. Supported: "
                f"{', '.join(sorted([*PARAM_CASTS, 'emo_vector']))}."
            )
        try:
            overrides[key] = cast(value)
        except ValueError as exc:
            raise DocumentError(
                f"Invalid value for `{key}` in `[[{body}]]`: {value}"
            ) from exc
    return overrides


def parse_script(text: str) -> list[dict[str, Any]]:
    """Split text into blocks, carrying `[[key=value]]` delivery overrides."""
    blocks: list[dict[str, Any]] = []
    current_lines: list[str] = []
    overrides: dict[str, Any] = {}

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            blocks.append({"text": body, "overrides": dict(overrides)})

    for line in text.splitlines():
        match = DIRECTIVE_RE.fullmatch(line)
        if match:
            flush()
            current_lines = []
            overrides.update(parse_directive(match.group(1)))
        else:
            current_lines.append(line)
    flush()
    if not blocks:
        raise DocumentError("No usable text found in the document")
    return blocks


def build_parts(text: str, limit: int) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for block in parse_script(text):
        for chunk in make_parts(block["text"], limit):
            parts.append(
                {"text": chunk, "overrides": dict(block["overrides"])}
            )
    return parts


def load_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"Voice profile not found: {path}\n"
            "Ask the agent to configure it once from a clean voice sample."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid profile JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Profile must contain a JSON object: {path}")
    return data


def resolve_path(value: Any, label: str) -> Path:
    if not value:
        raise SystemExit(f"Profile is missing {label}")
    path = Path(str(value)).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"{label} not found: {path}")
    return path


def resolve_optional(value: Any, label: str) -> Path | None:
    if not value:
        return None
    return resolve_path(value, label)


def find_ffmpeg() -> str | None:
    configured = os.environ.get("FFMPEG_BIN")
    if configured:
        path = Path(configured)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in (
        Path("/opt/homebrew/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path.home() / "miniforge3/bin/ffmpeg",
        Path.home() / "miniconda3/bin/ffmpeg",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def default_output_base(source: Path) -> Path:
    parent = Path(
        os.environ.get("ZHANG_OUTPUT_DIR", str(source.parent))
    ).expanduser()
    base = parent / f"{source.stem}.zhang-gousheng"
    try:
        base.parent.mkdir(parents=True, exist_ok=True)
        if os.access(base.parent, os.W_OK):
            return base
    except OSError:
        pass
    for fallback_dir in (
        Path.home() / "Documents/zhang-gousheng-tts",
        Path(tempfile.gettempdir()) / "zhang-gousheng-tts",
    ):
        try:
            fallback_dir.mkdir(parents=True, exist_ok=True)
            if os.access(fallback_dir, os.W_OK):
                return fallback_dir / f"{source.stem}.zhang-gousheng"
        except OSError:
            continue
    raise SystemExit("No writable output directory found")


def normalize_output_base(value: Path | None, source: Path) -> Path:
    if value is None:
        base = default_output_base(source)
    else:
        target = value.expanduser().resolve()
        if target.is_dir():
            base = target / f"{source.stem}.zhang-gousheng"
        elif target.suffix.lower() in {".wav", ".mp3"}:
            base = target.with_suffix("")
        else:
            base = target
    try:
        base.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        fallback_dir = Path(tempfile.gettempdir()) / "zhang-gousheng-tts"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        base = fallback_dir / base.name
        base.parent.mkdir(parents=True, exist_ok=True)
    return base


def concatenate_parts(
    results: list[dict[str, Any]],
    parts: list[dict[str, Any]],
    final_wav: Path,
    pause_ms: int,
) -> list[dict[str, Any]]:
    timeline = []
    current_seconds = 0.0
    pause_samples = int(44100 * pause_ms / 1000)
    final_wav.parent.mkdir(parents=True, exist_ok=True)
    with sf.SoundFile(
        final_wav,
        mode="w",
        samplerate=44100,
        channels=1,
        subtype="PCM_24",
    ) as output:
        for index, result in enumerate(results, 1):
            path = Path(result["output"])
            audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
            if sample_rate != 44100 or audio.shape[1] != 1:
                raise SystemExit(
                    f"Generated part has unexpected format: {path} "
                    f"({sample_rate} Hz, {audio.shape[1]} channels)"
                )
            duration = len(audio) / sample_rate
            timeline.append(
                {
                    "part": index,
                    "start_seconds": round(current_seconds, 2),
                    "duration_seconds": round(duration, 2),
                    "text_preview": str(result.get("text", ""))[:120],
                    "overrides": parts[index - 1]["overrides"],
                }
            )
            output.write(audio[:, 0])
            current_seconds += duration
            if index < len(results) and pause_samples > 0:
                output.write(np.zeros(pause_samples, dtype=np.float32))
                current_seconds += pause_ms / 1000
    return timeline


def encode_mp3(final_wav: Path, final_mp3: Path) -> None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise SystemExit("ffmpeg not found; cannot create MP3")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(final_wav),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(final_mp3),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg could not create MP3: {final_mp3}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Turn a document into finished narration audio."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--profile", type=Path, default=default_profile_path())
    parser.add_argument("--voice", type=Path)
    parser.add_argument("--style-reference", type=Path)
    parser.add_argument("--emo-vector", help="Optional JSON list of 8 numbers.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=["wav", "mp3", "both"], default=None)
    parser.add_argument("--chunk-chars", type=int)
    parser.add_argument("--pause-ms", type=int)
    parser.add_argument("--device")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--keep-parts", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and split the document without running IndexTTS.",
    )
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Document not found: {source}")

    text = clean_text(read_document(source))
    chunk_chars = int(args.chunk_chars or 500)
    if not 100 <= chunk_chars <= 3000:
        raise SystemExit("--chunk-chars must be between 100 and 3000")
    parts = build_parts(text, chunk_chars)
    if not parts:
        raise SystemExit("Document produced no narration parts")

    output_base = normalize_output_base(args.output, source)
    summary: dict[str, Any] = {
        "source": str(source),
        "profile": str(args.profile.expanduser().resolve()),
        "characters": len(text),
        "parts": len(parts),
        "output_base": str(output_base),
    }
    if args.dry_run:
        summary["chunks"] = [
            {
                "part": index,
                "characters": len(part["text"]),
                "overrides": part["overrides"],
                "text": part["text"][:160],
            }
            for index, part in enumerate(parts, 1)
        ]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    if not (ROOT / "pyproject.toml").is_file():
        raise SystemExit(
            f"IndexTTS checkout not found at {ROOT}. Set INDEXTTS_ROOT."
        )

    profile = load_profile(args.profile.expanduser().resolve())
    voice = (
        args.voice.expanduser().resolve()
        if args.voice
        else resolve_path(
            os.environ.get("ZHANG_VOICE_REFERENCE") or profile.get("voice"),
            "voice reference",
        )
    )
    style = (
        args.style_reference.expanduser().resolve()
        if args.style_reference
        else resolve_optional(
            os.environ.get("ZHANG_STYLE_REFERENCE")
            or profile.get("style_reference"),
            "style reference",
        )
    )
    if voice == style:
        raise SystemExit("Voice and style references must be different files")

    if style is not None:
        style_mode = "reference"
        emo_vector = None
    else:
        style_mode = "vector"
        raw_vector = (
            json.loads(args.emo_vector)
            if args.emo_vector
            else profile.get("emo_vector")
        )
        if raw_vector is None:
            raise SystemExit(
                "The profile has neither a style reference nor an emotion vector."
            )
        try:
            emo_vector = [float(number) for number in raw_vector]
        except (TypeError, ValueError) as exc:
            raise SystemExit("emo_vector must be a list of 8 numbers") from exc
        if len(emo_vector) != 8 or any(
            number < 0 or number > 1 for number in emo_vector
        ):
            raise SystemExit("emo_vector must contain 8 numbers between 0 and 1")

    output_format = args.format or str(profile.get("format", "both"))
    pause_ms = int(args.pause_ms if args.pause_ms is not None else profile.get("pause_ms", 250))
    if not 0 <= pause_ms <= 3000:
        raise SystemExit("--pause-ms must be between 0 and 3000")
    device = args.device or str(profile.get("device", "cpu"))
    if output_format in {"mp3", "both"} and find_ffmpeg() is None:
        print("WARNING: ffmpeg not found; writing WAV only.", file=sys.stderr)
        output_format = "wav"

    work_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_base.name}.parts-",
            dir=str(output_base.parent),
        )
    )
    manifest_path = work_dir / "manifest.jsonl"
    generation_report = work_dir / "generation_report.json"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for index, part in enumerate(parts, 1):
            item = {
                "text": part["text"],
                "output": f"part_{index:03d}.wav",
                **part["overrides"],
            }
            manifest.write(json.dumps(item, ensure_ascii=False) + "\n")

    command = [
        sys.executable,
        str(SCRIPT_DIR / "generate.py"),
        "--manifest",
        str(manifest_path),
        "--voice",
        str(voice),
        "--output",
        str(work_dir),
        "--report",
        str(generation_report),
        "--continue-on-error",
        "--lang",
        str(profile.get("lang", "ZH")),
        "--device",
        device,
        "--emo-alpha",
        str(profile.get("emo_alpha", 0.55)),
        "--duration-factor",
        str(profile.get("duration_factor", 1.10)),
        "--temperature",
        str(profile.get("temperature", 0.86)),
        "--top-p",
        str(profile.get("top_p", 0.91)),
        "--top-k",
        str(profile.get("top_k", 45)),
        "--repetition-penalty",
        str(profile.get("repetition_penalty", 8.2)),
        "--max-text-tokens-per-segment",
        str(profile.get("max_text_tokens_per_segment", 300)),
        "--interval-silence",
        str(profile.get("interval_silence", 200)),
    ]
    if style is not None:
        command.extend(["--style-reference", str(style)])
    elif emo_vector is not None:
        command.extend(["--emo-vector", json.dumps(emo_vector)])
    if args.seed is not None:
        command.extend(["--seed", str(args.seed)])

    print(
        f">> {source.name}: {len(parts)} parts, {len(text)} characters, "
        f"style={style_mode}",
        flush=True,
    )
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"Generation failed. Intermediate files kept at: {work_dir}"
        )

    try:
        report = json.loads(generation_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Generation report is invalid: {exc}") from exc
    if report.get("failures"):
        raise SystemExit(
            "Some document parts failed. Intermediate files kept at: "
            f"{work_dir}\n{json.dumps(report['failures'], ensure_ascii=False, indent=2)}"
        )
    generated = report.get("results", [])
    if len(generated) != len(parts):
        raise SystemExit(
            f"Expected {len(parts)} generated parts, got {len(generated)}"
        )

    final_wav = output_base.with_suffix(".wav")
    timeline = concatenate_parts(generated, parts, final_wav, pause_ms)
    outputs = {"wav": str(final_wav)}
    if output_format in {"mp3", "both"}:
        final_mp3 = output_base.with_suffix(".mp3")
        encode_mp3(final_wav, final_mp3)
        outputs["mp3"] = str(final_mp3)

    summary.update(
        {
            "style_mode": style_mode,
            "voice": str(voice),
            "style_reference": str(style) if style else None,
            "emo_vector": emo_vector,
            "parameters": {
                "emo_alpha": profile.get("emo_alpha"),
                "duration_factor": profile.get("duration_factor"),
                "temperature": profile.get("temperature"),
                "top_p": profile.get("top_p"),
                "top_k": profile.get("top_k"),
                "repetition_penalty": profile.get("repetition_penalty"),
                "chunk_chars": chunk_chars,
                "pause_ms": pause_ms,
                "device": device,
                "seed": args.seed,
            },
            "outputs": outputs,
            "duration_seconds": round(
                timeline[-1]["start_seconds"]
                + timeline[-1]["duration_seconds"],
                2,
            ),
            "timeline": timeline,
            "generation_report": str(generation_report) if args.keep_parts else None,
        }
    )
    final_report = output_base.with_suffix(".json")
    final_report.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary["report"] = str(final_report)
    if not args.keep_parts:
        shutil.rmtree(work_dir, ignore_errors=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
