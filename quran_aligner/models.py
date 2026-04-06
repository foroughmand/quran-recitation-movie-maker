from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Ayah:
    ayah_number: int
    text: str
    words: list[str]


@dataclass(slots=True)
class SurahText:
    surah_number: int
    ayahs: list[Ayah]


@dataclass(slots=True)
class TokenRef:
    ayah_number: int
    word_index_in_ayah: int
    original_word: str
    normalized_word: str
    normalization_profile: str


@dataclass(slots=True)
class AlignUnit:
    global_unit_index: int
    global_word_index: int
    ayah_number: int
    text: str
    kind: str


@dataclass(slots=True)
class WordAlignment:
    global_word_index: int
    word: str
    start_ms: int
    end_ms: int
    score: float


@dataclass(slots=True)
class FrameAlignment:
    frame_index: int
    start_ms: int
    end_ms: int
    global_unit_index: int | None
    global_word_index: int | None
    score: float


@dataclass(slots=True)
class AlignmentRunSegment:
    run_index: int
    global_word_index: int
    word: str
    start_ms: int
    end_ms: int
    score: float
    frame_count: int


@dataclass(slots=True)
class TimeInterval:
    start_ms: int
    end_ms: int


@dataclass(slots=True)
class WordOccurrence:
    global_word_index: int
    word: str
    intervals: list[TimeInterval]
    total_duration_ms: int
    visit_count: int


@dataclass(slots=True)
class AlignmentResult:
    words: list[WordAlignment]
    total_score: float
    backend: str
    frame_alignments: list[FrameAlignment] = field(default_factory=list)
    word_runs: list[AlignmentRunSegment] = field(default_factory=list)
    word_occurrences: list[WordOccurrence] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class AyahAlignment:
    ayah_number: int
    start_ms: int
    end_ms: int
    word_count: int
    mean_score: float


@dataclass(slots=True)
class AlignmentQuality:
    coverage: float
    zero_length_ratio: float
    has_decreasing_timestamps: bool
    has_overlapping_ayahs: bool
    average_word_score: float
    median_word_score: float
    low_score_ratio: float
    gap_count: int
    uncovered_gap_ratio: float
    warnings: list[str]


@dataclass(slots=True)
class AudioGap:
    start_ms: int
    end_ms: int
    duration_ms: int
    left_word_index: int | None
    right_word_index: int | None
    kind: str
    classification: str


@dataclass(slots=True)
class SuspiciousWord:
    global_word_index: int
    reason: str
    score: float
    start_ms: int
    end_ms: int
    flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RefinementReport:
    suspicious_words: list[SuspiciousWord]
    gaps: list[AudioGap]
    changed_word_count: int
    total_boundary_shift_ms: int
    notes: list[str]
    region_logs: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class AlignmentRun:
    surah: SurahText
    tokens: list[TokenRef]
    initial_result: AlignmentResult | None
    result: AlignmentResult
    ayah_alignments: list[AyahAlignment]
    quality: AlignmentQuality
    suspicious_words: list[SuspiciousWord] = field(default_factory=list)
    gaps: list[AudioGap] = field(default_factory=list)
    refinement: RefinementReport | None = None
