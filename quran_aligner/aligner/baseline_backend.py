from __future__ import annotations

from pathlib import Path

from ..dp_decoder import DecoderConfig, WordTimingPrior, build_scoring_matrix, decode_with_segmental_dp
from ..models import AlignmentResult, TokenRef, WordAlignment
from ..mp3 import read_mp3_info
from ..path_alignment import populate_path_outputs
from ..progress import ProgressEvent


class BaselineBackend:
    name = "baseline"

    def __init__(self, *, decoder_config: DecoderConfig | None = None) -> None:
        self.decoder_config = decoder_config or DecoderConfig()

    def align(self, audio_path: str, tokens: list[TokenRef], progress_callback=None) -> AlignmentResult:
        words = [token.normalized_word for token in tokens]
        total_audio_ms = self._read_duration_ms(audio_path)
        if progress_callback is not None:
            progress_callback(ProgressEvent(stage="align", message="Building baseline timing priors"))
        weighted_words = [(word, self._word_weight(word)) for word in words]
        total_weight = sum(weight for _, weight in weighted_words) or 1

        word_alignments: list[WordAlignment] = []
        priors: list[WordTimingPrior] = []
        cursor_ms = 0
        remaining_ms = total_audio_ms

        for index, (word, weight) in enumerate(weighted_words):
            raw_duration = round(total_audio_ms * (weight / total_weight))
            duration_ms = max(1, raw_duration)
            if index == len(weighted_words) - 1:
                duration_ms = max(1, remaining_ms)
            end_ms = min(total_audio_ms, cursor_ms + duration_ms)
            word_alignments.append(
                WordAlignment(
                    global_word_index=index,
                    word=word,
                    start_ms=cursor_ms,
                    end_ms=end_ms,
                    score=0.25,
                )
            )
            priors.append(
                WordTimingPrior(
                    start_ms=cursor_ms,
                    end_ms=end_ms,
                    score=0.25,
                )
            )
            consumed = end_ms - cursor_ms
            cursor_ms = end_ms
            remaining_ms = max(0, remaining_ms - consumed)

        average_word_ms = total_audio_ms / max(1, len(words))
        if progress_callback is not None:
            progress_callback(ProgressEvent(stage="align", message="Building scoring matrix"))
        # A weak heuristic for auto-bismillah candidate selection. It slightly
        # prefers transcripts whose per-word pace is closer to a plausible
        # recitation range, while remaining transparent about being a baseline.
        total_score = -abs(average_word_ms - 450.0)
        scoring_matrix = build_scoring_matrix(
            tokens,
            priors,
            total_audio_ms,
            self.decoder_config,
            progress_callback=progress_callback,
        )
        if progress_callback is not None:
            progress_callback(ProgressEvent(stage="align", message="Running segmental DP decoder"))
        decoded = decode_with_segmental_dp(
            tokens,
            scoring_matrix,
            total_audio_ms,
            self.decoder_config,
            progress_callback=progress_callback,
        )
        result = AlignmentResult(
            words=word_alignments,
            total_score=decoded.total_score if decoded.frames else total_score,
            backend=self.name,
            frame_alignments=decoded.frames,
            word_runs=decoded.runs,
            metadata={
                "mode": "duration-weighted-baseline",
                "duration_ms": total_audio_ms,
                "average_word_ms": average_word_ms,
                "primary_output": "frame_path",
                "decoder_mode": "segmental_repair_dp",
                "bucket_ms": self.decoder_config.bucket_ms,
                "max_repair_words": self.decoder_config.max_repair_words,
                "phrase_trace": [
                    {
                        "previous_word_index": item.previous_word_index,
                        "start_word_index": item.start_word_index,
                        "end_word_index": item.end_word_index,
                        "start_bucket": item.start_bucket,
                        "end_bucket": item.end_bucket,
                        "repair_width": item.repair_width,
                    }
                    for item in decoded.phrase_trace
                ],
            },
        )
        return populate_path_outputs(result=result, tokens=tokens, frames=decoded.frames, runs=decoded.runs)

    def _read_duration_ms(self, audio_path: str) -> int:
        path = Path(audio_path)
        suffix = path.suffix.lower()
        if suffix == ".mp3":
            return int(round(read_mp3_info(path).duration_seconds * 1000))
        raise ValueError(
            "Baseline backend currently supports MP3 input only. "
            "Use an MP3 file or switch to a learned backend once installed."
        )

    @staticmethod
    def _word_weight(word: str) -> int:
        weight = max(1, len(word))
        if len(word) <= 2:
            weight += 1
        return weight
