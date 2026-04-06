from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from .models import AlignmentQuality, AlignmentRun, AyahAlignment


def write_alignment_txt(path: str | Path, ayahs: list[AyahAlignment]) -> None:
    lines = [f"{ayah.ayah_number}\t{ayah.start_ms}\t{ayah.end_ms}" for ayah in ayahs]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _strip_heavy_decoder_debug(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned = {key: _strip_heavy_decoder_debug(item) for key, item in payload.items()}
        decoder_debug = cleaned.get("decoder_debug")
        if isinstance(decoder_debug, dict):
            slim_debug = {
                key: value
                for key, value in decoder_debug.items()
                if key not in {"scoring_matrix", "dp_scores", "backpointers"}
            }
            if "scoring_matrix" in decoder_debug:
                row_count = len(decoder_debug.get("scoring_matrix", []))
                column_count = len(decoder_debug["scoring_matrix"][0]) if row_count else 0
                slim_debug["scoring_matrix_shape"] = [row_count, column_count]
            if "dp_scores" in decoder_debug:
                row_count = len(decoder_debug.get("dp_scores", []))
                column_count = len(decoder_debug["dp_scores"][0]) if row_count else 0
                slim_debug["dp_scores_shape"] = [row_count, column_count]
            if "backpointers" in decoder_debug:
                row_count = len(decoder_debug.get("backpointers", []))
                column_count = len(decoder_debug["backpointers"][0]) if row_count else 0
                slim_debug["backpointers_shape"] = [row_count, column_count]
            cleaned["decoder_debug"] = slim_debug
        return cleaned
    if isinstance(payload, list):
        return [_strip_heavy_decoder_debug(item) for item in payload]
    return payload


def write_debug_json(path: str | Path, data: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(_to_jsonable(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def serialize_run(run: AlignmentRun, output_path: str | Path, quality: AlignmentQuality | None = None) -> None:
    payload = {
        "output_path": str(output_path),
        "surah_number": run.surah.surah_number,
        "tokens": run.tokens,
        "initial_result": run.initial_result,
        "result": run.result,
        "ayah_alignments": run.ayah_alignments,
        "quality": quality or run.quality,
        "suspicious_words": run.suspicious_words,
        "gaps": run.gaps,
        "refinement": run.refinement,
        "score_thresholds": {
            "min_word_score": run.result.metadata.get("min_word_score"),
        },
        "alignment_model": run.result.metadata.get("alignment_model"),
        "normalization_profile": run.result.metadata.get("normalization_profile"),
        "normalization_settings": run.result.metadata.get("normalization_settings"),
    }
    jsonable_payload = _to_jsonable(payload)
    trimmed_payload = _strip_heavy_decoder_debug(jsonable_payload)
    Path(output_path).write_text(json.dumps(trimmed_payload, ensure_ascii=False) + "\n", encoding="utf-8")
