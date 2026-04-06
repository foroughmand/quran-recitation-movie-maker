from __future__ import annotations

from dataclasses import replace
import os
from math import ceil
from pathlib import Path
import sys
import time

from ..dp_decoder import DecoderConfig, StateDecodeResult, decode_state_score_matrix
from ..models import AlignmentResult, AlignmentRunSegment, FrameAlignment, TokenRef, WordAlignment
from ..normalizer import (
    DEFAULT_CTC_ALIGNMENT_MODEL,
    MODERATE_NORMALIZATION,
    filter_text_for_tokenizer,
    flatten_tokens_to_align_units,
    normalize_quranic_text,
)
from ..path_alignment import populate_path_outputs
from ..progress import ProgressEvent


class CTCForcedAlignerBackend:
    name = "ctc"

    def __init__(
        self,
        *,
        language: str = "ara",
        alignment_model: str = DEFAULT_CTC_ALIGNMENT_MODEL,
        compute_dtype: str = "float32",
        batch_size: int = 4,
        state_dp_engine: str = "native",
        state_dp_mode: str = "jump",
        decoder_config: DecoderConfig | None = None,
    ) -> None:
        self.language = language
        self.alignment_model = alignment_model
        self.compute_dtype = compute_dtype
        self.batch_size = batch_size
        self.decoder_config = decoder_config or DecoderConfig(state_dp_engine=state_dp_engine, state_dp_mode=state_dp_mode)
        self.decoder_config.state_dp_engine = state_dp_engine
        self.decoder_config.state_dp_mode = state_dp_mode
        self._model = None
        self._tokenizer = None
        self._device = None
        self._dtype = None
        self._emissions_cache: dict[str, tuple[object, float, int]] = {}

    @staticmethod
    def _format_duration_seconds(seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _load_dependencies(self):
        try:
            import torch
            from ctc_forced_aligner import (
                generate_emissions,
                get_alignments,
                get_spans,
                load_alignment_model,
                load_audio,
                postprocess_results,
                preprocess_text,
            )
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Real CTC alignment requires the ctc-forced-aligner package and its dependencies in dev1."
            ) from exc
        return torch, generate_emissions, get_alignments, get_spans, load_alignment_model, load_audio, postprocess_results, preprocess_text

    def _ensure_model(self):
        (
            torch,
            _generate_emissions,
            _get_alignments,
            _get_spans,
            load_alignment_model,
            _load_audio,
            _postprocess_results,
            _preprocess_text,
        ) = self._load_dependencies()

        env_bin = str(Path(sys.executable).resolve().parent)
        current_path = os.environ.get("PATH", "")
        if env_bin not in current_path.split(os.pathsep):
            os.environ["PATH"] = env_bin + os.pathsep + current_path

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" and self.compute_dtype == "float16" else torch.float32
        if self._model is None or self._tokenizer is None or self._device != device or self._dtype != dtype:
            self._model, self._tokenizer = load_alignment_model(
                device=device,
                dtype=dtype,
                model_path=self.alignment_model,
            )
            self._device = device
            self._dtype = dtype
        return torch

    def prepare_tokens(self, tokens: list[TokenRef]) -> list[TokenRef]:
        self._ensure_model()
        tokenizer = self._tokenizer
        if tokenizer is None:
            return list(tokens)
        prepared_tokens: list[TokenRef] = []
        for token in tokens:
            filtered_chars: list[str] = []
            for char in token.normalized_word:
                if char.isspace():
                    filtered_chars.append(char)
                    continue
                if self._tokenizer_supports_text(tokenizer, char):
                    filtered_chars.append(char)
                    continue
                simplified = normalize_quranic_text(char, MODERATE_NORMALIZATION)
                if simplified and all(self._tokenizer_supports_text(tokenizer, item) for item in simplified):
                    filtered_chars.append(simplified)
            filtered_word = filter_text_for_tokenizer(
                "".join(filtered_chars),
                is_supported=lambda char: self._tokenizer_supports_text(tokenizer, char),
            )
            if not filtered_word:
                continue
            prepared_tokens.append(replace(token, normalized_word=filtered_word))
        return prepared_tokens

    def align(self, audio_path: str, tokens: list[TokenRef], progress_callback=None) -> AlignmentResult:
        align_started_at = time.monotonic()
        (
            torch,
            _generate_emissions,
            get_alignments,
            get_spans,
            _load_alignment_model,
            _load_audio,
            postprocess_results,
            preprocess_text,
        ) = self._load_dependencies()
        if progress_callback is not None:
            progress_callback(ProgressEvent(stage="align", message="Loading CTC alignment model"))
        model_started_at = time.monotonic()
        self._ensure_model()
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message=f"Loaded CTC model in {self._format_duration_seconds(time.monotonic() - model_started_at)}",
                )
            )

        alignment_model = self._model
        alignment_tokenizer = self._tokenizer
        if progress_callback is not None:
            progress_callback(ProgressEvent(stage="align", message="Computing model emissions"))
        emissions_started_at = time.monotonic()
        emissions, stride, total_audio_ms = self.get_emissions(audio_path)
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message=f"Computed model emissions in {self._format_duration_seconds(time.monotonic() - emissions_started_at)}",
                )
            )
        if progress_callback is not None:
            progress_callback(ProgressEvent(stage="align", message="Extracting monotone char spans"))
        decode_started_at = time.monotonic()
        result = self._align_tokens_from_emissions(
            tokens=tokens,
            emissions=emissions,
            stride=stride,
            tokenizer=alignment_tokenizer,
            get_alignments=get_alignments,
            get_spans=get_spans,
            postprocess_results=postprocess_results,
            preprocess_text=preprocess_text,
            start_ms_offset=0,
            progress_callback=progress_callback,
        )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message=f"Decoded raw state path in {self._format_duration_seconds(time.monotonic() - decode_started_at)}",
                )
            )

        metadata = dict(result.metadata)
        metadata.update(
            {
                "device": self._device,
                "alignment_model": self.alignment_model,
                "language": self.language,
                "compute_dtype": self.compute_dtype,
                "batch_size": self.batch_size,
                "stride": stride,
                "total_audio_ms": total_audio_ms,
                "transcript_unit_type": "char",
                "emissions_cache_key": self._build_emissions_cache_key(audio_path),
            }
        )
        if progress_callback is not None:
            progress_callback(ProgressEvent(stage="align", message="Finalizing DP-backed path outputs"))
        finalize_started_at = time.monotonic()
        finalized = populate_path_outputs(
            result=AlignmentResult(
                words=result.words,
                total_score=result.total_score,
                backend=self.name,
                frame_alignments=result.frame_alignments,
                word_runs=result.word_runs,
                word_occurrences=result.word_occurrences,
                metadata=metadata,
            ),
            tokens=tokens,
        )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message=(
                        f"Finalized DP-backed path outputs in "
                        f"{self._format_duration_seconds(time.monotonic() - finalize_started_at)} "
                        f"(total align {self._format_duration_seconds(time.monotonic() - align_started_at)})"
                    ),
                )
            )
        return finalized

    def get_emissions(self, audio_path: str) -> tuple[object, float, int]:
        torch, generate_emissions, _get_alignments, _get_spans, _load_alignment_model, load_audio, _postprocess_results, _preprocess_text = self._load_dependencies()
        self._ensure_model()

        device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = self._dtype or (torch.float16 if device == "cuda" and self.compute_dtype == "float16" else torch.float32)
        cache_key = self._build_emissions_cache_key(audio_path)
        cached = self._emissions_cache.get(cache_key)
        if cached is None:
            audio_waveform = load_audio(audio_path, dtype, device)
            emissions, stride = generate_emissions(
                self._model,
                audio_waveform,
                batch_size=self.batch_size,
            )
            total_audio_ms = int(round(audio_waveform.shape[-1] / 16000 * 1000))
            self._emissions_cache[cache_key] = (emissions, stride, total_audio_ms)
            return emissions, stride, total_audio_ms
        return cached

    def _build_emissions_cache_key(self, audio_path: str) -> str:
        return f"{Path(audio_path).resolve()}::{self.alignment_model}"

    def local_realign(
        self,
        audio_path: str,
        tokens: list[TokenRef],
        start_ms: int,
        end_ms: int,
        *,
        progress_callback=None,
        collect_decoder_debug: bool = False,
    ) -> AlignmentResult:
        from ctc_forced_aligner import get_alignments, get_spans, postprocess_results, preprocess_text

        emissions, stride, _ = self.get_emissions(audio_path)
        start_frame = max(0, int(start_ms / stride))
        end_frame = min(emissions.shape[0], max(start_frame + 1, ceil(end_ms / stride)))
        local_emissions = emissions[start_frame:end_frame]
        return self._align_tokens_from_emissions(
            tokens=tokens,
            emissions=local_emissions,
            stride=stride,
            tokenizer=self._tokenizer,
            get_alignments=get_alignments,
            get_spans=get_spans,
            postprocess_results=postprocess_results,
            preprocess_text=preprocess_text,
            start_ms_offset=int(start_frame * stride),
            progress_callback=progress_callback,
            collect_decoder_debug=collect_decoder_debug,
        )

    def _align_tokens_from_emissions(
        self,
        *,
        tokens: list[TokenRef],
        emissions,
        stride: float,
        tokenizer,
        get_alignments,
        get_spans,
        postprocess_results,
        preprocess_text,
        start_ms_offset: int,
        progress_callback=None,
        collect_decoder_debug: bool = False,
    ) -> AlignmentResult:
        if not tokens:
            return AlignmentResult(words=[], total_score=0.0, backend=self.name, metadata={})

        text = " ".join(token.normalized_word for token in tokens if token.normalized_word.strip())
        units = flatten_tokens_to_align_units(tokens, mode="grapheme")
        raw_symbol_count = sum(len([char for char in unit.text if char.strip()]) for unit in units)
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message=f"Preparing {len(units)} grapheme units",
                )
            )
        tokens_starred, text_starred = preprocess_text(
            text,
            romanize=False,
            language=self.language,
            split_size="char",
        )
        segments, scores, blank_token = get_alignments(
            emissions,
            tokens_starred,
            tokenizer,
        )
        spans = get_spans(tokens_starred, segments, blank_token)
        segment_rows = postprocess_results(text_starred, spans, stride, scores)
        char_rows = [row for row in segment_rows if str(row.get("text", "")).strip()]
        if len(char_rows) != raw_symbol_count:
            raise RuntimeError(f"Expected {raw_symbol_count} tokenizer symbol segments, got {len(char_rows)}.")
        total_window_ms = int(round(emissions.shape[0] * stride))
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message="Building raw grapheme-state score matrix from emissions",
                )
            )
        score_matrix_started_at = time.monotonic()
        scoring_matrix = self._build_raw_state_score_matrix(
            emissions=emissions,
            stride=stride,
            tokenizer=tokenizer,
            tokens_starred=tokens_starred,
            units=units,
            total_window_ms=total_window_ms,
            progress_callback=progress_callback,
        )
        bucket_silence_scores = self._build_bucket_silence_scores(
            emissions=emissions,
            stride=stride,
            tokenizer=tokenizer,
            blank_token=blank_token,
            total_window_ms=total_window_ms,
        )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message=(
                        f"Built raw grapheme-state score matrix in "
                        f"{self._format_duration_seconds(time.monotonic() - score_matrix_started_at)}"
                    ),
                )
            )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message="Running raw state DP decoder",
                )
            )
        # Backtracking is still part of the DP, but by default we only permit the
        # backward-jump branch to leave from a word-end state and land on a
        # word-start state.
        is_word_start_state = [
            unit_index == 0 or units[unit_index - 1].global_word_index != unit.global_word_index
            for unit_index, unit in enumerate(units)
        ]
        is_word_end_state = [
            unit_index == len(units) - 1 or units[unit_index + 1].global_word_index != unit.global_word_index
            for unit_index, unit in enumerate(units)
        ]
        decoded = decode_state_score_matrix(
            len(units),
            scoring_matrix,
            self.decoder_config,
            is_word_end_state=is_word_end_state,
            is_word_start_state=is_word_start_state,
            # bucket_silence_scores=bucket_silence_scores,
            bucket_silence_scores=None,
            progress_callback=progress_callback,
        )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message="Building frame/runs from decoded DP path",
                )
            )
        outputs_started_at = time.monotonic()
        frame_alignments, word_runs = self._build_frames_and_runs_from_state_path(
            state_result=decoded,
            scoring_matrix=scoring_matrix,
            units=units,
            tokens=tokens,
            total_window_ms=total_window_ms,
            start_ms_offset=start_ms_offset,
        )
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message=(
                        f"Built frame/runs from decoded path in "
                        f"{self._format_duration_seconds(time.monotonic() - outputs_started_at)}"
                    ),
                )
            )
        summarize_started_at = time.monotonic()
        alignments = self._summarize_word_alignments_from_runs(word_runs, tokens)
        if progress_callback is not None:
            progress_callback(
                ProgressEvent(
                    stage="align",
                    message=(
                        f"Summarized word alignments in "
                        f"{self._format_duration_seconds(time.monotonic() - summarize_started_at)}"
                    ),
                )
            )
        result = AlignmentResult(
            words=alignments,
            total_score=decoded.total_score,
            backend=self.name,
            frame_alignments=frame_alignments,
            word_runs=word_runs,
            metadata={
                "stride": stride,
                "alignment_model": self.alignment_model,
                "language": self.language,
                "transcript_unit_type": "grapheme",
                "primary_output": "frame_path",
                "decoder_mode": "raw_ctc_state_dp" if self.decoder_config.state_dp_mode == "jump" else "raw_ctc_state_dp_step_by_step",
                "state_dp_engine": self.decoder_config.state_dp_engine,
                "state_dp_mode": self.decoder_config.state_dp_mode,
                "bucket_ms": self.decoder_config.bucket_ms,
                "max_repair_words": self.decoder_config.max_repair_words,
                "phrase_trace": [
                    {
                        "previous_state_index": pointer[0],
                        "start_word_index": units[state_index].global_word_index,
                        "end_word_index": units[state_index].global_word_index,
                        "start_bucket": pointer[1] if pointer is not None else 0,
                        "end_bucket": bucket_index + 1,
                        "repair_width": 1 if pointer is None or pointer[0] is None else abs(state_index - pointer[0]) + 1,
                    }
                    for state_index, row in enumerate(decoded.backpointers)
                    for bucket_index, pointer in enumerate(row[1:], start=0)
                    if pointer is not None and decoded.bucket_to_state[bucket_index] == state_index
                ],
                "decoder_debug": {
                    "bucket_count": len(scoring_matrix[0]) if scoring_matrix else 0,
                    "word_count": len(tokens),
                    "state_count": len(units),
                    "bucket_ms": self.decoder_config.bucket_ms,
                    "state_dp_engine": self.decoder_config.state_dp_engine,
                    "state_dp_mode": self.decoder_config.state_dp_mode,
                    "bucket_silence_scores": [round(value, 4) for value in bucket_silence_scores],
                    "state_rows": [
                        {
                            "state_index": unit.global_unit_index,
                            "global_word_index": unit.global_word_index,
                            "ayah_number": unit.ayah_number,
                            "char": unit.text,
                            "grapheme": unit.text,
                            "unit_kind": unit.kind,
                            "word": tokens[unit.global_word_index].original_word,
                            "normalized_word": tokens[unit.global_word_index].normalized_word,
                            "word_index_in_ayah": tokens[unit.global_word_index].word_index_in_ayah,
                            "label": (
                                f"{unit.global_unit_index}: {unit.text} "
                                f"(w{unit.global_word_index + 1} {tokens[unit.global_word_index].original_word})"
                            ),
                            "is_word_start": is_word_start_state[unit.global_unit_index],
                            "is_word_end": is_word_end_state[unit.global_unit_index],
                        }
                        for unit in units
                    ],
                    "scoring_matrix": [
                        [round(value, 4) for value in row]
                        for row in scoring_matrix
                    ],
                    "dp_scores": [
                        [None if value <= -10.0**18 / 2 else round(value, 4) for value in row]
                        for row in decoded.dp_scores
                    ],
                    "backpointers": [
                        [
                            None if pointer is None else {"prev_state_index": pointer[0], "prev_bucket": pointer[1]}
                            for pointer in row
                        ]
                        for row in decoded.backpointers
                    ],
                    "bucket_to_state": list(decoded.bucket_to_state),
                    "bucket_to_word": [
                        units[state_index].global_word_index
                        for state_index in decoded.bucket_to_state
                    ],
                },
            },
        )
        return populate_path_outputs(result=result, tokens=tokens, frames=frame_alignments, runs=word_runs)

    def _build_raw_state_score_matrix(
        self,
        *,
        emissions,
        stride: float,
        tokenizer,
        tokens_starred: list[str],
        units,
        total_window_ms: int,
        progress_callback=None,
    ) -> list[list[float]]:
        vocab = tokenizer.get_vocab()
        dictionary = {key.lower(): value for key, value in vocab.items()}
        dictionary["<star>"] = len(dictionary)
        token_id_groups = [self._resolve_unit_token_ids(tokenizer, dictionary, unit.text) for unit in units]
        bucket_count = max(1, (total_window_ms + self.decoder_config.bucket_ms - 1) // self.decoder_config.bucket_ms)
        matrix: list[list[float]] = []
        for unit_index, token_ids in enumerate(token_id_groups):
            if progress_callback is not None:
                progress_callback(
                    ProgressEvent(
                        stage="score-matrix",
                        message=f"Scoring state {unit_index + 1} of {len(token_id_groups)}",
                        completed=unit_index + 1,
                        total=len(token_id_groups),
                    )
                )
            row = [0.0] * bucket_count
            bucket_counts = [0] * bucket_count
            for frame_index in range(emissions.shape[0]):
                frame_center_ms = (frame_index + 0.5) * stride
                bucket_index = min(bucket_count - 1, int(frame_center_ms // self.decoder_config.bucket_ms))
                row[bucket_index] += sum(float(emissions[frame_index, token_id].item()) for token_id in token_ids) / max(1, len(token_ids))
                bucket_counts[bucket_index] += 1
            for bucket_index, count in enumerate(bucket_counts):
                if count:
                    row[bucket_index] /= count
            matrix.append(row)
        return matrix

    def _resolve_unit_token_ids(self, tokenizer, dictionary: dict[str, int], text: str) -> list[int]:
        token_ids: list[int] = []
        for char in text:
            if not char.strip():
                continue
            token_ids.append(self._resolve_token_id(tokenizer, dictionary, char))
        if not token_ids:
            raise KeyError(text)
        return token_ids

    def _build_bucket_silence_scores(
        self,
        *,
        emissions,
        stride: float,
        tokenizer,
        blank_token,
        total_window_ms: int,
    ) -> list[float]:
        bucket_count = max(1, (total_window_ms + self.decoder_config.bucket_ms - 1) // self.decoder_config.bucket_ms)
        scores = [0.0] * bucket_count
        bucket_counts = [0] * bucket_count
        blank_index = self._resolve_blank_token_id(tokenizer, blank_token)
        for frame_index in range(emissions.shape[0]):
            frame_center_ms = (frame_index + 0.5) * stride
            bucket_index = min(bucket_count - 1, int(frame_center_ms // self.decoder_config.bucket_ms))
            scores[bucket_index] += float(emissions[frame_index, blank_index].item())
            bucket_counts[bucket_index] += 1
        for bucket_index, count in enumerate(bucket_counts):
            if count:
                scores[bucket_index] /= count
        return scores

    def _resolve_blank_token_id(self, tokenizer, blank_token) -> int:
        if isinstance(blank_token, int):
            return blank_token
        text = str(blank_token)
        if text.isdigit():
            return int(text)
        vocab = tokenizer.get_vocab()
        direct = vocab.get(text)
        if direct is not None:
            return int(direct)
        lower_vocab = {key.lower(): value for key, value in vocab.items()}
        lower = lower_vocab.get(text.lower())
        if lower is not None:
            return int(lower)
        convert = getattr(tokenizer, "convert_tokens_to_ids", None)
        if callable(convert):
            token_id = convert(text)
            if isinstance(token_id, int) and token_id >= 0:
                return token_id
        raise ValueError(f"Could not resolve blank token id from {blank_token!r}.")

    def _tokenizer_supports_text(self, tokenizer, text: str) -> bool:
        get_vocab = getattr(tokenizer, "get_vocab", None)
        if callable(get_vocab):
            vocab = get_vocab()
            if text in vocab or text.lower() in {key.lower() for key in vocab}:
                return True
        convert = getattr(tokenizer, "convert_tokens_to_ids", None)
        if not callable(convert):
            return False
        token_id = convert(text)
        if not isinstance(token_id, int) or token_id < 0:
            return False
        unk_token = getattr(tokenizer, "unk_token", None)
        if unk_token:
            unk_id = convert(unk_token)
            if isinstance(unk_id, int) and token_id == unk_id and text != unk_token:
                return False
        return True

    def _resolve_token_id(self, tokenizer, dictionary: dict[str, int], text: str) -> int:
        direct = dictionary.get(text.lower())
        if direct is not None:
            return direct

        simplified = normalize_quranic_text(text, MODERATE_NORMALIZATION)
        if simplified:
            simplified_id = dictionary.get(simplified.lower())
            if simplified_id is not None:
                return simplified_id

        convert = getattr(tokenizer, "convert_tokens_to_ids", None)
        if callable(convert):
            candidates = [text]
            if simplified and simplified != text:
                candidates.append(simplified)
            for candidate in candidates:
                token_id = convert(candidate)
                if isinstance(token_id, int) and token_id >= 0:
                    return token_id

        unk_token = getattr(tokenizer, "unk_token", None)
        if unk_token:
            unk_id = dictionary.get(str(unk_token).lower())
            if unk_id is not None:
                return unk_id
            if callable(convert):
                token_id = convert(unk_token)
                if isinstance(token_id, int) and token_id >= 0:
                    return token_id

        raise KeyError(text)

    def _build_frames_and_runs_from_state_path(
        self,
        *,
        state_result: StateDecodeResult,
        scoring_matrix: list[list[float]],
        units,
        tokens: list[TokenRef],
        total_window_ms: int,
        start_ms_offset: int,
    ) -> tuple[list[FrameAlignment], list[AlignmentRunSegment]]:
        bucket_ms = self.decoder_config.bucket_ms
        frames: list[FrameAlignment] = []
        runs: list[AlignmentRunSegment] = []
        current_word_index = None
        current_run_start = 0
        current_scores: list[float] = []
        for bucket_index, state_index in enumerate(state_result.bucket_to_state):
            unit = units[state_index]
            word_index = unit.global_word_index
            start_ms = start_ms_offset + bucket_index * bucket_ms
            end_ms = start_ms_offset + min(total_window_ms, (bucket_index + 1) * bucket_ms)
            score = scoring_matrix[state_index][bucket_index]
            frames.append(
                FrameAlignment(
                    frame_index=bucket_index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    global_unit_index=unit.global_unit_index,
                    global_word_index=word_index,
                    score=score,
                )
            )
            if current_word_index is None:
                current_word_index = word_index
                current_run_start = bucket_index
            if word_index != current_word_index:
                runs.append(
                    AlignmentRunSegment(
                        run_index=len(runs),
                        global_word_index=current_word_index,
                        word=tokens[current_word_index].normalized_word,
                        start_ms=start_ms_offset + current_run_start * bucket_ms,
                        end_ms=start_ms_offset + bucket_index * bucket_ms,
                        score=sum(current_scores) / max(1, len(current_scores)),
                        frame_count=len(current_scores),
                    )
                )
                current_word_index = word_index
                current_run_start = bucket_index
                current_scores = []
            current_scores.append(score)
        if current_word_index is not None:
            runs.append(
                AlignmentRunSegment(
                    run_index=len(runs),
                    global_word_index=current_word_index,
                    word=tokens[current_word_index].normalized_word,
                    start_ms=start_ms_offset + current_run_start * bucket_ms,
                    end_ms=start_ms_offset + min(total_window_ms, len(state_result.bucket_to_state) * bucket_ms),
                    score=sum(current_scores) / max(1, len(current_scores)),
                    frame_count=len(current_scores),
                )
            )
        return frames, runs

    @staticmethod
    def _summarize_word_alignments_from_runs(runs: list[AlignmentRunSegment], tokens: list[TokenRef]) -> list[WordAlignment]:
        by_word: dict[int, list[AlignmentRunSegment]] = {}
        for run in runs:
            by_word.setdefault(run.global_word_index, []).append(run)
        alignments: list[WordAlignment] = []
        for word_index, token in enumerate(tokens):
            runs_for_word = by_word.get(word_index, [])
            if not runs_for_word:
                alignments.append(
                    WordAlignment(
                        global_word_index=word_index,
                        word=token.normalized_word,
                        start_ms=0,
                        end_ms=0,
                        score=0.0,
                    )
                )
                continue
            first = runs_for_word[0]
            last = runs_for_word[-1]
            alignments.append(
                WordAlignment(
                    global_word_index=word_index,
                    word=token.normalized_word,
                    start_ms=first.start_ms,
                    end_ms=last.end_ms,
                    score=sum(run.score for run in runs_for_word) / len(runs_for_word),
                )
            )
        return alignments
