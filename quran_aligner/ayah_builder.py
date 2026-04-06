from __future__ import annotations

from collections import defaultdict
from statistics import median

from .models import AlignmentQuality, AlignmentResult, AudioGap, AyahAlignment, TokenRef, WordAlignment
from .refinement import score_to_confidence


def build_ayah_alignments(tokens: list[TokenRef], alignment: AlignmentResult) -> list[AyahAlignment]:
    token_lookup = {index: token for index, token in enumerate(tokens)}
    grouped: dict[int, list[tuple[TokenRef, WordAlignment]]] = defaultdict(list)

    for word_alignment in alignment.words:
        token = token_lookup.get(word_alignment.global_word_index)
        if token is None:
            continue
        grouped[token.ayah_number].append((token, word_alignment))

    ayahs: list[AyahAlignment] = []
    for ayah_number in sorted(grouped):
        if ayah_number == 0:
            continue
        items = grouped[ayah_number]
        ayahs.append(
            AyahAlignment(
                ayah_number=ayah_number,
                start_ms=min(word.start_ms for _, word in items),
                end_ms=max(word.end_ms for _, word in items),
                word_count=len(items),
                mean_score=sum(word.score for _, word in items) / len(items),
            )
        )
    return ayahs


def evaluate_alignment_quality(
    tokens: list[TokenRef],
    alignment: AlignmentResult,
    ayahs: list[AyahAlignment],
    *,
    min_coverage: float = 0.85,
    min_word_score: float = 0.45,
    gaps: list[AudioGap] | None = None,
    suspicious_word_count: int = 0,
    total_audio_ms: int | None = None,
) -> AlignmentQuality:
    total_word_count = len([token for token in tokens if token.ayah_number != 0]) or 1
    aligned_words = [item for item in alignment.words if item.global_word_index < len(tokens)]
    zero_length_count = sum(1 for item in aligned_words if item.end_ms <= item.start_ms)
    has_decreasing = any(
        current.start_ms < previous.start_ms or current.end_ms < previous.end_ms
        for previous, current in zip(aligned_words, aligned_words[1:])
    )
    has_overlaps = any(current.start_ms < previous.end_ms for previous, current in zip(ayahs, ayahs[1:]))
    coverage = len([token for token in aligned_words if tokens[token.global_word_index].ayah_number != 0]) / total_word_count
    confidences = [score_to_confidence(word.score) for word in aligned_words]
    average_word_score = sum(confidences) / max(1, len(confidences))
    median_word_score = median(confidences) if confidences else 0.0
    low_score_ratio = sum(1 for confidence in confidences if confidence < min_word_score) / max(1, len(confidences))
    gaps = gaps or []
    uncovered_gap_ratio = sum(gap.duration_ms for gap in gaps) / max(1, total_audio_ms or max((word.end_ms for word in aligned_words), default=1))

    warnings: list[str] = []
    if coverage < min_coverage:
        warnings.append(f"Low alignment coverage: {coverage:.1%}")
    if zero_length_count:
        warnings.append(f"{zero_length_count} zero-length word spans detected")
    if has_decreasing:
        warnings.append("Word timestamps are not monotonic")
    if has_overlaps:
        warnings.append("Ayah spans overlap")
    if low_score_ratio > 0.2:
        warnings.append("High ratio of low-confidence words")
    if uncovered_gap_ratio > 0.08 or len(gaps) >= 10:
        warnings.append("Large uncovered audio regions")
    if suspicious_word_count:
        warnings.append("Suspicious local phrase boundaries detected")

    return AlignmentQuality(
        coverage=coverage,
        zero_length_ratio=zero_length_count / max(1, len(aligned_words)),
        has_decreasing_timestamps=has_decreasing,
        has_overlapping_ayahs=has_overlaps,
        average_word_score=average_word_score,
        median_word_score=median_word_score,
        low_score_ratio=low_score_ratio,
        gap_count=len(gaps),
        uncovered_gap_ratio=uncovered_gap_ratio,
        warnings=warnings,
    )
