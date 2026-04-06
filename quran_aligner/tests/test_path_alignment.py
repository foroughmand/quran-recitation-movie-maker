from __future__ import annotations

import unittest

from quran_aligner.dp_decoder import DecoderConfig, WordTimingPrior, build_scoring_matrix, decode_state_score_matrix, decode_with_segmental_dp
from quran_aligner.models import AlignmentResult, FrameAlignment, TokenRef
from quran_aligner.native.dp_kernel import build_native_library
from quran_aligner.path_alignment import populate_path_outputs


class PathAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            build_native_library()
        except Exception as exc:  # pragma: no cover - environment-specific
            raise unittest.SkipTest(f"Native DP library could not be built: {exc}") from exc

    def test_populate_path_outputs_builds_runs_and_occurrences(self) -> None:
        tokens = [
            TokenRef(ayah_number=1, word_index_in_ayah=1, original_word="w1", normalized_word="w1", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=2, original_word="w2", normalized_word="w2", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=3, original_word="w3", normalized_word="w3", normalization_profile="light"),
        ]
        result = AlignmentResult(
            words=[],
            total_score=1.0,
            backend="fake",
            frame_alignments=[
                FrameAlignment(frame_index=10, start_ms=0, end_ms=40, global_unit_index=None, global_word_index=0, score=0.9),
                FrameAlignment(frame_index=11, start_ms=40, end_ms=80, global_unit_index=None, global_word_index=1, score=0.8),
                FrameAlignment(frame_index=12, start_ms=80, end_ms=120, global_unit_index=None, global_word_index=0, score=0.7),
                FrameAlignment(frame_index=13, start_ms=120, end_ms=160, global_unit_index=None, global_word_index=2, score=0.95),
            ],
        )

        populated = populate_path_outputs(result=result, tokens=tokens)

        self.assertEqual([frame.frame_index for frame in populated.frame_alignments], [0, 1, 2, 3])
        self.assertEqual([run.global_word_index for run in populated.word_runs], [0, 1, 0, 2])
        self.assertEqual(populated.word_occurrences[0].visit_count, 2)
        self.assertEqual(
            [(interval.start_ms, interval.end_ms) for interval in populated.word_occurrences[0].intervals],
            [(0, 40), (80, 120)],
        )
        self.assertEqual((populated.words[0].start_ms, populated.words[0].end_ms), (0, 40))

    def test_segmental_dp_builds_path_from_scoring_matrix(self) -> None:
        tokens = [
            TokenRef(ayah_number=1, word_index_in_ayah=1, original_word="w1", normalized_word="w1", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=2, original_word="w2", normalized_word="w2", normalization_profile="light"),
            TokenRef(ayah_number=1, word_index_in_ayah=3, original_word="w3", normalized_word="w3", normalization_profile="light"),
        ]
        priors = [
            WordTimingPrior(start_ms=0, end_ms=40, score=1.0),
            WordTimingPrior(start_ms=40, end_ms=80, score=1.0),
            WordTimingPrior(start_ms=80, end_ms=120, score=1.0),
        ]
        config = DecoderConfig(bucket_ms=40, max_repair_words=3)
        scoring = build_scoring_matrix(tokens, priors, 120, config)
        decoded = decode_with_segmental_dp(tokens, scoring, 120, config)

        self.assertEqual(decoded.bucket_to_word, [0, 1, 2])
        self.assertTrue(decoded.phrase_trace)
        self.assertEqual(decoded.phrase_trace[-1].end_word_index, 2)
        self.assertEqual([(run.global_word_index, run.start_ms, run.end_ms) for run in decoded.runs], [(0, 0, 40), (1, 40, 80), (2, 80, 120)])

    def test_state_dp_only_allows_backtracking_from_word_end_to_word_start(self) -> None:
        scoring = [
            [11.0, -8.0, -8.0, 1.0, -5.0, -1.0],
            [-2.0, 29.0, -4.0, 9.0, -9.0, 8.0],
            [-5.0, 3.0, 10.0, 2.0, 6.0, 1.0],
            [7.0, 4.0, 6.0, -2.0, -9.0, 10.0],
        ]

        unrestricted = decode_state_score_matrix(
            4,
            scoring,
            DecoderConfig(
                bucket_ms=40,
                max_phrase_buckets=4,
                backtrack_only_from_word_end=False,
                backtrack_only_to_word_start=False,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
            ),
            is_word_start_state=[True, False, True, False],
            is_word_end_state=[False, True, False, True],
        )
        restricted = decode_state_score_matrix(
            4,
            scoring,
            DecoderConfig(
                bucket_ms=40,
                max_phrase_buckets=4,
                backtrack_only_from_word_end=True,
                backtrack_only_to_word_start=True,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
            ),
            is_word_start_state=[True, False, True, False],
            is_word_end_state=[False, True, False, True],
        )

        self.assertEqual(unrestricted.bucket_to_state, [0, 1, 2, 1, 2, 3])
        self.assertEqual(restricted.bucket_to_state, [0, 1, 2, 2, 2, 3])

    def test_state_dp_backtrack_penalty_can_suppress_jump(self) -> None:
        scoring = [
            [11.0, -8.0, -8.0, 1.0, -5.0, -1.0],
            [-2.0, 29.0, -4.0, 9.0, -9.0, 8.0],
            [-5.0, 3.0, 10.0, 2.0, 6.0, 1.0],
            [7.0, 4.0, 6.0, -2.0, -9.0, 10.0],
        ]
        start_mask = [True, False, True, False]
        end_mask = [False, True, False, True]

        no_penalty = decode_state_score_matrix(
            4,
            scoring,
            DecoderConfig(
                bucket_ms=40,
                max_phrase_buckets=4,
                backtrack_only_from_word_end=False,
                backtrack_only_to_word_start=False,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
            ),
            is_word_start_state=start_mask,
            is_word_end_state=end_mask,
        )
        penalized = decode_state_score_matrix(
            4,
            scoring,
            DecoderConfig(
                bucket_ms=40,
                max_phrase_buckets=4,
                backtrack_only_from_word_end=False,
                backtrack_only_to_word_start=False,
                backtrack_base_penalty=8.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
            ),
            is_word_start_state=start_mask,
            is_word_end_state=end_mask,
        )

        self.assertEqual(no_penalty.bucket_to_state, [0, 1, 2, 1, 2, 3])
        self.assertEqual(penalized.bucket_to_state, [0, 1, 2, 2, 2, 3])

    def test_step_by_step_dp_allows_silence_only_at_word_end(self) -> None:
        scoring = [
            [9.0, -6.0, -8.0, -7.0, -7.0, -8.0],
            [-6.0, 9.0, -8.0, -7.0, -7.0, -8.0],
            [-8.0, -8.0, -7.0, 9.0, -6.0, -8.0],
            [-8.0, -8.0, -7.0, -6.0, 9.0, 8.0],
        ]
        decoded = decode_state_score_matrix(
            4,
            scoring,
            DecoderConfig(
                bucket_ms=40,
                backtrack_only_from_word_end=True,
                backtrack_only_to_word_start=True,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
                state_dp_mode="step_by_step",
                silence_stay_score=0.0,
            ),
            is_word_start_state=[True, False, True, False],
            is_word_end_state=[False, True, False, True],
        )

        self.assertEqual(decoded.bucket_to_state, [0, 1, 1, 2, 3, 3])

    def test_step_by_step_dp_supports_boundary_backtrack(self) -> None:
        scoring = [
            [10.0, -5.0, -5.0, -5.0, 10.0, -5.0, -5.0, -5.0],
            [-5.0, 10.0, -5.0, -5.0, -5.0, 10.0, -5.0, -5.0],
            [-5.0, -5.0, 10.0, -5.0, -5.0, -5.0, 10.0, -5.0],
            [-5.0, -5.0, -5.0, 10.0, -5.0, -5.0, -5.0, 10.0],
        ]
        decoded = decode_state_score_matrix(
            4,
            scoring,
            DecoderConfig(
                bucket_ms=40,
                backtrack_only_from_word_end=True,
                backtrack_only_to_word_start=True,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
                state_dp_mode="step_by_step",
                silence_stay_score=-2.0,
            ),
            is_word_start_state=[True, False, True, False],
            is_word_end_state=[False, True, False, True],
        )

        self.assertEqual(decoded.bucket_to_state, [0, 1, 2, 3, 0, 1, 2, 3])

    def test_step_by_step_dp_can_use_bucket_specific_silence_scores(self) -> None:
        scoring = [
            [8.0, -7.0, -7.0, -7.0],
            [-7.0, 8.0, -7.0, -7.0],
        ]
        decoded = decode_state_score_matrix(
            2,
            scoring,
            DecoderConfig(
                bucket_ms=40,
                backtrack_only_from_word_end=True,
                backtrack_only_to_word_start=True,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
                state_dp_mode="step_by_step",
                silence_stay_score=-10.0,
            ),
            is_word_start_state=[True, False],
            is_word_end_state=[False, True],
            bucket_silence_scores=[-10.0, -10.0, 2.0, 2.0],
        )

        self.assertEqual(decoded.bucket_to_state, [0, 1, 1, 1])

    def test_native_step_by_step_matches_python_for_silence_case(self) -> None:
        scoring = [
            [9.0, -6.0, -8.0, -7.0, -7.0, -8.0],
            [-6.0, 9.0, -8.0, -7.0, -7.0, -8.0],
            [-8.0, -8.0, -7.0, 9.0, -6.0, -8.0],
            [-8.0, -8.0, -7.0, -6.0, 9.0, 8.0],
        ]
        kwargs = dict(
            state_count=4,
            scoring_matrix=scoring,
            config=DecoderConfig(
                bucket_ms=40,
                backtrack_only_from_word_end=True,
                backtrack_only_to_word_start=True,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
                state_dp_mode="step_by_step",
                silence_stay_score=0.0,
            ),
            is_word_start_state=[True, False, True, False],
            is_word_end_state=[False, True, False, True],
        )

        python_decoded = decode_state_score_matrix(**kwargs)
        native_decoded = decode_state_score_matrix(
            **{
                **kwargs,
                "config": DecoderConfig(
                    bucket_ms=40,
                    backtrack_only_from_word_end=True,
                    backtrack_only_to_word_start=True,
                    backtrack_base_penalty=0.0,
                    backtrack_step_penalty=0.0,
                    state_dp_mode="step_by_step",
                    state_dp_engine="native",
                    silence_stay_score=0.0,
                ),
            }
        )

        self.assertEqual(native_decoded.bucket_to_state, python_decoded.bucket_to_state)

    def test_native_step_by_step_matches_python_for_bucket_silence_scores(self) -> None:
        scoring = [
            [8.0, -7.0, -7.0, -7.0],
            [-7.0, 8.0, -7.0, -7.0],
        ]
        kwargs = dict(
            state_count=2,
            scoring_matrix=scoring,
            is_word_start_state=[True, False],
            is_word_end_state=[False, True],
            bucket_silence_scores=[-10.0, -10.0, 2.0, 2.0],
        )
        python_decoded = decode_state_score_matrix(
            **kwargs,
            config=DecoderConfig(
                bucket_ms=40,
                backtrack_only_from_word_end=True,
                backtrack_only_to_word_start=True,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="python",
                state_dp_mode="step_by_step",
                silence_stay_score=-10.0,
            ),
        )
        native_decoded = decode_state_score_matrix(
            **kwargs,
            config=DecoderConfig(
                bucket_ms=40,
                backtrack_only_from_word_end=True,
                backtrack_only_to_word_start=True,
                backtrack_base_penalty=0.0,
                backtrack_step_penalty=0.0,
                state_dp_engine="native",
                state_dp_mode="step_by_step",
                silence_stay_score=-10.0,
            ),
        )

        self.assertEqual(native_decoded.bucket_to_state, python_decoded.bucket_to_state)


if __name__ == "__main__":
    unittest.main()
