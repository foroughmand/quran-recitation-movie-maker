from __future__ import annotations

import math

from .models import AlignmentResult, AudioGap
from .mp3 import read_mp3_info


def score_to_confidence(score: float) -> float:
    if 0.0 <= score <= 1.0:
        return score
    return max(0.0, min(1.0, math.exp(score / 15.0)))


def infer_total_audio_ms(audio_path: str, result: AlignmentResult) -> int:
    if "total_audio_ms" in result.metadata:
        return int(result.metadata["total_audio_ms"])
    if audio_path.lower().endswith(".mp3"):
        return int(round(read_mp3_info(audio_path).duration_seconds * 1000))
    return max((word.end_ms for word in result.words), default=0)


def compute_audio_gaps(
    result: AlignmentResult,
    total_audio_ms: int,
    suspicious_indices: set[int] | None = None,
) -> list[AudioGap]:
    suspicious_indices = suspicious_indices or set()
    words = sorted(result.words, key=lambda item: item.start_ms)
    gaps: list[AudioGap] = []

    def classify_gap(duration_ms: int, left_idx: int | None, right_idx: int | None, kind: str) -> str:
        if duration_ms < 80:
            return "tiny_gap"
        if kind != "between":
            return "likely_pause"
        left_suspicious = left_idx in suspicious_indices
        right_suspicious = right_idx in suspicious_indices
        if duration_ms >= 1200 and left_suspicious and right_suspicious:
            return "possible_repeat_region"
        if duration_ms >= 350 and (left_suspicious or right_suspicious):
            return "likely_boundary_error"
        return "likely_pause"

    if words:
        leading_gap = words[0].start_ms
        if leading_gap >= 20:
            gaps.append(
                AudioGap(
                    start_ms=0,
                    end_ms=words[0].start_ms,
                    duration_ms=leading_gap,
                    left_word_index=None,
                    right_word_index=words[0].global_word_index,
                    kind="leading",
                    classification=classify_gap(leading_gap, None, words[0].global_word_index, "leading"),
                )
            )

    for left, right in zip(words, words[1:]):
        gap_duration = right.start_ms - left.end_ms
        if gap_duration < 20:
            continue
        gaps.append(
            AudioGap(
                start_ms=left.end_ms,
                end_ms=right.start_ms,
                duration_ms=gap_duration,
                left_word_index=left.global_word_index,
                right_word_index=right.global_word_index,
                kind="between",
                classification=classify_gap(gap_duration, left.global_word_index, right.global_word_index, "between"),
            )
        )

    if words:
        trailing_gap = total_audio_ms - words[-1].end_ms
        if trailing_gap >= 20:
            gaps.append(
                AudioGap(
                    start_ms=words[-1].end_ms,
                    end_ms=total_audio_ms,
                    duration_ms=trailing_gap,
                    left_word_index=words[-1].global_word_index,
                    right_word_index=None,
                    kind="trailing",
                    classification=classify_gap(trailing_gap, words[-1].global_word_index, None, "trailing"),
                )
            )

    return gaps
