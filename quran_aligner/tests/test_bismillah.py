from __future__ import annotations

import unittest

from quran_aligner.models import Ayah, SurahText
from quran_aligner.normalizer import prepare_target_text


class BismillahTests(unittest.TestCase):
    def setUp(self) -> None:
        self.surah = SurahText(
            surah_number=1,
            ayahs=[Ayah(ayah_number=1, text="الْحَمْدُ لِلَّهِ", words=["الحمد", "لله"])],
        )

    def test_force_prepends_synthetic_ayah(self) -> None:
        [candidate] = prepare_target_text(self.surah, "force")
        self.assertEqual(candidate.ayahs[0].ayah_number, 0)

    def test_auto_returns_both_candidates(self) -> None:
        candidates = prepare_target_text(self.surah, "auto")
        self.assertEqual(len(candidates), 2)

    def test_force_does_not_duplicate_existing_bismillah(self) -> None:
        surah = SurahText(
            surah_number=13,
            ayahs=[Ayah(ayah_number=1, text="بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ المر", words=["بسم", "الله", "الرحمن", "الرحيم", "المر"])],
        )
        [candidate] = prepare_target_text(surah, "force")
        self.assertEqual(candidate.ayahs[0].ayah_number, 0)
        self.assertEqual(candidate.ayahs[1].words, ["المر"])


if __name__ == "__main__":
    unittest.main()
