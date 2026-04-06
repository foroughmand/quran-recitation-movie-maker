from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import ctypes
import time
from typing import Any

import numpy as np

from .models import AlignmentRunSegment, FrameAlignment, TokenRef
from .native.dp_kernel import load_native_library
from .progress import ProgressEvent


NEG_INF = -10.0**18


def _format_duration_seconds(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


@dataclass(slots=True)
class WordTimingPrior:
    start_ms: int
    end_ms: int
    score: float


@dataclass(slots=True)
class DecoderConfig:
    bucket_ms: int = 40
    max_repair_words: int = 4
    max_phrase_buckets: int = 96
    duration_penalty: float = 0.35
    boundary_flex_penalty: float = 0.08
    outside_span_penalty: float = 0.45
    stay_bonus: float = 0.15
    repair_base_penalty: float = 1.5
    repair_step_penalty: float = 0.9
    backtrack_only_from_word_end: bool = True
    backtrack_only_to_word_start: bool = True
    backtrack_base_penalty: float = 100.0
    backtrack_step_penalty: float = 0.0
    state_dp_engine: str = "native"
    state_dp_mode: str = "jump"
    silence_stay_score: float = -25.0

    def beta(self, k: int) -> float:
        if k <= 1:
            return 0.0
        return self.repair_base_penalty + (k - 2) * self.repair_step_penalty

    def backtrack_penalty(self, jump_distance: int) -> float:
        if jump_distance <= 0:
            return 0.0
        return self.backtrack_base_penalty + jump_distance * self.backtrack_step_penalty


@dataclass(slots=True)
class PhraseTrace:
    previous_word_index: int | None
    start_word_index: int
    end_word_index: int
    start_bucket: int
    end_bucket: int
    repair_width: int


@dataclass(slots=True)
class DecoderResult:
    bucket_to_word: list[int]
    frames: list[FrameAlignment]
    runs: list[AlignmentRunSegment]
    total_score: float
    scoring_matrix: list[list[float]]
    phrase_trace: list[PhraseTrace]
    debug: dict[str, object] | None = None


@dataclass(slots=True)
class StateDecodeResult:
    """dp_scores/backpointers: python engine uses nested lists; native uses ndarray / (ps, pb) tuple."""

    bucket_to_state: list[int]
    total_score: float
    dp_scores: Any
    backpointers: Any


def _backtrack_state_path(
    back: list[list[tuple[int | None, int] | None]],
    state_count: int,
    bucket_count: int,
    *,
    progress_callback=None,
) -> list[int]:
    bucket_to_state = [-1] * bucket_count
    state_index: int | None = state_count - 1
    bucket = bucket_count
    covered = 0
    while state_index is not None:
        pointer = back[state_index][bucket]
        if pointer is None:
            raise RuntimeError("State DP path is missing a backpointer.")
        previous_state, previous_bucket = pointer
        for bucket_index in range(previous_bucket, bucket):
            bucket_to_state[bucket_index] = state_index
        covered += bucket - previous_bucket
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="backtrack",
                    message=f"Backtracking final DP path ({covered}/{bucket_count} buckets)",
                    completed=covered,
                    total=bucket_count,
                )
            )
        state_index = previous_state
        bucket = previous_bucket
        if state_index is None and bucket != 0:
            raise RuntimeError("State DP terminated before covering bucket 0.")

    if any(state < 0 for state in bucket_to_state):
        raise RuntimeError("State DP produced an incomplete bucket path.")
    return bucket_to_state


def _backtrack_state_path_numpy(
    prev_state: np.ndarray,
    prev_bucket: np.ndarray,
    state_count: int,
    bucket_count: int,
    *,
    progress_callback=None,
) -> list[int]:
    bucket_to_state = [-1] * bucket_count
    state_index: int | None = state_count - 1
    bucket = bucket_count
    covered = 0
    while state_index is not None:
        prev_sv = int(prev_state[state_index, bucket])
        prev_bv = int(prev_bucket[state_index, bucket])
        if prev_sv == -2:
            pointer = None
        elif prev_sv == -1:
            pointer = (None, prev_bv)
        else:
            pointer = (prev_sv, prev_bv)
        if pointer is None:
            raise RuntimeError("State DP path is missing a backpointer.")
        previous_state, previous_bucket = pointer
        for bucket_index in range(previous_bucket, bucket):
            bucket_to_state[bucket_index] = state_index
        covered += bucket - previous_bucket
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="backtrack",
                    message=f"Backtracking final DP path ({covered}/{bucket_count} buckets)",
                    completed=covered,
                    total=bucket_count,
                )
            )
        state_index = previous_state
        bucket = previous_bucket
        if state_index is None and bucket != 0:
            raise RuntimeError("State DP terminated before covering bucket 0.")

    if any(state < 0 for state in bucket_to_state):
        raise RuntimeError("State DP produced an incomplete bucket path.")
    return bucket_to_state


def state_dp_phrase_trace_payload(decoded: StateDecodeResult, units) -> list[dict[str, object]]:
    """Same entries as the CTC backend ``phrase_trace`` list (for review / debug)."""
    back = decoded.backpointers
    bts = decoded.bucket_to_state
    bucket_count = len(bts)
    state_count = len(units)
    traces: list[dict[str, object]] = []
    if isinstance(back, tuple):
        ps, pb = back
        for state_index in range(min(state_count, ps.shape[0])):
            for bucket_index in range(bucket_count):
                col = bucket_index + 1
                prev_sv = int(ps[state_index, col])
                prev_bv = int(pb[state_index, col])
                if prev_sv == -2:
                    pointer = None
                elif prev_sv == -1:
                    pointer = (None, prev_bv)
                else:
                    pointer = (prev_sv, prev_bv)
                if pointer is None or bts[bucket_index] != state_index:
                    continue
                traces.append(
                    {
                        "previous_state_index": pointer[0],
                        "start_word_index": units[state_index].global_word_index,
                        "end_word_index": units[state_index].global_word_index,
                        "start_bucket": pointer[1] if pointer is not None else 0,
                        "end_bucket": bucket_index + 1,
                        "repair_width": 1 if pointer is None or pointer[0] is None else abs(state_index - pointer[0]) + 1,
                    }
                )
    else:
        for state_index, row in enumerate(back):
            for bucket_index, pointer in enumerate(row[1:], start=0):
                if pointer is not None and bts[bucket_index] == state_index:
                    traces.append(
                        {
                            "previous_state_index": pointer[0],
                            "start_word_index": units[state_index].global_word_index,
                            "end_word_index": units[state_index].global_word_index,
                            "start_bucket": pointer[1] if pointer is not None else 0,
                            "end_bucket": bucket_index + 1,
                            "repair_width": 1 if pointer is None or pointer[0] is None else abs(state_index - pointer[0]) + 1,
                        }
                    )
    return traces


def build_scoring_matrix(
    tokens: list[TokenRef],
    priors: list[WordTimingPrior],
    total_audio_ms: int,
    config: DecoderConfig,
    progress_callback=None,
) -> list[list[float]]:
    bucket_count = max(1, (total_audio_ms + config.bucket_ms - 1) // config.bucket_ms)
    weights = [_word_weight(token.normalized_word) for token in tokens]
    total_weight = sum(weights) or 1

    if len(priors) != len(tokens):
        raise ValueError("Word priors must match token count.")

    matrix: list[list[float]] = []
    for word_index, token in enumerate(tokens):
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="score-matrix",
                    message=f"Scoring word {word_index + 1} of {len(tokens)}",
                    completed=word_index + 1,
                    total=len(tokens),
                )
            )
        prior = priors[word_index]
        prior_duration_ms = max(config.bucket_ms, prior.end_ms - prior.start_ms)
        expected_bucket_count = max(1.0, prior_duration_ms / config.bucket_ms)
        fallback_expected = max(1.0, bucket_count * (weights[word_index] / total_weight))
        expected_bucket_count = (expected_bucket_count + fallback_expected) / 2.0
        center_ms = (prior.start_ms + prior.end_ms) / 2.0
        row: list[float] = []

        for bucket_index in range(bucket_count):
            bucket_start_ms = bucket_index * config.bucket_ms
            bucket_end_ms = min(total_audio_ms, bucket_start_ms + config.bucket_ms)
            bucket_center_ms = (bucket_start_ms + bucket_end_ms) / 2.0
            overlap_ms = max(0.0, min(bucket_end_ms, prior.end_ms) - max(bucket_start_ms, prior.start_ms))
            overlap_ratio = overlap_ms / max(1.0, bucket_end_ms - bucket_start_ms)
            center_distance = abs(bucket_center_ms - center_ms) / max(config.bucket_ms, prior_duration_ms / 2.0)
            outside_distance = 0.0
            if bucket_end_ms <= prior.start_ms:
                outside_distance = (prior.start_ms - bucket_end_ms) / config.bucket_ms
            elif bucket_start_ms >= prior.end_ms:
                outside_distance = (bucket_start_ms - prior.end_ms) / config.bucket_ms

            score = float(prior.score)
            score += overlap_ratio * (1.0 + config.stay_bonus)
            score -= center_distance * config.boundary_flex_penalty
            score -= outside_distance * config.outside_span_penalty
            score -= abs(1.0 - overlap_ratio) * (config.duration_penalty / max(1.0, expected_bucket_count))
            row.append(score)
        matrix.append(row)
    return matrix


def decode_with_segmental_dp(
    tokens: list[TokenRef],
    scoring_matrix: list[list[float]],
    total_audio_ms: int,
    config: DecoderConfig,
    progress_callback=None,
    collect_debug: bool = False,
) -> DecoderResult:
    word_count = len(tokens)
    bucket_count = len(scoring_matrix[0]) if scoring_matrix else 0
    if word_count == 0 or bucket_count == 0:
        return DecoderResult(
            bucket_to_word=[],
            frames=[],
            runs=[],
            total_score=0.0,
            scoring_matrix=scoring_matrix,
            phrase_trace=[],
            debug=None,
        )

    prefix_sums: list[list[float]] = []
    expected_lengths: list[float] = []
    for row in scoring_matrix:
        prefix = [0.0]
        for value in row:
            prefix.append(prefix[-1] + value)
        prefix_sums.append(prefix)
        positive_bins = sum(1 for value in row if value > 0.0)
        expected_lengths.append(float(max(1, positive_bins)))

    def word_interval_score(word_index: int, start_bucket: int, end_bucket: int) -> float:
        if end_bucket <= start_bucket:
            return NEG_INF
        bucket_span = end_bucket - start_bucket
        if bucket_span > config.max_phrase_buckets:
            return NEG_INF
        interval_sum = prefix_sums[word_index][end_bucket] - prefix_sums[word_index][start_bucket]
        duration_penalty = abs(bucket_span - expected_lengths[word_index]) * config.duration_penalty
        return interval_sum - duration_penalty

    dp = [[NEG_INF] * (bucket_count + 1) for _ in range(word_count)]
    back: list[list[tuple[int | None, int] | None]] = [[None] * (bucket_count + 1) for _ in range(word_count)]

    for b in range(1, bucket_count + 1):
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="decode",
                    message=f"Filling DP bucket {b} of {bucket_count}",
                    completed=b,
                    total=bucket_count,
                )
            )
        start_low = max(0, b - config.max_phrase_buckets)
        suffix_best_scores: dict[int, list[float]] = {}
        suffix_best_words: dict[int, list[int | None]] = {}
        for a in range(start_low, b):
            scores = [NEG_INF] * (word_count + 1)
            words = [None] * (word_count + 1)
            best_score = NEG_INF
            best_word: int | None = None
            for word_index in range(word_count - 1, -1, -1):
                if dp[word_index][a] > best_score:
                    best_score = dp[word_index][a]
                    best_word = word_index
                scores[word_index] = best_score
                words[word_index] = best_word
            suffix_best_scores[a] = scores
            suffix_best_words[a] = words

        for i in range(word_count):
            best_score = NEG_INF
            best_back: tuple[int | None, int] | None = None
            for a in range(start_low, b):
                segment_score = word_interval_score(i, a, b)
                if segment_score <= NEG_INF / 2:
                    continue

                if i == 0 and a == 0:
                    candidate = segment_score
                    if candidate > best_score:
                        best_score = candidate
                        best_back = (None, 0)

                if i > 0:
                    prev_score = dp[i - 1][a]
                    if prev_score > NEG_INF / 2:
                        candidate = prev_score + segment_score
                        if candidate > best_score:
                            best_score = candidate
                            best_back = (i - 1, a)

                back_score = suffix_best_scores[a][i] if a in suffix_best_scores else NEG_INF
                back_word = suffix_best_words[a][i] if a in suffix_best_words else None
                if back_word is not None and back_score > NEG_INF / 2:
                    candidate = back_score + segment_score
                    if candidate > best_score:
                        best_score = candidate
                        best_back = (back_word, a)

            dp[i][b] = best_score
            back[i][b] = best_back

    if dp[word_count - 1][bucket_count] <= NEG_INF / 2:
        raise RuntimeError("Segmental DP failed to produce a full alignment path.")

    bucket_to_word = [-1] * bucket_count
    phrase_trace: list[PhraseTrace] = []
    i = word_count - 1
    b = bucket_count
    while i is not None:
        prev = back[i][b]
        if prev is None:
            raise RuntimeError("Segmental DP path is missing a backpointer.")
        prev_i, a = prev
        for bucket_index in range(a, b):
            bucket_to_word[bucket_index] = i
        phrase_trace.append(
            PhraseTrace(
                previous_word_index=prev_i,
                start_word_index=i,
                end_word_index=i,
                start_bucket=a,
                end_bucket=b,
                repair_width=1 if prev_i is None else abs(prev_i - i) + 1,
            )
        )
        i = prev_i
        b = a
        if i is None and b != 0:
            raise RuntimeError("Segmental DP path terminated before reaching bucket 0.")

    phrase_trace.reverse()
    if any(word_index < 0 for word_index in bucket_to_word):
        raise RuntimeError("Segmental DP produced an incomplete bucket path.")

    frames = _frames_from_bucket_path(bucket_to_word, scoring_matrix, total_audio_ms, config.bucket_ms)
    runs = _runs_from_bucket_path(bucket_to_word, scoring_matrix, total_audio_ms, config.bucket_ms, tokens)
    debug_payload = None
    if collect_debug:
        debug_payload = {
            "bucket_count": bucket_count,
            "word_count": word_count,
            "bucket_ms": config.bucket_ms,
            "expected_lengths": [round(value, 3) for value in expected_lengths],
            "scoring_matrix": [
                [None if value <= NEG_INF / 2 else round(value, 4) for value in row]
                for row in scoring_matrix
            ],
            "dp_scores": [
                [None if value <= NEG_INF / 2 else round(value, 4) for value in row]
                for row in dp
            ],
            "backpointers": [
                [
                    None
                    if pointer is None
                    else {
                        "prev_word_index": pointer[0],
                        "prev_bucket": pointer[1],
                    }
                    for pointer in row
                ]
                for row in back
            ],
            "bucket_to_word": list(bucket_to_word),
        }
    return DecoderResult(
        bucket_to_word=bucket_to_word,
        frames=frames,
        runs=runs,
        total_score=dp[word_count - 1][bucket_count],
        scoring_matrix=scoring_matrix,
        phrase_trace=phrase_trace,
        debug=debug_payload,
    )


def decode_state_score_matrix(
    state_count: int,
    scoring_matrix: list[list[float]] | np.ndarray,
    config: DecoderConfig,
    *,
    is_word_end_state: list[bool] | None = None,
    is_word_start_state: list[bool] | None = None,
    bucket_silence_scores: list[float] | None = None,
    progress_callback=None,
) -> StateDecodeResult:
    """Decode the best time->state path from a raw score matrix.

    DP semantics:
    - `dp[i][b]` is the best score for explaining buckets `0..b-1` while ending in state `i`.
    - Normal forward progression is always allowed from `i-1 -> i`.
    - A same-state continuation is also allowed through the generic `previous_state == i` case.
    - Backtracking means jumping from a later state `j > i` back to an earlier state `i`
      while audio time still moves forward.

    The boundary options do not change the rest of the DP. They only gate the
    backward-jump branch. When enabled, a jump from `j > i` to `i` is legal only if:
    - the source state `j` is marked as a word-end state
    - the destination state `i` is marked as a word-start state

    Backtracking can also be penalized numerically. A true backward jump `j > i`
    subtracts `config.backtrack_penalty(j - i)` from its candidate score.
    """
    scoring_arr = np.ascontiguousarray(scoring_matrix, dtype=np.float64)
    if scoring_arr.ndim != 2:
        raise ValueError("scoring_matrix must be a 2-D array or list-of-rows.")
    sm_states, bucket_count = int(scoring_arr.shape[0]), int(scoring_arr.shape[1])
    if state_count <= 0 or bucket_count <= 0:
        return StateDecodeResult(bucket_to_state=[], total_score=0.0, dp_scores=[], backpointers=[])
    if sm_states != state_count:
        raise ValueError(f"scoring_matrix row count {sm_states} does not match state_count {state_count}.")
    if is_word_end_state is not None and len(is_word_end_state) != state_count:
        raise ValueError("is_word_end_state must have one entry per decoder state.")
    if is_word_start_state is not None and len(is_word_start_state) != state_count:
        raise ValueError("is_word_start_state must have one entry per decoder state.")
    if bucket_silence_scores is not None and len(bucket_silence_scores) != bucket_count:
        raise ValueError("bucket_silence_scores must have one entry per bucket.")

    if config.state_dp_engine == "native":
        return _decode_state_score_matrix_native(
            state_count,
            scoring_arr,
            config,
            is_word_end_state=is_word_end_state,
            is_word_start_state=is_word_start_state,
            bucket_silence_scores=bucket_silence_scores,
            progress_callback=progress_callback,
        )
    if config.state_dp_engine != "python":
        raise ValueError("state_dp_engine must be 'native' or 'python'.")

    if config.state_dp_mode not in {"jump", "step_by_step"}:
        raise ValueError("state_dp_mode must be 'jump' or 'step_by_step'.")

    fill_started_at = time.monotonic()

    prefix_sums = np.empty((state_count, bucket_count + 1), dtype=np.float64)
    prefix_sums[:, 0] = 0.0
    prefix_sums[:, 1:] = np.cumsum(scoring_arr, axis=1)

    if config.state_dp_mode == "jump":
        dp = [[NEG_INF] * (bucket_count + 1) for _ in range(state_count)]
        back: list[list[tuple[int | None, int] | None]] = [[None] * (bucket_count + 1) for _ in range(state_count)]
        constant_backtrack_penalty = config.backtrack_step_penalty == 0.0
        source_ok_by_state = (
            [True] * state_count
            if not config.backtrack_only_from_word_end or is_word_end_state is None
            else [bool(flag) for flag in is_word_end_state]
        )
        destination_ok_by_state = (
            [True] * state_count
            if not config.backtrack_only_to_word_start or is_word_start_state is None
            else [bool(flag) for flag in is_word_start_state]
        )
        local_scores = [0.0] * state_count
        suffix_any_scores = [NEG_INF] * state_count
        suffix_any_states = [-1] * state_count
        suffix_source_scores = [NEG_INF] * state_count
        suffix_source_states = [-1] * state_count

        for b in range(1, bucket_count + 1):
            if progress_callback is not None:
                progress_callback(
                    ProgressEvent(
                        stage="decode",
                        message=f"Filling DP bucket {b} of {bucket_count}",
                        completed=b,
                        total=bucket_count,
                    )
                )
            best_scores = [NEG_INF] * state_count
            best_backs: list[tuple[int | None, int] | None] = [None] * state_count
            start_low = max(0, b - config.max_phrase_buckets)
            for a in range(start_low, b):
                if constant_backtrack_penalty:
                    running_any_score = NEG_INF
                    running_any_state = -1
                    running_source_score = NEG_INF
                    running_source_state = -1
                    for state_index in range(state_count - 1, -1, -1):
                        prev_score = dp[state_index][a]
                        if prev_score > running_any_score:
                            running_any_score = prev_score
                            running_any_state = state_index
                        if source_ok_by_state[state_index] and prev_score > running_source_score:
                            running_source_score = prev_score
                            running_source_state = state_index
                        suffix_any_scores[state_index] = running_any_score
                        suffix_any_states[state_index] = running_any_state
                        suffix_source_scores[state_index] = running_source_score
                        suffix_source_states[state_index] = running_source_state

                for state_index in range(state_count):
                    local_scores[state_index] = float(prefix_sums[state_index, b] - prefix_sums[state_index, a])

                for state_index in range(state_count):
                    local_score = local_scores[state_index]
                    if state_index == 0 and a == 0 and local_score > best_scores[state_index]:
                        best_scores[state_index] = local_score
                        best_backs[state_index] = (None, 0)
                    if state_index > 0:
                        prev_score = dp[state_index - 1][a]
                        if prev_score > NEG_INF / 2:
                            candidate = prev_score + local_score
                            if candidate > best_scores[state_index]:
                                best_scores[state_index] = candidate
                                best_backs[state_index] = (state_index - 1, a)
                    stay_score = dp[state_index][a]
                    if stay_score > NEG_INF / 2:
                        candidate = stay_score + local_score
                        if candidate > best_scores[state_index]:
                            best_scores[state_index] = candidate
                            best_backs[state_index] = (state_index, a)
                    if constant_backtrack_penalty:
                        if destination_ok_by_state[state_index] and state_index + 1 < state_count:
                            if config.backtrack_only_from_word_end:
                                backtrack_score = suffix_source_scores[state_index + 1]
                                backtrack_state = suffix_source_states[state_index + 1]
                            else:
                                backtrack_score = suffix_any_scores[state_index + 1]
                                backtrack_state = suffix_any_states[state_index + 1]
                            if backtrack_state >= 0 and backtrack_score > NEG_INF / 2:
                                candidate = backtrack_score + local_score - config.backtrack_base_penalty
                                if candidate > best_scores[state_index]:
                                    best_scores[state_index] = candidate
                                    best_backs[state_index] = (backtrack_state, a)
                    else:
                        if not destination_ok_by_state[state_index]:
                            continue
                        for previous_state in range(state_index + 1, state_count):
                            if not source_ok_by_state[previous_state]:
                                continue
                            prev_score = dp[previous_state][a]
                            if prev_score <= NEG_INF / 2:
                                continue
                            candidate = prev_score + local_score - config.backtrack_penalty(previous_state - state_index)
                            if candidate > best_scores[state_index]:
                                best_scores[state_index] = candidate
                                best_backs[state_index] = (previous_state, a)
            for state_index in range(state_count):
                dp[state_index][b] = best_scores[state_index]
                back[state_index][b] = best_backs[state_index]
    else:
        dp = [[NEG_INF] * (bucket_count + 1) for _ in range(state_count)]
        back = [[None] * (bucket_count + 1) for _ in range(state_count)]
        constant_backtrack_penalty = config.backtrack_step_penalty == 0.0
        source_ok_by_state = (
            [True] * state_count
            if not config.backtrack_only_from_word_end or is_word_end_state is None
            else [bool(flag) for flag in is_word_end_state]
        )
        destination_ok_by_state = (
            [True] * state_count
            if not config.backtrack_only_to_word_start or is_word_start_state is None
            else [bool(flag) for flag in is_word_start_state]
        )
        suffix_source_scores = [NEG_INF] * state_count
        suffix_source_states = [-1] * state_count

        for b in range(1, bucket_count + 1):
            if progress_callback is not None:
                progress_callback(
                    ProgressEvent(
                        stage="decode",
                        message=f"Filling DP bucket {b} of {bucket_count}",
                        completed=b,
                        total=bucket_count,
                    )
                )
            bucket_index = b - 1
            local_scores = scoring_arr[:, bucket_index]
            if constant_backtrack_penalty:
                running_source_score = NEG_INF
                running_source_state = -1
                for state_index in range(state_count - 1, -1, -1):
                    if source_ok_by_state[state_index]:
                        prev_score = dp[state_index][b - 1]
                        if prev_score > running_source_score:
                            running_source_score = prev_score
                            running_source_state = state_index
                    suffix_source_scores[state_index] = running_source_score
                    suffix_source_states[state_index] = running_source_state

            for state_index in range(state_count):
                best_score = NEG_INF
                best_back: tuple[int | None, int] | None = None
                local_score = local_scores[state_index]

                if state_index == 0 and b == 1:
                    best_score = local_score
                    best_back = (None, 0)

                stay_prev = dp[state_index][b - 1]
                if stay_prev > NEG_INF / 2:
                    candidate = stay_prev + local_score
                    if candidate > best_score:
                        best_score = candidate
                        best_back = (state_index, b - 1)
                    if source_ok_by_state[state_index]:
                        silence_value = (
                            bucket_silence_scores[bucket_index]
                            if bucket_silence_scores is not None
                            else config.silence_stay_score
                        )
                        silence_candidate = stay_prev + silence_value
                        if silence_candidate > best_score:
                            best_score = silence_candidate
                            best_back = (state_index, b - 1)

                if state_index > 0:
                    prev_score = dp[state_index - 1][b - 1]
                    if prev_score > NEG_INF / 2:
                        candidate = prev_score + local_score
                        if candidate > best_score:
                            best_score = candidate
                            best_back = (state_index - 1, b - 1)

                if destination_ok_by_state[state_index] and state_index + 1 < state_count:
                    if constant_backtrack_penalty:
                        backtrack_score = suffix_source_scores[state_index + 1]
                        backtrack_state = suffix_source_states[state_index + 1]
                        if backtrack_state >= 0 and backtrack_score > NEG_INF / 2:
                            candidate = backtrack_score + local_score - config.backtrack_base_penalty
                            if candidate > best_score:
                                best_score = candidate
                                best_back = (backtrack_state, b - 1)
                    else:
                        for previous_state in range(state_index + 1, state_count):
                            if not source_ok_by_state[previous_state]:
                                continue
                            prev_score = dp[previous_state][b - 1]
                            if prev_score <= NEG_INF / 2:
                                continue
                            candidate = prev_score + local_score - config.backtrack_penalty(previous_state - state_index)
                            if candidate > best_score:
                                best_score = candidate
                                best_back = (previous_state, b - 1)

                dp[state_index][b] = best_score
                back[state_index][b] = best_back

    if dp[state_count - 1][bucket_count] <= NEG_INF / 2:
        raise RuntimeError("State DP failed to produce a full alignment path.")

    fill_elapsed = time.monotonic() - fill_started_at
    if progress_callback is not None:
        progress_callback(
            ProgressEvent(
                stage="align",
                message=f"Completed DP fill in {_format_duration_seconds(fill_elapsed)}",
            )
        )

    backtrack_started_at = time.monotonic()
    bucket_to_state = _backtrack_state_path(
        back,
        state_count,
        bucket_count,
        progress_callback=progress_callback,
    )
    backtrack_elapsed = time.monotonic() - backtrack_started_at
    if progress_callback is not None:
        progress_callback(
            ProgressEvent(
                stage="align",
                message=f"Completed DP backtracking in {_format_duration_seconds(backtrack_elapsed)}",
            )
        )

    return StateDecodeResult(
        bucket_to_state=bucket_to_state,
        total_score=dp[state_count - 1][bucket_count],
        dp_scores=dp,
        backpointers=back,
    )


def _decode_state_score_matrix_native(
    state_count: int,
    scoring_arr: np.ndarray,
    config: DecoderConfig,
    *,
    is_word_end_state: list[bool] | None,
    is_word_start_state: list[bool] | None,
    bucket_silence_scores: list[float] | None,
    progress_callback=None,
) -> StateDecodeResult:
    fill_started_at = time.monotonic()
    if scoring_arr.ndim != 2:
        raise ValueError("native decode expects a 2-D scoring matrix")
    bucket_count = int(scoring_arr.shape[1])
    if state_count <= 0 or bucket_count <= 0:
        return StateDecodeResult(bucket_to_state=[], total_score=0.0, dp_scores=[], backpointers=[])

    library = load_native_library()
    n_scores = state_count * bucket_count
    flat = np.ascontiguousarray(scoring_arr, dtype=np.float64).ravel(order="C")
    if flat.size != n_scores:
        raise ValueError("scoring matrix size does not match state_count * bucket_count")
    score_buffer = (ctypes.c_double * n_scores)()
    ctypes.memmove(
        ctypes.addressof(score_buffer),
        flat.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        n_scores * ctypes.sizeof(ctypes.c_double),
    )
    end_mask_values = [1 if flag else 0 for flag in (is_word_end_state or [False] * state_count)]
    start_mask_values = [1 if flag else 0 for flag in (is_word_start_state or [False] * state_count)]
    end_mask = (ctypes.c_uint8 * len(end_mask_values))(*end_mask_values)
    start_mask = (ctypes.c_uint8 * len(start_mask_values))(*start_mask_values)
    silence_buffer = None
    silence_ptr = None
    if bucket_silence_scores is not None:
        nb = len(bucket_silence_scores)
        silence_buffer = (ctypes.c_double * nb)()
        sil_flat = np.asarray(bucket_silence_scores, dtype=np.float64).ravel()
        ctypes.memmove(
            ctypes.addressof(silence_buffer),
            sil_flat.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            nb * ctypes.sizeof(ctypes.c_double),
        )
        silence_ptr = silence_buffer

    total_cells = state_count * (bucket_count + 1)
    dp_buffer = (ctypes.c_double * total_cells)()
    prev_state_buffer = (ctypes.c_int * total_cells)()
    prev_bucket_buffer = (ctypes.c_int * total_cells)()
    callback_type = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int)
    progress_holder = None
    progress_ptr = None
    if progress_callback is not None:
        def _progress_native(completed: int, total: int) -> None:
            progress_callback(
                ProgressEvent(
                    stage="decode",
                    message=f"Filling DP bucket {completed} of {total}",
                    completed=completed,
                    total=total,
                )
            )
        progress_holder = callback_type(_progress_native)
        progress_ptr = progress_holder

    status = library.decode_state_dp_native(
        state_count,
        bucket_count,
        score_buffer,
        config.max_phrase_buckets,
        end_mask,
        start_mask,
        1 if config.backtrack_only_from_word_end else 0,
        1 if config.backtrack_only_to_word_start else 0,
        config.backtrack_base_penalty,
        config.backtrack_step_penalty,
        1 if config.state_dp_mode == "step_by_step" else 0,
        config.silence_stay_score,
        silence_ptr,
        dp_buffer,
        prev_state_buffer,
        prev_bucket_buffer,
        progress_ptr,
    )
    if status != 0:
        raise RuntimeError(f"Native DP kernel failed with status {status}.")

    if progress_callback is not None:
        progress_callback(
            ProgressEvent(
                stage="align",
                message=(
                    "Native DP fill done; packing dp/back as NumPy arrays "
                    f"({state_count}×{bucket_count + 1} cells)"
                ),
            )
        )

    dp_arr = np.ctypeslib.as_array(dp_buffer).reshape(state_count, bucket_count + 1).copy()
    prev_s_arr = np.ctypeslib.as_array(prev_state_buffer).reshape(state_count, bucket_count + 1).copy()
    prev_b_arr = np.ctypeslib.as_array(prev_bucket_buffer).reshape(state_count, bucket_count + 1).copy()

    if float(dp_arr[state_count - 1, bucket_count]) <= NEG_INF / 2:
        raise RuntimeError("State DP failed to produce a full alignment path.")

    fill_elapsed = time.monotonic() - fill_started_at
    if progress_callback is not None:
        progress_callback(
            ProgressEvent(
                stage="align",
                message=f"Completed DP fill in {_format_duration_seconds(fill_elapsed)}",
            )
        )

    backtrack_started_at = time.monotonic()
    bucket_to_state = _backtrack_state_path_numpy(
        prev_s_arr,
        prev_b_arr,
        state_count,
        bucket_count,
        progress_callback=progress_callback,
    )
    backtrack_elapsed = time.monotonic() - backtrack_started_at
    if progress_callback is not None:
        progress_callback(
            ProgressEvent(
                stage="align",
                message=f"Completed DP backtracking in {_format_duration_seconds(backtrack_elapsed)}",
            )
        )

    return StateDecodeResult(
        bucket_to_state=bucket_to_state,
        total_score=float(dp_arr[state_count - 1, bucket_count]),
        dp_scores=dp_arr,
        backpointers=(prev_s_arr, prev_b_arr),
    )


def score_matrix_at(scoring_matrix: list[list[float]] | np.ndarray, row: int, col: int) -> float:
    if isinstance(scoring_matrix, np.ndarray):
        return float(scoring_matrix[row, col])
    return float(scoring_matrix[row][col])


def _frames_from_bucket_path(
    bucket_to_word: list[int],
    scoring_matrix: list[list[float]] | np.ndarray,
    total_audio_ms: int,
    bucket_ms: int,
) -> list[FrameAlignment]:
    frames: list[FrameAlignment] = []
    for bucket_index, word_index in enumerate(bucket_to_word):
        start_ms = bucket_index * bucket_ms
        end_ms = min(total_audio_ms, start_ms + bucket_ms)
        frames.append(
            FrameAlignment(
                frame_index=bucket_index,
                start_ms=start_ms,
                end_ms=end_ms,
                global_unit_index=None,
                global_word_index=word_index,
                score=score_matrix_at(scoring_matrix, word_index, bucket_index),
            )
        )
    return frames


def _runs_from_bucket_path(
    bucket_to_word: list[int],
    scoring_matrix: list[list[float]] | np.ndarray,
    total_audio_ms: int,
    bucket_ms: int,
    tokens: list[TokenRef],
) -> list[AlignmentRunSegment]:
    if not bucket_to_word:
        return []
    runs: list[AlignmentRunSegment] = []
    run_start = 0
    current_word = bucket_to_word[0]
    for bucket_index in range(1, len(bucket_to_word) + 1):
        at_end = bucket_index == len(bucket_to_word)
        next_word = None if at_end else bucket_to_word[bucket_index]
        if not at_end and next_word == current_word:
            continue
        run_end = bucket_index
        word = tokens[current_word].normalized_word if 0 <= current_word < len(tokens) else ""
        frame_count = run_end - run_start
        run_score = sum(score_matrix_at(scoring_matrix, current_word, idx) for idx in range(run_start, run_end)) / max(
            1, frame_count
        )
        runs.append(
            AlignmentRunSegment(
                run_index=len(runs),
                global_word_index=current_word,
                word=word,
                start_ms=run_start * bucket_ms,
                end_ms=min(total_audio_ms, run_end * bucket_ms),
                score=run_score,
                frame_count=frame_count,
            )
        )
        run_start = bucket_index
        if not at_end:
            current_word = next_word
    return runs


def _word_weight(word: str) -> int:
    weight = max(1, len(word))
    if len(word) <= 2:
        weight += 1
    return weight
