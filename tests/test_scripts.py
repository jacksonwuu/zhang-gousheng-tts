from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyze_audio  # noqa: E402
import check_env  # noqa: E402
import configure_profile  # noqa: E402
import generate  # noqa: E402
import make_audio  # noqa: E402
import prepare_reference  # noqa: E402


class GenerateValidationTests(unittest.TestCase):
    def test_rejects_out_of_range_parameters(self) -> None:
        with self.assertRaises(ValueError):
            generate.validate_generation_params(
                emo_alpha=1.2,
                duration_factor=1.1,
                temperature=0.86,
                top_p=0.91,
                top_k=45,
                repetition_penalty=8.2,
                max_text_tokens_per_segment=300,
                interval_silence=200,
                emo_vector=None,
            )

    def test_accepts_documented_defaults(self) -> None:
        generate.validate_generation_params(
            emo_alpha=0.55,
            duration_factor=1.10,
            temperature=0.86,
            top_p=0.91,
            top_k=45,
            repetition_penalty=8.2,
            max_text_tokens_per_segment=300,
            interval_silence=200,
            emo_vector=[0.08, 0.02, 0, 0, 0, 0, 0.05, 0.65],
        )

    def test_manifest_output_stays_inside_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = generate.safe_manifest_output(root, "day1/001.wav", 1)
            self.assertTrue(str(nested).startswith(str(root.resolve())))
            with self.assertRaises(SystemExit):
                generate.safe_manifest_output(root, "../escape.wav", 2)
            with self.assertRaises(SystemExit):
                generate.safe_manifest_output(root, "/tmp/escape.wav", 3)
            with self.assertRaises(SystemExit):
                generate.safe_manifest_output(root, "001.mp3", 4)

    def test_manifest_vector_validation(self) -> None:
        self.assertEqual(
            generate.manifest_vector([0, 0.5, 1, 0, 0, 0, 0.2, 0.8], 1),
            [0.0, 0.5, 1.0, 0.0, 0.0, 0.0, 0.2, 0.8],
        )
        with self.assertRaises(SystemExit):
            generate.manifest_vector(["bad"], 1)


class ReferenceSelectionTests(unittest.TestCase):
    def test_selects_the_louder_window(self) -> None:
        sample_rate = 16000
        quiet = np.zeros(sample_rate * 5, dtype=np.float32)
        loud = (
            np.sin(
                2
                * np.pi
                * 220
                * np.arange(sample_rate * 5, dtype=np.float32)
                / sample_rate
            )
            * 0.4
        )
        audio = np.concatenate([quiet, loud])
        start, end, ratio = prepare_reference.select_window(
            audio, sample_rate, 5
        )
        self.assertGreater(start, sample_rate * 4)
        self.assertGreater(ratio, 0.8)
        self.assertLessEqual(end, audio.size)

    def test_silence_is_not_treated_as_speech(self) -> None:
        audio = np.zeros(16000, dtype=np.float32)
        _, _, ratio = prepare_reference.select_window(audio, 16000, 5)
        self.assertEqual(ratio, 0.0)


class AnalysisTests(unittest.TestCase):
    def test_spoken_units(self) -> None:
        self.assertEqual(analyze_audio.spoken_units("你好，AI 2026。"), 4)


class DocumentTests(unittest.TestCase):
    def test_clean_markdown(self) -> None:
        text = "# 标题\n\n- **重点**：[链接](https://example.com)\n\n> 引用"
        cleaned = make_audio.clean_text(text)
        self.assertIn("标题", cleaned)
        self.assertIn("重点", cleaned)
        self.assertIn("链接", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("#", cleaned)

    def test_parts_respect_limit(self) -> None:
        text = "这是一句测试。" * 120
        parts = make_audio.make_parts(text, 100)
        self.assertTrue(parts)
        self.assertTrue(all(len(part) <= 100 for part in parts))

    def test_read_docx(self) -> None:
        xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body>'
            "<w:p><w:r><w:t>第一段</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>第二段</w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)
            text = make_audio.read_docx(path)
        self.assertIn("第一段", text)
        self.assertIn("第二段", text)

    def test_read_subtitles(self) -> None:
        content = (
            "1\n00:00:00,000 --> 00:00:01,000\n你好。\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n你好。\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.srt"
            path.write_text(content, encoding="utf-8")
            text = make_audio.read_subtitles(path)
        self.assertEqual(text, "你好。")

    def test_read_html_skips_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.html"
            path.write_text(
                "<html><script>bad()</script><p>正文</p></html>",
                encoding="utf-8",
            )
            text = make_audio.read_html(path)
        self.assertIn("正文", text)
        self.assertNotIn("bad()", text)

    def test_unsupported_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.xyz"
            path.write_text("test", encoding="utf-8")
            with self.assertRaises(make_audio.DocumentError):
                make_audio.read_document(path)


class DirectiveTests(unittest.TestCase):
    def test_directive_applies_until_replaced(self) -> None:
        text = (
            "[[emo_alpha=0.62 duration_factor=0.98]]\n"
            "第一段。\n\n"
            "[[emo_alpha=0.45]]\n"
            "第二段。"
        )
        blocks = make_audio.parse_script(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["overrides"]["emo_alpha"], 0.62)
        self.assertEqual(blocks[1]["overrides"]["emo_alpha"], 0.45)
        self.assertEqual(blocks[1]["overrides"]["duration_factor"], 0.98)
        self.assertNotIn("[[", blocks[0]["text"])

    def test_speed_alias(self) -> None:
        self.assertEqual(
            make_audio.parse_directive("speed=0.95"),
            {"duration_factor": 0.95},
        )

    def test_emo_vector_directive(self) -> None:
        overrides = make_audio.parse_directive(
            "emo_vector=0.08 0.02 0 0 0 0 0.05 0.65"
        )
        self.assertEqual(len(overrides["emo_vector"]), 8)
        self.assertEqual(overrides["emo_vector"][-1], 0.65)

    def test_unknown_directive_is_rejected(self) -> None:
        with self.assertRaises(make_audio.DocumentError):
            make_audio.parse_directive("pitch=2")


class ProfileTests(unittest.TestCase):
    def test_vector_route_has_a_default_vector(self) -> None:
        self.assertEqual(len(configure_profile.VECTOR_DEFAULTS["emo_vector"]), 8)
        self.assertIsNone(configure_profile.REFERENCE_DEFAULTS["emo_vector"])

    def test_profile_root_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = Path(temp_dir) / "profile.json"
            profile.write_text(
                json.dumps({"indextts_root": temp_dir}), encoding="utf-8"
            )
            old_profile = os.environ.get("ZHANG_PROFILE")
            old_root = os.environ.pop("INDEXTTS_ROOT", None)
            os.environ["ZHANG_PROFILE"] = str(profile)
            try:
                self.assertEqual(
                    check_env.default_indextts_root(), Path(temp_dir)
                )
            finally:
                os.environ.pop("ZHANG_PROFILE", None)
                if old_profile is not None:
                    os.environ["ZHANG_PROFILE"] = old_profile
                if old_root is not None:
                    os.environ["INDEXTTS_ROOT"] = old_root


if __name__ == "__main__":
    unittest.main()
