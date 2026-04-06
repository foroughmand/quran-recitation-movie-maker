from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import median

from .models import AlignmentResult, AudioGap, SuspiciousWord, TokenRef, WordAlignment
from .refinement import compute_audio_gaps, infer_total_audio_ms, score_to_confidence


@dataclass(slots=True)
class SuspiciousRegion:
    start_word_index: int
    end_word_index: int
    start_ms: int
    end_ms: int
    reason: str


@dataclass(slots=True)
class RefinementProposal:
    start_word_index: int
    end_word_index: int
    old_local_score: float
    new_local_score: float
    score_improvement: float
    replacement_words: list[WordAlignment]
    start_ms: int
    end_ms: int
    accepted: bool
    reason: str


def _validate_local_phrase_words(local_phrase_words: int) -> int:
    if local_phrase_words < 1:
        raise ValueError("local_phrase_words must be at least 1")
    if local_phrase_words % 2 == 0:
        raise ValueError("local_phrase_words must be an odd number")
    return local_phrase_words


def find_suspicious_words(
    result: AlignmentResult,
    *,
    min_word_confidence: float,
    gaps: list[AudioGap],
) -> list[SuspiciousWord]:
    confidences = [score_to_confidence(word.score) for word in result.words]
    neighborhood_median = median(confidences) if confidences else 0.0
    gap_by_index: dict[int, list[AudioGap]] = {}
    for gap in gaps:
        if gap.left_word_index is not None:
            gap_by_index.setdefault(gap.left_word_index, []).append(gap)
        if gap.right_word_index is not None:
            gap_by_index.setdefault(gap.right_word_index, []).append(gap)

    suspicious: list[SuspiciousWord] = []
    for word in result.words:
        confidence = score_to_confidence(word.score)
        flags: list[str] = []
        if confidence < min_word_confidence:
            flags.append("low_score")
        if confidence + 0.12 < neighborhood_median:
            flags.append("local_score_drop")
        if any(gap.duration_ms >= 250 for gap in gap_by_index.get(word.global_word_index, [])):
            flags.append("adjacent_gap")
        if flags:
            suspicious.append(
                SuspiciousWord(
                    global_word_index=word.global_word_index,
                    reason=", ".join(flags),
                    score=word.score,
                    start_ms=word.start_ms,
                    end_ms=word.end_ms,
                    flags=flags,
                )
            )
    return suspicious


def build_local_phrase_windows(
    suspicious_words: list[SuspiciousWord],
    total_words: int,
    *,
    local_phrase_words: int,
    word_alignments: list[WordAlignment],
    window_padding_ms: int,
) -> list[SuspiciousRegion]:
    local_phrase_words = _validate_local_phrase_words(local_phrase_words)
    if not suspicious_words or total_words <= 0:
        return []

    half_width = local_phrase_words // 2
    regions: list[SuspiciousRegion] = []
    seen_ranges: set[tuple[int, int]] = set()

    for suspicious in sorted(suspicious_words, key=lambda item: item.global_word_index):
        center = suspicious.global_word_index
        start_word_index = max(0, center - half_width)
        end_word_index = min(total_words - 1, center + half_width)

        while end_word_index - start_word_index + 1 < local_phrase_words and start_word_index > 0:
            start_word_index -= 1
        while end_word_index - start_word_index + 1 < local_phrase_words and end_word_index < total_words - 1:
            end_word_index += 1

        key = (start_word_index, end_word_index)
        if key in seen_ranges:
            continue
        seen_ranges.add(key)

        regions.append(
            SuspiciousRegion(
                start_word_index=start_word_index,
                end_word_index=end_word_index,
                start_ms=max(0, word_alignments[start_word_index].start_ms - window_padding_ms),
                end_ms=word_alignments[end_word_index].end_ms + window_padding_ms,
                reason=suspicious.reason,
            )
        )
    return regions


def select_non_overlapping_proposals(
    proposals: list[RefinementProposal],
) -> list[RefinementProposal]:
    selected: list[RefinementProposal] = []
    occupied: list[tuple[int, int]] = []

    for proposal in sorted(
        (item for item in proposals if item.accepted),
        key=lambda item: item.score_improvement,
        reverse=True,
    ):
        overlaps = any(
            not (proposal.end_word_index < start or proposal.start_word_index > end)
            for start, end in occupied
        )
        if overlaps:
            continue
        selected.append(proposal)
        occupied.append((proposal.start_word_index, proposal.end_word_index))

    return sorted(selected, key=lambda item: item.start_word_index)


def apply_refinement_proposals(
    original_words: list[WordAlignment],
    proposals: list[RefinementProposal],
) -> list[WordAlignment]:
    refined_words = [replace(word) for word in original_words]
    for proposal in proposals:
        for index, replacement in enumerate(proposal.replacement_words, start=proposal.start_word_index):
            refined_words[index] = replace(replacement, global_word_index=index)
    return refined_words


def refine_alignment_with_emissions(
    tokens: list[TokenRef],
    result: AlignmentResult,
    *,
    backend,
    audio_path: str,
    min_word_confidence: float = 0.45,
    window_padding_ms: int = 250,
    min_score_improvement: float = 0.05,
    local_phrase_words: int = 3,
) -> tuple[AlignmentResult, list[SuspiciousRegion], list[str], list[SuspiciousWord], list[AudioGap]]:
    local_phrase_words = _validate_local_phrase_words(local_phrase_words)
    total_audio_ms = infer_total_audio_ms(audio_path, result)
    gaps = compute_audio_gaps(result, total_audio_ms)
    suspicious_words = find_suspicious_words(
        result,
        min_word_confidence=min_word_confidence,
        gaps=gaps,
    )
    regions = build_local_phrase_windows(
        suspicious_words,
        len(result.words),
        local_phrase_words=local_phrase_words,
        word_alignments=result.words,
        window_padding_ms=window_padding_ms,
    )
    if not regions or not hasattr(backend, "local_realign"):
        return result, regions, [], suspicious_words, gaps

    proposals: list[RefinementProposal] = []
    region_logs: list[dict[str, object]] = []

    for region in regions:
        local_tokens = tokens[region.start_word_index : region.end_word_index + 1]
        old_local_words = result.words[region.start_word_index : region.end_word_index + 1]
        old_local_score = sum(word.score for word in old_local_words)
        new_local = backend.local_realign(audio_path, local_tokens, region.start_ms, region.end_ms)
        new_local_score = sum(word.score for word in new_local.words)
        score_improvement = new_local_score - old_local_score
        accepted = score_improvement > min_score_improvement

        proposal = RefinementProposal(
            start_word_index=region.start_word_index,
            end_word_index=region.end_word_index,
            old_local_score=old_local_score,
            new_local_score=new_local_score,
            score_improvement=score_improvement,
            replacement_words=[
                replace(word, global_word_index=region.start_word_index + offset)
                for offset, word in enumerate(new_local.words)
            ],
            start_ms=region.start_ms,
            end_ms=region.end_ms,
            accepted=accepted,
            reason=region.reason,
        )
        proposals.append(proposal)

        region_logs.append(
            {
                "trigger_region": {
                    "start_word_index": region.start_word_index,
                    "end_word_index": region.end_word_index,
                    "start_ms": region.start_ms,
                    "end_ms": region.end_ms,
                    "reason": region.reason,
                },
                "phrase_window": {
                    "start_word_index": region.start_word_index,
                    "end_word_index": region.end_word_index,
                    "start_ms": region.start_ms,
                    "end_ms": region.end_ms,
                    "duration_ms": max(0, region.end_ms - region.start_ms),
                },
                "center_word_index": (region.start_word_index + region.end_word_index) // 2,
                "local_phrase_words": local_phrase_words,
                "words": [
                    {
                        "global_word_index": region.start_word_index + offset,
                        "ayah_number": token.ayah_number,
                        "original_word": token.original_word,
                        "normalized_word": token.normalized_word,
                        "old_start_ms": old_word.start_ms,
                        "old_end_ms": old_word.end_ms,
                        "old_score": old_word.score,
                        "new_start_ms": new_word.start_ms if offset < len(new_local.words) else None,
                        "new_end_ms": new_word.end_ms if offset < len(new_local.words) else None,
                        "new_score": new_word.score if offset < len(new_local.words) else None,
                    }
                    for offset, (token, old_word) in enumerate(zip(local_tokens, old_local_words))
                    for new_word in [new_local.words[offset] if offset < len(new_local.words) else None]
                ],
                "old_local_score": old_local_score,
                "new_local_score": new_local_score,
                "score_improvement": score_improvement,
                "acceptance_margin": min_score_improvement,
                "decision": "accepted" if accepted else "rejected",
            }
        )

    selected_proposals = select_non_overlapping_proposals(proposals)
    refined_words = apply_refinement_proposals(result.words, selected_proposals)
    refined_total_score = sum(word.score for word in refined_words)
    refined_result = replace(
        result,
        words=refined_words,
        total_score=refined_total_score,
        metadata={
            **result.metadata,
            "refinement_region_logs": region_logs,
            "local_phrase_words": local_phrase_words,
            "attempted_refinement_windows": len(regions),
            "accepted_refinement_windows": sum(1 for item in proposals if item.accepted),
            "selected_refinement_windows": len(selected_proposals),
        },
    )
    refined_gaps = compute_audio_gaps(refined_result, total_audio_ms)
    refined_suspicious = find_suspicious_words(
        refined_result,
        min_word_confidence=min_word_confidence,
        gaps=refined_gaps,
    )
    notes = [
        f"Suspicious regions considered: {len(regions)}",
        f"Accepted proposals: {sum(1 for item in proposals if item.accepted)}",
        f"Selected non-overlapping proposals: {len(selected_proposals)}",
    ]
    return refined_result, regions, notes, refined_suspicious, refined_gaps
