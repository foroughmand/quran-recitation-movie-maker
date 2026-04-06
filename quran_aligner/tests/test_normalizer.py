from __future__ import annotations

import unittest

from quran_aligner.normalizer import (
    AGGRESSIVE_NORMALIZATION,
    LIGHT_NORMALIZATION,
    MODERATE_NORMALIZATION,
    QURAN_UTHMANI_ALIGNMENT_MODEL,
    QURAN_UTHMANI_NORMALIZATION,
    choose_normalization_profile,
    filter_text_for_tokenizer,
    flatten_tokens_to_align_units,
    normalize_quranic_text,
    split_text_to_graphemes,
    split_words,
)
from quran_aligner.models import TokenRef


class NormalizerTests(unittest.TestCase):
    def test_light_profile_keeps_diacritics(self) -> None:
        self.assertEqual(normalize_quranic_text("إِنَّ ٱللَّهَ", LIGHT_NORMALIZATION), "إِنَّ ٱللَّهَ")

    def test_moderate_profile_removes_diacritics(self) -> None:
        self.assertEqual(normalize_quranic_text("إِنَّ ٱللَّهَ", MODERATE_NORMALIZATION), "ان الله")

    def test_aggressive_profile_normalizes_ta_marbuta(self) -> None:
        self.assertEqual(normalize_quranic_text("رحمة", AGGRESSIVE_NORMALIZATION), "رحمه")

    def test_split_words_ignores_punctuation(self) -> None:
        self.assertEqual(split_words("بِسْمِ اللَّهِ، الرَّحْمَٰنِ", MODERATE_NORMALIZATION), ["بسم", "الله", "الرحمن"])

    def test_quran_uthmani_profile_keeps_core_quranic_symbols(self) -> None:
        self.assertEqual(normalize_quranic_text("إِنَّ ٱللَّهَ", QURAN_UTHMANI_NORMALIZATION), "إِنَّ ٱللَّهَ")

    def test_model_default_profile_switches_for_quran_model(self) -> None:
        self.assertEqual(
            choose_normalization_profile(None, alignment_model=QURAN_UTHMANI_ALIGNMENT_MODEL),
            "quran_uthmani",
        )

    def test_filter_text_for_tokenizer_removes_unsupported_chars(self) -> None:
        self.assertEqual(
            filter_text_for_tokenizer("ٱللَّهِۚ", is_supported=lambda char: char != "ۚ"),
            "ٱللَّهِ",
        )

    def test_split_text_to_graphemes_keeps_marks_attached(self) -> None:
        self.assertEqual(split_text_to_graphemes("حِكْمَةٌ"), ["حِ", "كْ", "مَ", "ةٌ"])

    def test_flatten_tokens_to_align_units_uses_graphemes_by_default(self) -> None:
        units = flatten_tokens_to_align_units(
            [
                TokenRef(
                    ayah_number=1,
                    word_index_in_ayah=1,
                    original_word="حِكْمَةٌ",
                    normalized_word="حِكْمَةٌ",
                    normalization_profile="quran_uthmani",
                )
            ]
        )
        self.assertEqual([unit.text for unit in units], ["حِ", "كْ", "مَ", "ةٌ"])
        self.assertTrue(all(unit.kind == "grapheme" for unit in units))


if __name__ == "__main__":
    unittest.main()
