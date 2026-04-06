from __future__ import annotations

import unittest

from quran_aligner.ayah_builder import build_ayah_alignments
from quran_aligner.models import AlignmentResult, TokenRef, WordAlignment


class AyahBuilderTests(unittest.TestCase):
    def test_groups_word_spans_by_ayah(self) -> None:
        tokens = [
            TokenRef(ayah_number=1, word_index_in_ayah=1, original_word="a", normalized_word="a", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=2, original_word="b", normalized_word="b", normalization_profile="light"),
            TokenRef(ayah_number=2, word_index_in_ayah=1, original_word="c", normalized_word="c", normalization_profile="light"),
        ]
        result = AlignmentResult(
            words=[
                WordAlignment(global_word_index=0, word="a", start_ms=0, end_ms=100, score=0.8),
                WordAlignment(global_word_index=1, word="b", start_ms=110, end_ms=220, score=0.9),
                WordAlignment(global_word_index=2, word="c", start_ms=300, end_ms=500, score=0.7),
            ],
            total_score=2.4,
            backend="fake",
        )

        ayahs = build_ayah_alignments(tokens, result)

        self.assertEqual(len(ayahs), 2)
        self.assertEqual((ayahs[0].ayah_number, ayahs[0].start_ms, ayahs[0].end_ms), (1, 0, 220))
        self.assertEqual((ayahs[1].ayah_number, ayahs[1].start_ms, ayahs[1].end_ms), (2, 300, 500))


if __name__ == "__main__":
    unittest.main()
