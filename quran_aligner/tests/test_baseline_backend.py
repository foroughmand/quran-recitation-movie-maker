from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quran_aligner.aligner.baseline_backend import BaselineBackend
from quran_aligner.models import TokenRef


class BaselineBackendTests(unittest.TestCase):
    def test_aligns_mp3_by_duration(self) -> None:
        sample = Path("quran_aligner/data/13-rad-shatri.mp3")
        if not sample.exists():
            self.skipTest("sample MP3 not present")
        tokens = [
            TokenRef(ayah_number=1, word_index_in_ayah=1, original_word="الحمد", normalized_word="الحمد", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=2, original_word="لله", normalized_word="لله", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=3, original_word="رب", normalized_word="رب", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=4, original_word="العالمين", normalized_word="العالمين", normalization_profile="light"),
        ]
        result = BaselineBackend().align(str(sample), tokens)
        self.assertEqual(result.backend, "baseline")
        self.assertEqual(len(result.words), 4)
        self.assertTrue(result.frame_alignments)
        self.assertTrue(result.word_runs)
        self.assertEqual(len(result.word_occurrences), 4)
        self.assertGreater(result.words[-1].end_ms, result.words[0].start_ms)


if __name__ == "__main__":
    unittest.main()
