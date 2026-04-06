from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quran_aligner.app import run_alignment
from quran_aligner.models import AlignmentResult, WordAlignment


class FakeBackend:
    alignment_model = "fake/model"

    def align(self, audio_path: str, tokens) -> AlignmentResult:
        spans = []
        for index, token in enumerate(tokens):
            start = index * 100
            spans.append(
                WordAlignment(
                    global_word_index=index,
                    word=token.normalized_word,
                    start_ms=start,
                    end_ms=start + 80,
                    score=0.95,
                )
            )
        return AlignmentResult(words=spans, total_score=len(spans), backend="fake")


class EndToEndSmokeTests(unittest.TestCase):
    def test_writes_alignment_and_debug_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "alignment.txt"
            debug_path = Path(tmpdir) / "alignment.debug.json"
            review_path = Path(tmpdir) / "index.html"
            run = run_alignment(
                audio_path="dummy.wav",
                surah_number=112,
                mode="full",
                include_bismillah_mode="off",
                disable_refinement=True,
                output_path=str(output_path),
                debug_path=str(debug_path),
                review_path=str(review_path),
                backend=FakeBackend(),
                prefer_remote_text=False,
            )

            self.assertTrue(output_path.exists())
            self.assertTrue(debug_path.exists())
            self.assertTrue(review_path.exists())
            self.assertEqual(run.result.backend, "fake")
            self.assertEqual(run.ayah_alignments[0].ayah_number, 1)

    def test_ayah_mode_limits_output_to_one_ayah(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run = run_alignment(
                audio_path="dummy.wav",
                surah_number=112,
                mode="ayah",
                ayah_number=2,
                include_bismillah_mode="off",
                disable_refinement=True,
                output_dir=tmpdir,
                backend=FakeBackend(),
                prefer_remote_text=False,
            )

            self.assertEqual([ayah.ayah_number for ayah in run.ayah_alignments], [2])

    def test_run_alignment_uses_quran_profile_default_for_quran_model(self) -> None:
        backend = FakeBackend()
        backend.alignment_model = "rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final"
        with tempfile.TemporaryDirectory() as tmpdir:
            run = run_alignment(
                audio_path="dummy.wav",
                surah_number=112,
                mode="full",
                include_bismillah_mode="off",
                disable_refinement=True,
                output_dir=tmpdir,
                backend=backend,
                prefer_remote_text=False,
            )

            self.assertEqual(run.result.metadata["normalization_profile"], "quran_uthmani")


if __name__ == "__main__":
    unittest.main()
