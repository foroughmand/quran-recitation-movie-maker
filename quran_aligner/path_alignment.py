from __future__ import annotations

from dataclasses import replace

from .models import (
    AlignmentResult,
    AlignmentRunSegment,
    FrameAlignment,
    TimeInterval,
    TokenRef,
    WordAlignment,
    WordOccurrence,
)


def build_runs_from_frames(
    frames: list[FrameAlignment],
    tokens: list[TokenRef],
) -> list[AlignmentRunSegment]:
    runs: list[AlignmentRunSegment] = []
    current: FrameAlignment | None = None
    current_frames: list[FrameAlignment] = []

    def flush() -> None:
        nonlocal current, current_frames
        if current is None or current.global_word_index is None or not current_frames:
            current = None
            current_frames = []
            return
        word_index = current.global_word_index
        frame_count = len(current_frames)
        mean_score = sum(frame.score for frame in current_frames) / max(1, frame_count)
        word = tokens[word_index].normalized_word if 0 <= word_index < len(tokens) else ""
        runs.append(
            AlignmentRunSegment(
                run_index=len(runs),
                global_word_index=word_index,
                word=word,
                start_ms=current_frames[0].start_ms,
                end_ms=current_frames[-1].end_ms,
                score=mean_score,
                frame_count=frame_count,
            )
        )
        current = None
        current_frames = []

    for frame in frames:
        if current is None:
            current = frame
            current_frames = [frame]
            continue
        contiguous = frame.start_ms <= current_frames[-1].end_ms
        same_word = frame.global_word_index == current.global_word_index
        if same_word and contiguous:
            current_frames.append(frame)
            current = frame
            continue
        flush()
        current = frame
        current_frames = [frame]

    flush()
    return runs


def build_occurrences_from_runs(runs: list[AlignmentRunSegment]) -> list[WordOccurrence]:
    by_word: dict[int, list[AlignmentRunSegment]] = {}
    for run in runs:
        by_word.setdefault(run.global_word_index, []).append(run)

    occurrences: list[WordOccurrence] = []
    for global_word_index in sorted(by_word):
        word_runs = by_word[global_word_index]
        occurrences.append(
            WordOccurrence(
                global_word_index=global_word_index,
                word=word_runs[0].word if word_runs else "",
                intervals=[
                    TimeInterval(start_ms=run.start_ms, end_ms=run.end_ms)
                    for run in word_runs
                ],
                total_duration_ms=sum(max(0, run.end_ms - run.start_ms) for run in word_runs),
                visit_count=len(word_runs),
            )
        )
    return occurrences


def summarize_words_from_runs(
    runs: list[AlignmentRunSegment],
    tokens: list[TokenRef],
) -> list[WordAlignment]:
    by_word: dict[int, list[AlignmentRunSegment]] = {}
    for run in runs:
        by_word.setdefault(run.global_word_index, []).append(run)

    summaries: list[WordAlignment] = []
    for word_index, token in enumerate(tokens):
        word_runs = by_word.get(word_index, [])
        if not word_runs:
            summaries.append(
                WordAlignment(
                    global_word_index=word_index,
                    word=token.normalized_word,
                    start_ms=0,
                    end_ms=0,
                    score=0.0,
                )
            )
            continue
        best_run = max(
            word_runs,
            key=lambda run: (max(0, run.end_ms - run.start_ms), run.score, -run.start_ms),
        )
        summaries.append(
            WordAlignment(
                global_word_index=word_index,
                word=token.normalized_word,
                start_ms=best_run.start_ms,
                end_ms=best_run.end_ms,
                score=best_run.score,
            )
        )
    return summaries


def populate_path_outputs(
    *,
    result: AlignmentResult,
    tokens: list[TokenRef],
    frames: list[FrameAlignment] | None = None,
    runs: list[AlignmentRunSegment] | None = None,
) -> AlignmentResult:
    resolved_frames = [
        replace(frame, frame_index=index)
        for index, frame in enumerate(frames if frames is not None else result.frame_alignments)
    ]
    resolved_runs = [
        replace(run, run_index=index)
        for index, run in enumerate(runs if runs is not None else result.word_runs)
    ]
    if not resolved_runs and resolved_frames:
        resolved_runs = build_runs_from_frames(resolved_frames, tokens)
    occurrences = build_occurrences_from_runs(resolved_runs) if resolved_runs else list(result.word_occurrences)
    words = summarize_words_from_runs(resolved_runs, tokens) if resolved_runs else [replace(word) for word in result.words]
    return replace(
        result,
        words=words,
        frame_alignments=resolved_frames,
        word_runs=resolved_runs,
        word_occurrences=occurrences,
    )
