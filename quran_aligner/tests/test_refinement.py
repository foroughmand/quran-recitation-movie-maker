from __future__ import annotations

import unittest

from quran_aligner.acoustic_refinement import (
    RefinementProposal,
    build_local_phrase_windows,
    find_suspicious_words,
    select_non_overlapping_proposals,
    refine_alignment_with_emissions,
)
from quran_aligner.models import AlignmentResult, TokenRef, WordAlignment
from quran_aligner.refinement import compute_audio_gaps


class _FakeBackend:
    def __init__(self, replacement: AlignmentResult) -> None:
        self.replacement = replacement

    def local_realign(self, audio_path: str, tokens: list[TokenRef], start_ms: int, end_ms: int) -> AlignmentResult:
        return self.replacement


class AcousticRefinementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tokens = [
            TokenRef(ayah_number=1, word_index_in_ayah=1, original_word="قال", normalized_word="قال", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=2, original_word="من", normalized_word="من", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=3, original_word="ربك", normalized_word="ربك", normalization_profile="light"),
        ]
        self.result = AlignmentResult(
            words=[
                WordAlignment(global_word_index=0, word="قال", start_ms=0, end_ms=300, score=-2.0),
                WordAlignment(global_word_index=1, word="من", start_ms=900, end_ms=920, score=-18.0),
                WordAlignment(global_word_index=2, word="ربك", start_ms=980, end_ms=1400, score=-3.0),
            ],
            total_score=-23.0,
            backend="ctc",
            metadata={"total_audio_ms": 1600},
        )

    def test_compute_audio_gaps_reports_internal_gap(self) -> None:
        gaps = compute_audio_gaps(self.result, 1600)
        self.assertTrue(any(gap.kind == "between" for gap in gaps))

    def test_find_suspicious_words_flags_low_score_word(self) -> None:
        gaps = compute_audio_gaps(self.result, 1600)
        suspicious = find_suspicious_words(self.result, min_word_confidence=0.45, gaps=gaps)
        suspect = next(item for item in suspicious if item.global_word_index == 1)
        self.assertIn("low_score", suspect.flags)

    def test_build_local_phrase_windows_keeps_fixed_size(self) -> None:
        gaps = compute_audio_gaps(self.result, 1600)
        suspicious = find_suspicious_words(self.result, min_word_confidence=0.45, gaps=gaps)
        regions = build_local_phrase_windows(
            suspicious,
            len(self.result.words),
            local_phrase_words=3,
            word_alignments=self.result.words,
            window_padding_ms=250,
        )
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].start_word_index, 0)
        self.assertEqual(regions[0].end_word_index, 2)

    def test_refine_alignment_only_accepts_score_improvement(self) -> None:
        better = AlignmentResult(
            words=[
                WordAlignment(global_word_index=0, word="قال", start_ms=0, end_ms=260, score=-1.0),
                WordAlignment(global_word_index=1, word="من", start_ms=860, end_ms=980, score=-4.0),
                WordAlignment(global_word_index=2, word="ربك", start_ms=980, end_ms=1400, score=-2.0),
            ],
            total_score=-7.0,
            backend="ctc",
            metadata={"total_audio_ms": 1600},
        )
        refined, regions, notes, suspicious, gaps = refine_alignment_with_emissions(
            self.tokens,
            self.result,
            backend=_FakeBackend(better),
            audio_path="example.mp3",
            min_word_confidence=0.45,
            window_padding_ms=250,
            min_score_improvement=0.05,
            local_phrase_words=3,
        )
        self.assertEqual(len(regions), 1)
        self.assertNotEqual(refined.words[1].end_ms, self.result.words[1].end_ms)
        self.assertTrue(any("Accepted proposals: 1" in note for note in notes))
        self.assertIsInstance(suspicious, list)
        self.assertIsInstance(gaps, list)

    def test_refine_alignment_rejects_non_improving_candidate(self) -> None:
        worse = AlignmentResult(
            words=[
                WordAlignment(global_word_index=0, word="قال", start_ms=0, end_ms=260, score=-10.0),
                WordAlignment(global_word_index=1, word="من", start_ms=860, end_ms=980, score=-12.0),
                WordAlignment(global_word_index=2, word="ربك", start_ms=980, end_ms=1400, score=-10.0),
            ],
            total_score=-32.0,
            backend="ctc",
            metadata={"total_audio_ms": 1600},
        )
        refined, _regions, notes, _suspicious, _gaps = refine_alignment_with_emissions(
            self.tokens,
            self.result,
            backend=_FakeBackend(worse),
            audio_path="example.mp3",
            min_word_confidence=0.45,
            window_padding_ms=250,
            min_score_improvement=0.05,
            local_phrase_words=3,
        )
        self.assertEqual(refined.words[1].end_ms, self.result.words[1].end_ms)
        self.assertTrue(any("Accepted proposals: 0" in note for note in notes))

    def test_select_non_overlapping_proposals_keeps_best_ranges(self) -> None:
        better = AlignmentResult(
            words=[
                WordAlignment(global_word_index=0, word="قال", start_ms=0, end_ms=260, score=-1.0),
                WordAlignment(global_word_index=1, word="من", start_ms=860, end_ms=980, score=-4.0),
                WordAlignment(global_word_index=2, word="ربك", start_ms=980, end_ms=1400, score=-2.0),
            ],
            total_score=-7.0,
            backend="ctc",
            metadata={"total_audio_ms": 1600},
        )
        proposals = [
            RefinementProposal(
                start_word_index=0,
                end_word_index=1,
                old_local_score=-20.0,
                new_local_score=-10.0,
                score_improvement=10.0,
                replacement_words=better.words[:2],
                start_ms=0,
                end_ms=980,
                accepted=True,
                reason="a",
            ),
            RefinementProposal(
                start_word_index=1,
                end_word_index=2,
                old_local_score=-20.0,
                new_local_score=-15.0,
                score_improvement=5.0,
                replacement_words=better.words[1:],
                start_ms=860,
                end_ms=1400,
                accepted=True,
                reason="b",
            ),
        ]
        selected = select_non_overlapping_proposals(proposals)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].start_word_index, 0)
