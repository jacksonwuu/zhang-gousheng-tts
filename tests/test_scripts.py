from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyze_audio  # noqa: E402
import generate  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
