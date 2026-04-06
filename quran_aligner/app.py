from __future__ import annotations

from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import shutil
import time

from .acoustic_refinement import refine_alignment_with_emissions
from .aligner.base import AlignmentBackend, make_backend
from .ayah_builder import build_ayah_alignments, evaluate_alignment_quality
from .models import AlignmentResult, AlignmentRun, RefinementReport, SurahText
from .normalizer import (
    DEFAULT_CTC_ALIGNMENT_MODEL,
    LIGHT_NORMALIZATION,
    NormalizationConfig,
    choose_normalization_profile,
    flatten_surah_to_tokens,
    prepare_target_text,
    resolve_normalization_config,
)
from .path_alignment import populate_path_outputs
from .progress import ProgressEvent
from .refinement import infer_total_audio_ms, score_to_confidence
from .region_debug_page import write_region_debug_data_js, write_region_debug_html
from .review_page import write_review_html
from .text_provider import fetch_surah_text
from .writer import serialize_run, write_alignment_txt, write_debug_json


def _format_ms(ms: int) -> str:
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    millis = ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def _format_duration_seconds(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _worst_words(run: AlignmentRun, limit: int = 20) -> list[dict[str, object]]:
    word_rows = []
    for word in run.result.words:
        token = run.tokens[word.global_word_index]
        if token.ayah_number == 0:
            continue
        suspicious = next((item for item in run.suspicious_words if item.global_word_index == word.global_word_index), None)
        word_rows.append(
            {
                "id": word.global_word_index + 1,
                "text": token.original_word,
                "ayah_number": token.ayah_number,
                "score": word.score,
                "confidence": score_to_confidence(word.score),
                "flags": suspicious.flags if suspicious else [],
            }
        )
    return sorted(word_rows, key=lambda item: item["confidence"])[:limit]


def _largest_gaps(run: AlignmentRun, limit: int = 20) -> list[dict[str, object]]:
    return [
        {
            "start_ms": gap.start_ms,
            "end_ms": gap.end_ms,
            "duration_ms": gap.duration_ms,
            "classification": gap.classification,
            "kind": gap.kind,
        }
        for gap in sorted(run.gaps, key=lambda item: item.duration_ms, reverse=True)[:limit]
    ]


def _lowest_ayahs(run: AlignmentRun, limit: int = 20) -> list[dict[str, object]]:
    return [
        {
            "ayah_number": ayah.ayah_number,
            "mean_score": ayah.mean_score,
            "confidence": score_to_confidence(ayah.mean_score),
            "start_ms": ayah.start_ms,
            "end_ms": ayah.end_ms,
        }
        for ayah in sorted(run.ayah_alignments, key=lambda item: score_to_confidence(item.mean_score))[:limit]
    ]


def _build_review_payload(
    run: AlignmentRun,
    audio_path: Path,
    output_dir: Path,
    mode: str,
    *,
    show_suspicious_only: bool,
) -> dict[str, object]:
    initial_words = run.initial_result.words if run.initial_result is not None else run.result.words
    word_rows = []
    before_rows = []
    by_ayah: dict[int, list[dict[str, object]]] = {}
    suspicious_lookup = {item.global_word_index: item for item in run.suspicious_words}
    for word_alignment in initial_words:
        token = run.tokens[word_alignment.global_word_index]
        if token.ayah_number == 0:
            continue
        before_rows.append(
            {
                "global_word_index": word_alignment.global_word_index,
                "ayah_number": token.ayah_number,
                "text": token.original_word,
                "start_ms": word_alignment.start_ms,
                "end_ms": word_alignment.end_ms,
                "score": word_alignment.score,
                "confidence": score_to_confidence(word_alignment.score),
            }
        )
    for index, word_alignment in enumerate(run.result.words, start=1):
        token = run.tokens[word_alignment.global_word_index]
        if token.ayah_number == 0:
            continue
        suspicious = suspicious_lookup.get(word_alignment.global_word_index)
        row = {
            "id": index,
            "global_word_index": word_alignment.global_word_index,
            "ayah_number": token.ayah_number,
            "word_index_in_ayah": token.word_index_in_ayah,
            "text": token.original_word,
            "normalized": token.normalized_word,
            "normalization_profile": token.normalization_profile,
            "start_ms": word_alignment.start_ms,
            "end_ms": word_alignment.end_ms,
            "score": word_alignment.score,
            "confidence": score_to_confidence(word_alignment.score),
            "flags": suspicious.flags if suspicious else [],
            "is_suspicious": suspicious is not None,
        }
        word_rows.append(row)
        by_ayah.setdefault(token.ayah_number, []).append(row)

    run_rows = []
    for run_segment in run.result.word_runs:
        token = run.tokens[run_segment.global_word_index]
        if token.ayah_number == 0:
            continue
        run_rows.append(
            {
                "run_index": run_segment.run_index,
                "global_word_index": run_segment.global_word_index,
                "ayah_number": token.ayah_number,
                "word_index_in_ayah": token.word_index_in_ayah,
                "text": token.original_word,
                "normalized": token.normalized_word,
                "start_ms": run_segment.start_ms,
                "end_ms": run_segment.end_ms,
                "score": run_segment.score,
                "frame_count": run_segment.frame_count,
            }
        )

    occurrence_rows = []
    for occurrence in run.result.word_occurrences:
        token = run.tokens[occurrence.global_word_index]
        if token.ayah_number == 0:
            continue
        occurrence_rows.append(
            {
                "global_word_index": occurrence.global_word_index,
                "ayah_number": token.ayah_number,
                "word_index_in_ayah": token.word_index_in_ayah,
                "text": token.original_word,
                "normalized": token.normalized_word,
                "visit_count": occurrence.visit_count,
                "total_duration_ms": occurrence.total_duration_ms,
                "intervals": [
                    {
                        "start_ms": interval.start_ms,
                        "end_ms": interval.end_ms,
                    }
                    for interval in occurrence.intervals
                ],
            }
        )

    ayah_text_lookup = {ayah.ayah_number: ayah.text for ayah in run.surah.ayahs if ayah.ayah_number != 0}
    ayah_rows = [
        {
            "ayah_number": ayah.ayah_number,
            "text": ayah_text_lookup.get(ayah.ayah_number, ""),
            "start_ms": ayah.start_ms,
            "end_ms": ayah.end_ms,
            "words": by_ayah.get(ayah.ayah_number, []),
        }
        for ayah in run.ayah_alignments
    ]
    duration_ms = max((item["end_ms"] for item in word_rows), default=0)
    return {
        "title": f"Surah {run.surah.surah_number} alignment review",
        "surah_number": run.surah.surah_number,
        "mode": mode,
        "backend": run.result.backend,
        "normalization_profile": run.tokens[0].normalization_profile if run.tokens else LIGHT_NORMALIZATION.profile_name,
        "audio": {
            "path": str(audio_path),
            "relative_path": os.path.relpath(audio_path, output_dir),
            "duration_ms": infer_total_audio_ms(str(audio_path), run.result),
            "duration_label": _format_ms(infer_total_audio_ms(str(audio_path), run.result)),
        },
        "words": word_rows,
        "frame_path": [
            {
                "frame_index": frame.frame_index,
                "start_ms": frame.start_ms,
                "end_ms": frame.end_ms,
                "global_unit_index": frame.global_unit_index,
                "global_word_index": frame.global_word_index,
                "score": frame.score,
            }
            for frame in run.result.frame_alignments
            if frame.global_word_index is not None
            and 0 <= frame.global_word_index < len(run.tokens)
            and run.tokens[frame.global_word_index].ayah_number != 0
        ],
        "word_runs": run_rows,
        "word_occurrences": occurrence_rows,
        "comparison": {
            "before_words": before_rows,
            "after_words": word_rows,
            "has_refinement": run.initial_result is not None and run.initial_result.words != run.result.words,
        },
        "ayahs": ayah_rows,
        "quality": {
            "coverage": run.quality.coverage,
            "zero_length_ratio": run.quality.zero_length_ratio,
            "average_word_score": run.quality.average_word_score,
            "median_word_score": run.quality.median_word_score,
            "low_score_ratio": run.quality.low_score_ratio,
            "gap_count": run.quality.gap_count,
            "uncovered_gap_ratio": run.quality.uncovered_gap_ratio,
            "warnings": run.quality.warnings,
        },
        "suspicious_words": [
            {
                "global_word_index": item.global_word_index,
                "reason": item.reason,
                "score": item.score,
                "confidence": score_to_confidence(item.score),
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "flags": item.flags,
            }
            for item in run.suspicious_words
        ],
        "gaps": [
            {
                "start_ms": gap.start_ms,
                "end_ms": gap.end_ms,
                "duration_ms": gap.duration_ms,
                "left_word_index": gap.left_word_index,
                "right_word_index": gap.right_word_index,
                "kind": gap.kind,
                "classification": gap.classification,
            }
            for gap in run.gaps
        ],
        "refinement": {
            "changed_word_count": run.refinement.changed_word_count if run.refinement else 0,
            "total_boundary_shift_ms": run.refinement.total_boundary_shift_ms if run.refinement else 0,
            "notes": run.refinement.notes if run.refinement else [],
            "region_logs": run.refinement.region_logs if run.refinement else [],
        },
        "decoder": {
            "mode": run.result.metadata.get("decoder_mode"),
            "bucket_ms": run.result.metadata.get("bucket_ms"),
            "max_repair_words": run.result.metadata.get("max_repair_words"),
            "phrase_trace": run.result.metadata.get("phrase_trace", []),
            "debug": None,
            "analysis_files": {},
        },
        "summaries": {
            "worst_words": _worst_words(run),
            "largest_gaps": _largest_gaps(run),
            "lowest_ayahs": _lowest_ayahs(run),
        },
        "ui": {
            "show_suspicious_only": show_suspicious_only,
        },
    }


def _write_review_ayah_analysis_files(run: AlignmentRun, output_dir: Path) -> dict[int, str]:
    decoder_debug = run.result.metadata.get("decoder_debug")
    if not isinstance(decoder_debug, dict):
        return {}
    state_rows = decoder_debug.get("state_rows")
    scoring_matrix = decoder_debug.get("scoring_matrix")
    dp_scores = decoder_debug.get("dp_scores")
    bucket_to_state = decoder_debug.get("bucket_to_state")
    bucket_to_word = decoder_debug.get("bucket_to_word")
    bucket_ms = decoder_debug.get("bucket_ms") or run.result.metadata.get("bucket_ms")
    if not (
        isinstance(state_rows, list)
        and isinstance(scoring_matrix, list)
        and isinstance(dp_scores, list)
        and isinstance(bucket_to_state, list)
        and isinstance(bucket_to_word, list)
        and bucket_ms
    ):
        return {}

    analysis_dir = output_dir / "ayah-analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[int, str] = {}

    for ayah in run.ayah_alignments:
        ayah_number = ayah.ayah_number
        if ayah_number == 0:
            continue
        ayah_word_indices = [
            index for index, token in enumerate(run.tokens)
            if token.ayah_number == ayah_number
        ]
        if not ayah_word_indices:
            continue
        selected_state_rows = [
            row for row in state_rows
            if row.get("global_word_index") in ayah_word_indices
        ]
        if not selected_state_rows:
            continue
        state_indices = [int(row["state_index"]) for row in selected_state_rows]
        bucket_start = max(0, min(len(bucket_to_state) - 1, int(ayah.start_ms // bucket_ms))) if bucket_to_state else 0
        bucket_end = max(bucket_start, min(len(bucket_to_state) - 1, int(max(ayah.start_ms, ayah.end_ms - 1) // bucket_ms))) if bucket_to_state else 0
        payload = {
            "ayah_number": ayah_number,
            "start_ms": ayah.start_ms,
            "end_ms": ayah.end_ms,
            "bucket_ms": bucket_ms,
            "bucket_start": bucket_start,
            "bucket_end": bucket_end,
            "word_start_index": ayah_word_indices[0],
            "word_end_index": ayah_word_indices[-1],
            "state_rows": selected_state_rows,
            "bucket_to_state": bucket_to_state[bucket_start : bucket_end + 1],
            "bucket_to_word": bucket_to_word[bucket_start : bucket_end + 1],
            "bucket_silence_scores": (decoder_debug.get("bucket_silence_scores") or [])[bucket_start : bucket_end + 1],
            "scoring_matrix": [
                scoring_matrix[state_index][bucket_start : bucket_end + 1]
                for state_index in state_indices
            ],
            "dp_scores": [
                dp_scores[state_index][bucket_start + 1 : bucket_end + 2]
                for state_index in state_indices
            ],
        }
        target = analysis_dir / f"ayah-{ayah_number:03d}.js"
        target.write_text(
            "window.__QURAN_ALIGNER_AYAH_ANALYSIS = window.__QURAN_ALIGNER_AYAH_ANALYSIS || {};\n"
            f"window.__QURAN_ALIGNER_AYAH_ANALYSIS[{ayah_number}] = "
            + json.dumps(payload, ensure_ascii=False)
            + ";\n",
            encoding="utf-8",
        )
        manifest[ayah_number] = os.path.relpath(target, output_dir)
    return manifest


def _stage_audio_for_review(audio_path: Path, output_dir: Path) -> Path:
    if not audio_path.exists():
        return audio_path
    staged_name = f"audio{audio_path.suffix.lower()}"
    staged_path = output_dir / staged_name
    if audio_path.resolve() != staged_path.resolve():
        shutil.copy2(audio_path, staged_path)
    return staged_path


def _emit_progress(progress_callback, stage: str, message: str, completed: int | None = None, total: int | None = None) -> None:
    if progress_callback is None:
        return
    progress_callback(ProgressEvent(stage=stage, message=message, completed=completed, total=total))


def _call_backend_align(backend: AlignmentBackend, audio_path: str, tokens, progress_callback=None):
    try:
        signature = inspect.signature(backend.align)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and "progress_callback" in signature.parameters:
        return backend.align(audio_path, tokens, progress_callback=progress_callback)
    return backend.align(audio_path, tokens)


def _prepare_tokens_for_backend(backend, tokens, progress_callback=None):
    if not hasattr(backend, "prepare_tokens"):
        return tokens
    if progress_callback is not None:
        progress_callback(ProgressEvent(stage="setup", message="Preparing transcript tokens for the selected model"))
    try:
        signature = inspect.signature(backend.prepare_tokens)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and "progress_callback" in signature.parameters:
        return backend.prepare_tokens(tokens, progress_callback=progress_callback)
    return backend.prepare_tokens(tokens)


def _call_backend_local_realign(
    backend,
    audio_path: str,
    tokens,
    start_ms: int,
    end_ms: int,
    *,
    progress_callback=None,
    collect_decoder_debug: bool = False,
):
    if not hasattr(backend, "local_realign"):
        raise RuntimeError("Selected backend does not support local region inspection.")
    try:
        signature = inspect.signature(backend.local_realign)
    except (TypeError, ValueError):
        signature = None
    kwargs = {}
    if signature is not None:
        if "progress_callback" in signature.parameters:
            kwargs["progress_callback"] = progress_callback
        if "collect_decoder_debug" in signature.parameters:
            kwargs["collect_decoder_debug"] = collect_decoder_debug
    return backend.local_realign(audio_path, tokens, start_ms, end_ms, **kwargs)


def inspect_alignment_region(
    *,
    run: AlignmentRun,
    audio_path: str,
    backend,
    output_dir: Path,
    start_ms: int,
    end_ms: int,
    ayah_number: int | None = None,
    word_start: int | None = None,
    word_end: int | None = None,
    progress_callback=None,
) -> dict[str, object]:
    if end_ms <= start_ms:
        raise ValueError("inspect region end must be greater than start")
    resolved_output_dir = output_dir.resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    review_audio_file = _stage_audio_for_review(Path(audio_path).resolve(), resolved_output_dir)
    tokens = run.tokens
    if ayah_number is not None:
        tokens = [token for token in tokens if token.ayah_number == ayah_number]
    if word_start is not None:
        tokens = [token for token in tokens if token.word_index_in_ayah >= word_start]
    if word_end is not None:
        tokens = [token for token in tokens if token.word_index_in_ayah <= word_end]
    if not tokens:
        raise ValueError("No tokens matched the requested inspection region.")

    _emit_progress(progress_callback, "inspect", f"Running local region decode for {len(tokens)} token(s)")
    result = _call_backend_local_realign(
        backend,
        audio_path,
        tokens,
        start_ms,
        end_ms,
        progress_callback=progress_callback,
        collect_decoder_debug=True,
    )
    result = populate_path_outputs(result=result, tokens=tokens)
    decoder_debug = result.metadata.get("decoder_debug")
    if not decoder_debug:
        raise RuntimeError("Decoder debug payload was not produced for region inspection.")

    payload = {
        "region": {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "ayah_number": ayah_number,
            "word_start": word_start,
            "word_end": word_end,
        },
        "audio": {
            "path": str(review_audio_file),
            "relative_path": os.path.relpath(review_audio_file, resolved_output_dir),
            "duration_ms": infer_total_audio_ms(str(audio_path), result),
            "duration_label": _format_ms(infer_total_audio_ms(str(audio_path), result)),
        },
        "tokens": [
            {
                "index": index,
                "ayah_number": token.ayah_number,
                "word_index_in_ayah": token.word_index_in_ayah,
                "original_word": token.original_word,
                "normalized_word": token.normalized_word,
            }
            for index, token in enumerate(tokens)
        ],
        "decoder": {
            **decoder_debug,
            "phrase_trace": result.metadata.get("phrase_trace", []),
        },
        "metadata": {
            "alignment_model": result.metadata.get("alignment_model", getattr(backend, "alignment_model", None)),
            "normalization_profile": run.result.metadata.get("normalization_profile"),
        },
        "runs": [
            {
                "run_index": run_segment.run_index,
                "global_word_index": run_segment.global_word_index,
                "word": run_segment.word,
                "start_ms": run_segment.start_ms,
                "end_ms": run_segment.end_ms,
                "score": run_segment.score,
                "frame_count": run_segment.frame_count,
            }
            for run_segment in result.word_runs
        ],
    }
    write_debug_json(resolved_output_dir / "region-inspect.debug.json", payload)
    write_region_debug_html(resolved_output_dir / "region-inspect.html", payload)
    write_region_debug_data_js(resolved_output_dir / "region-inspect.data.js", payload)
    return payload


def inspect_alignment_region_only(
    *,
    audio_path: str,
    surah_number: int,
    backend,
    output_dir: Path,
    start_ms: int,
    end_ms: int,
    normalization_profile: str | None = None,
    alignment_model: str | None = None,
    prefer_remote_text: bool = True,
    ayah_number: int | None = None,
    word_start: int | None = None,
    word_end: int | None = None,
    progress_callback=None,
) -> dict[str, object]:
    resolved_output_dir = output_dir.resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    review_audio_file = _stage_audio_for_review(Path(audio_path).resolve(), resolved_output_dir)
    _emit_progress(progress_callback, "inspect", f"Loading Surah {surah_number} text for region-only decode")
    resolved_profile = choose_normalization_profile(
        normalization_profile,
        alignment_model=alignment_model or getattr(backend, "alignment_model", DEFAULT_CTC_ALIGNMENT_MODEL),
    )
    normalization_config = resolve_normalization_config(resolved_profile)
    surah = fetch_surah_text(surah_number, prefer_remote=prefer_remote_text)
    tokens = flatten_surah_to_tokens(surah, normalization_config)
    tokens = _prepare_tokens_for_backend(backend, tokens, progress_callback=progress_callback)
    if ayah_number is not None:
        tokens = [token for token in tokens if token.ayah_number == ayah_number]
    if word_start is not None:
        tokens = [token for token in tokens if token.word_index_in_ayah >= word_start]
    if word_end is not None:
        tokens = [token for token in tokens if token.word_index_in_ayah <= word_end]
    if not tokens:
        raise ValueError("No tokens matched the requested inspection region.")

    _emit_progress(progress_callback, "inspect", f"Running local region decode for {len(tokens)} token(s)")
    result = _call_backend_local_realign(
        backend,
        audio_path,
        tokens,
        start_ms,
        end_ms,
        progress_callback=progress_callback,
        collect_decoder_debug=True,
    )
    result = populate_path_outputs(result=result, tokens=tokens)
    decoder_debug = result.metadata.get("decoder_debug")
    if not decoder_debug:
        raise RuntimeError("Decoder debug payload was not produced for region inspection.")

    payload = {
        "region": {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "ayah_number": ayah_number,
            "word_start": word_start,
            "word_end": word_end,
            "surah_number": surah_number,
        },
        "audio": {
            "path": str(review_audio_file),
            "relative_path": os.path.relpath(review_audio_file, resolved_output_dir),
            "duration_ms": infer_total_audio_ms(str(audio_path), result),
            "duration_label": _format_ms(infer_total_audio_ms(str(audio_path), result)),
        },
        "tokens": [
            {
                "index": index,
                "ayah_number": token.ayah_number,
                "word_index_in_ayah": token.word_index_in_ayah,
                "original_word": token.original_word,
                "normalized_word": token.normalized_word,
            }
            for index, token in enumerate(tokens)
        ],
        "decoder": {
            **decoder_debug,
            "phrase_trace": result.metadata.get("phrase_trace", []),
        },
        "metadata": {
            "alignment_model": result.metadata.get("alignment_model", getattr(backend, "alignment_model", None)),
            "normalization_profile": normalization_config.profile_name,
        },
        "runs": [
            {
                "run_index": run_segment.run_index,
                "global_word_index": run_segment.global_word_index,
                "word": run_segment.word,
                "start_ms": run_segment.start_ms,
                "end_ms": run_segment.end_ms,
                "score": run_segment.score,
                "frame_count": run_segment.frame_count,
            }
            for run_segment in result.word_runs
        ],
    }
    write_debug_json(resolved_output_dir / "region-inspect.debug.json", payload)
    write_region_debug_html(resolved_output_dir / "region-inspect.html", payload)
    write_region_debug_data_js(resolved_output_dir / "region-inspect.data.js", payload)
    _emit_progress(progress_callback, "inspect", "Region-only inspection finished", completed=1, total=1)
    return payload


def _select_surah_scope(surah: SurahText, mode: str, ayah_number: int | None) -> SurahText:
    if mode == "full" or mode == "test" or mode == "ayah":
        return surah
    if mode not in {"full", "test", "ayah"}:
        raise ValueError("mode must be one of: full, ayah, test")
    return surah


def _filter_run_to_ayah(run: AlignmentRun, ayah_number: int) -> AlignmentRun:
    matching_ayahs = [ayah for ayah in run.surah.ayahs if ayah.ayah_number == ayah_number]
    if not matching_ayahs:
        raise ValueError(f"Surah {run.surah.surah_number} does not contain ayah {ayah_number}")

    filtered_tokens = [token for token in run.tokens if token.ayah_number == ayah_number]
    filtered_words = [
        replace(word)
        for word in run.result.words
        if 0 <= word.global_word_index < len(run.tokens) and run.tokens[word.global_word_index].ayah_number == ayah_number
    ]
    index_map = {
        old_index: new_index
        for new_index, old_index in enumerate(
            [index for index, token in enumerate(run.tokens) if token.ayah_number == ayah_number]
        )
    }
    for word in filtered_words:
        word.global_word_index = index_map[word.global_word_index]

    filtered_frames = [
        replace(frame, global_word_index=index_map[frame.global_word_index])
        for frame in run.result.frame_alignments
        if frame.global_word_index in index_map
    ]
    filtered_runs = [
        replace(run_segment, global_word_index=index_map[run_segment.global_word_index])
        for run_segment in run.result.word_runs
        if run_segment.global_word_index in index_map
    ]
    filtered_occurrences = [
        replace(occurrence, global_word_index=index_map[occurrence.global_word_index])
        for occurrence in run.result.word_occurrences
        if occurrence.global_word_index in index_map
    ]
    filtered_result = replace(
        run.result,
        words=filtered_words,
        frame_alignments=filtered_frames,
        word_runs=filtered_runs,
        word_occurrences=filtered_occurrences,
    )
    filtered_initial_result = None
    if run.initial_result is not None:
        filtered_initial_words = [
            replace(word)
            for word in run.initial_result.words
            if 0 <= word.global_word_index < len(run.tokens) and run.tokens[word.global_word_index].ayah_number == ayah_number
        ]
        for word in filtered_initial_words:
            word.global_word_index = index_map[word.global_word_index]
        filtered_initial_frames = [
            replace(frame, global_word_index=index_map[frame.global_word_index])
            for frame in run.initial_result.frame_alignments
            if frame.global_word_index in index_map
        ]
        filtered_initial_runs = [
            replace(run_segment, global_word_index=index_map[run_segment.global_word_index])
            for run_segment in run.initial_result.word_runs
            if run_segment.global_word_index in index_map
        ]
        filtered_initial_occurrences = [
            replace(occurrence, global_word_index=index_map[occurrence.global_word_index])
            for occurrence in run.initial_result.word_occurrences
            if occurrence.global_word_index in index_map
        ]
        filtered_initial_result = replace(
            run.initial_result,
            words=filtered_initial_words,
            frame_alignments=filtered_initial_frames,
            word_runs=filtered_initial_runs,
            word_occurrences=filtered_initial_occurrences,
        )
    filtered_ayah_alignments = [ayah for ayah in run.ayah_alignments if ayah.ayah_number == ayah_number]
    filtered_surah = SurahText(surah_number=run.surah.surah_number, ayahs=matching_ayahs)
    filtered_suspicious = [
        replace(item, global_word_index=index_map[item.global_word_index])
        for item in run.suspicious_words
        if item.global_word_index in index_map
    ]
    filtered_gaps = [
        replace(
            gap,
            left_word_index=index_map.get(gap.left_word_index) if gap.left_word_index is not None else None,
            right_word_index=index_map.get(gap.right_word_index) if gap.right_word_index is not None else None,
        )
        for gap in run.gaps
        if (gap.left_word_index in index_map or gap.left_word_index is None)
        and (gap.right_word_index in index_map or gap.right_word_index is None)
    ]
    filtered_quality = evaluate_alignment_quality(
        filtered_tokens,
        filtered_result,
        filtered_ayah_alignments,
        min_word_score=float(run.result.metadata.get("min_word_score", 0.45)),
        gaps=filtered_gaps,
        suspicious_word_count=len(filtered_suspicious),
        total_audio_ms=max((word.end_ms for word in filtered_words), default=0),
    )
    filtered_refinement = None
    if run.refinement is not None:
        filtered_refinement = RefinementReport(
            suspicious_words=filtered_suspicious,
            gaps=filtered_gaps,
            changed_word_count=0,
            total_boundary_shift_ms=0,
            notes=["Filtered from a full-surah refinement pass; aggregate shift metrics are not recomputed for ayah view."],
            region_logs=run.refinement.region_logs,
        )
    filtered_result = populate_path_outputs(result=filtered_result, tokens=filtered_tokens)
    if filtered_initial_result is not None:
        filtered_initial_result = populate_path_outputs(result=filtered_initial_result, tokens=filtered_tokens)
    return AlignmentRun(
        surah=filtered_surah,
        tokens=filtered_tokens,
        initial_result=filtered_initial_result,
        result=filtered_result,
        ayah_alignments=filtered_ayah_alignments,
        quality=filtered_quality,
        suspicious_words=filtered_suspicious,
        gaps=filtered_gaps,
        refinement=filtered_refinement,
    )


def _enrich_result_metadata(
    result: AlignmentResult,
    *,
    audio_path: str,
    normalization_config: NormalizationConfig,
    min_word_score: float,
    suspicious_word_count: int,
    gap_count: int,
    uncovered_gap_duration_total: int,
) -> AlignmentResult:
    scores = [score_to_confidence(word.score) for word in result.words]
    sorted_scores = sorted(scores)
    median_score = sorted_scores[len(sorted_scores) // 2] if sorted_scores else 0.0
    metadata = dict(result.metadata)
    metadata.update(
        {
            "normalization_profile": normalization_config.profile_name,
            "normalization_settings": {
                "remove_diacritics": normalization_config.remove_diacritics,
                "remove_decorative_marks": normalization_config.remove_decorative_marks,
                "remove_punctuation": normalization_config.remove_punctuation,
                "normalize_alif_variants": normalization_config.normalize_alif_variants,
                "normalize_alif_maqsura": normalization_config.normalize_alif_maqsura,
                "normalize_ta_marbuta": normalization_config.normalize_ta_marbuta,
                "normalize_hamza_on_waw_ya": normalization_config.normalize_hamza_on_waw_ya,
            },
            "min_word_score": min_word_score,
            "total_audio_ms": infer_total_audio_ms(audio_path, result),
            "average_word_score": sum(scores) / max(1, len(scores)),
            "minimum_word_score": min(scores) if scores else 0.0,
            "median_word_score": median_score,
            "suspicious_word_count": suspicious_word_count,
            "uncovered_gap_count": gap_count,
            "uncovered_gap_duration_total": uncovered_gap_duration_total,
        }
    )
    return replace(result, metadata=metadata)


def run_alignment(
    audio_path: str,
    surah_number: int,
    *,
    mode: str = "full",
    ayah_number: int | None = None,
    include_bismillah_mode: str = "auto",
    backend_name: str = "auto",
    alignment_model: str | None = None,
    normalization_profile: str | None = None,
    min_word_score: float = 0.45,
    local_window_ms: int = 250,
    local_phrase_words: int = 3,
    max_gap_to_absorb_ms: int = 120,
    disable_refinement: bool = False,
    show_suspicious_only: bool = False,
    output_dir: str | None = None,
    output_path: str | None = None,
    debug_path: str | None = None,
    review_path: str | None = None,
    backend: AlignmentBackend | None = None,
    prefer_remote_text: bool = True,
    state_dp_engine: str = "native",
    state_dp_mode: str = "jump",
    progress_callback=None,
) -> AlignmentRun:
    _emit_progress(progress_callback, "setup", "Resolving normalization profile")
    resolved_alignment_model = alignment_model or getattr(backend, "alignment_model", DEFAULT_CTC_ALIGNMENT_MODEL)
    if backend is None and backend_name == "auto":
        backend_name = "baseline" if mode == "test" else "ctc"
    resolved_profile = choose_normalization_profile(
        normalization_profile,
        alignment_model=resolved_alignment_model,
    )
    normalization_config = resolve_normalization_config(resolved_profile)
    _emit_progress(progress_callback, "setup", f"Loading Surah {surah_number} text")
    surah = fetch_surah_text(surah_number, prefer_remote=prefer_remote_text)
    surah = _select_surah_scope(surah, mode, ayah_number)
    candidates = prepare_target_text(surah, include_bismillah_mode, normalization_config)
    alignment_backend = backend or make_backend(
        backend_name,
        state_dp_engine=state_dp_engine,
        state_dp_mode=state_dp_mode,
        alignment_model=resolved_alignment_model if backend_name == "ctc" else None,
    )
    _emit_progress(progress_callback, "setup", f"Prepared {len(candidates)} transcript candidate(s)")

    best_run: AlignmentRun | None = None
    candidate_elapsed_seconds: list[float] = []
    for candidate_index, candidate in enumerate(candidates, start=1):
        candidate_started_at = time.monotonic()
        _emit_progress(
            progress_callback,
            "candidate",
            f"Aligning candidate {candidate_index} of {len(candidates)}",
            completed=candidate_index,
            total=len(candidates),
        )
        tokens = flatten_surah_to_tokens(candidate, normalization_config)
        tokens = _prepare_tokens_for_backend(alignment_backend, tokens, progress_callback=progress_callback)
        _emit_progress(
            progress_callback,
            "candidate",
            f"Flattened {len(tokens)} token(s) for candidate {candidate_index}/{len(candidates)}",
        )
        result = populate_path_outputs(
            result=_call_backend_align(alignment_backend, audio_path, tokens, progress_callback=progress_callback),
            tokens=tokens,
        )
        initial_result = replace(result, words=[replace(word) for word in result.words])
        refinement_report = None
        suspicious_words = []
        gaps = []
        if not disable_refinement:
            _emit_progress(progress_callback, "refine", f"Refining candidate {candidate_index}")
            result, _suspicious_regions, notes, suspicious_words, gaps = refine_alignment_with_emissions(
                tokens,
                result,
                backend=alignment_backend,
                audio_path=audio_path,
                min_word_confidence=min_word_score,
                window_padding_ms=local_window_ms,
                min_score_improvement=0.05,
                local_phrase_words=local_phrase_words,
            )
            changed_count = sum(
                1
                for before, after in zip(initial_result.words, result.words)
                if before.start_ms != after.start_ms or before.end_ms != after.end_ms
            )
            total_shift = sum(
                abs(before.start_ms - after.start_ms) + abs(before.end_ms - after.end_ms)
                for before, after in zip(initial_result.words, result.words)
            )
            refinement_report = RefinementReport(
                suspicious_words=suspicious_words,
                gaps=gaps,
                changed_word_count=changed_count,
                total_boundary_shift_ms=total_shift,
                notes=notes,
                region_logs=list(result.metadata.get("refinement_region_logs", [])),
            )
        _emit_progress(progress_callback, "score", f"Evaluating candidate {candidate_index}/{len(candidates)}")
        result = populate_path_outputs(result=result, tokens=tokens)
        result = _enrich_result_metadata(
            result,
            audio_path=audio_path,
            normalization_config=normalization_config,
            min_word_score=min_word_score,
            suspicious_word_count=len(suspicious_words),
            gap_count=len(gaps),
            uncovered_gap_duration_total=sum(gap.duration_ms for gap in gaps),
        )
        ayah_alignments = build_ayah_alignments(tokens, result)
        quality = evaluate_alignment_quality(
            tokens,
            result,
            ayah_alignments,
            min_word_score=min_word_score,
            gaps=gaps,
            suspicious_word_count=len(suspicious_words),
            total_audio_ms=int(result.metadata.get("total_audio_ms", 0)),
        )
        run = AlignmentRun(
            surah=candidate,
            tokens=tokens,
            initial_result=initial_result,
            result=result,
            ayah_alignments=ayah_alignments,
            quality=quality,
            suspicious_words=suspicious_words,
            gaps=gaps,
            refinement=refinement_report,
        )
        if best_run is None or run.result.total_score > best_run.result.total_score:
            best_run = run
        elapsed_seconds = time.monotonic() - candidate_started_at
        candidate_elapsed_seconds.append(elapsed_seconds)
        remaining_candidates = len(candidates) - candidate_index
        average_seconds = sum(candidate_elapsed_seconds) / len(candidate_elapsed_seconds)
        estimate_seconds = average_seconds * remaining_candidates
        summary = (
            f"Completed candidate {candidate_index}/{len(candidates)} "
            f"in {_format_duration_seconds(elapsed_seconds)}"
        )
        if remaining_candidates > 0:
            summary += f"; estimated remaining {_format_duration_seconds(estimate_seconds)}"
        _emit_progress(
            progress_callback,
            "candidate",
            summary,
            completed=candidate_index,
            total=len(candidates),
        )

    if best_run is None:
        raise RuntimeError("No alignment candidates were produced.")
    _emit_progress(progress_callback, "finalize", "Selecting best candidate")
    if mode == "ayah":
        if ayah_number is None:
            raise ValueError("--ayah-number is required when --mode ayah is used")
        best_run = _filter_run_to_ayah(best_run, ayah_number)

    audio_file = Path(audio_path).resolve()
    resolved_output_dir = Path(output_dir).resolve() if output_dir else Path.cwd()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    resolved_output = Path(output_path).resolve() if output_path else resolved_output_dir / "alignment.txt"
    _emit_progress(progress_callback, "write", "Writing alignment text")
    write_alignment_txt(resolved_output, best_run.ayah_alignments)

    resolved_debug = Path(debug_path).resolve() if debug_path else resolved_output_dir / "alignment.debug.json"
    _emit_progress(progress_callback, "write", "Writing debug JSON")
    debug_started_at = time.monotonic()
    serialize_run(best_run, resolved_debug)
    _emit_progress(
        progress_callback,
        "write",
        f"Wrote debug JSON in {_format_duration_seconds(time.monotonic() - debug_started_at)}",
    )
    if best_run.refinement is not None:
        _emit_progress(progress_callback, "write", "Writing refinement debug JSON")
        write_debug_json(
            resolved_output_dir / "refinement.debug.json",
            {
                "surah_number": best_run.surah.surah_number,
                "backend": best_run.result.backend,
                "normalization_profile": best_run.result.metadata.get("normalization_profile"),
                "local_phrase_words": best_run.result.metadata.get("local_phrase_words"),
                "attempted_refinement_windows": best_run.result.metadata.get("attempted_refinement_windows"),
                "accepted_refinement_windows": best_run.result.metadata.get("accepted_refinement_windows"),
                "selected_refinement_windows": best_run.result.metadata.get("selected_refinement_windows"),
                "notes": best_run.refinement.notes,
                "changed_word_count": best_run.refinement.changed_word_count,
                "total_boundary_shift_ms": best_run.refinement.total_boundary_shift_ms,
                "suspicious_words": best_run.suspicious_words,
                "gaps": best_run.gaps,
                "region_logs": best_run.refinement.region_logs,
            },
        )
    resolved_review = Path(review_path).resolve() if review_path else resolved_output_dir / "index.html"
    _emit_progress(progress_callback, "write", "Writing review HTML")
    review_audio_file = _stage_audio_for_review(audio_file, resolved_output_dir)
    review_payload = _build_review_payload(
        best_run,
        review_audio_file,
        resolved_output_dir,
        mode,
        show_suspicious_only=show_suspicious_only,
    )
    review_payload["decoder"]["analysis_files"] = _write_review_ayah_analysis_files(best_run, resolved_output_dir)
    write_review_html(
        resolved_review,
        review_payload,
    )
    _emit_progress(progress_callback, "done", "Alignment run finished", completed=1, total=1)
    return best_run
