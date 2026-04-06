from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .config import BISMILLAH_TEXT
from .models import AlignUnit, Ayah, SurahText, TokenRef


ARABIC_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")
DECORATIVE_RE = re.compile(r"[\u06de\u06e9\u06dd\u06df-\u06e8]")
ARABIC_PUNCTUATION_RE = re.compile(r"[،؛؟ـ]")
PUNCTUATION_RE = re.compile(r"[^\u0600-\u06ff0-9\s]")
WHITESPACE_RE = re.compile(r"\s+")

DEFAULT_CTC_ALIGNMENT_MODEL = "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
QURAN_UTHMANI_ALIGNMENT_MODEL = "rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final"


@dataclass(slots=True, frozen=True)
class NormalizationConfig:
    profile_name: str
    remove_diacritics: bool = False
    remove_decorative_marks: bool = True
    remove_punctuation: bool = True
    normalize_alif_variants: bool = True
    normalize_alif_maqsura: bool = False
    normalize_ta_marbuta: bool = False
    normalize_hamza_on_waw_ya: bool = False
    preserved_marks: frozenset[str] = frozenset()


LIGHT_NORMALIZATION = NormalizationConfig(
    profile_name="light",
    normalize_alif_variants=False,
)
MODERATE_NORMALIZATION = NormalizationConfig(
    profile_name="moderate",
    remove_diacritics=True,
    normalize_alif_variants=True,
    normalize_alif_maqsura=True,
)
AGGRESSIVE_NORMALIZATION = NormalizationConfig(
    profile_name="aggressive",
    remove_diacritics=True,
    normalize_alif_maqsura=True,
    normalize_ta_marbuta=True,
    normalize_hamza_on_waw_ya=True,
)
QURAN_UTHMANI_NORMALIZATION = NormalizationConfig(
    profile_name="quran_uthmani",
    remove_diacritics=False,
    remove_decorative_marks=False,
    remove_punctuation=True,
    normalize_alif_variants=False,
    normalize_alif_maqsura=False,
    normalize_ta_marbuta=False,
    normalize_hamza_on_waw_ya=False,
)

NORMALIZATION_PROFILES = {
    "light": LIGHT_NORMALIZATION,
    "moderate": MODERATE_NORMALIZATION,
    "aggressive": AGGRESSIVE_NORMALIZATION,
    "quran_uthmani": QURAN_UTHMANI_NORMALIZATION,
}


def is_quran_alignment_model(alignment_model: str | None) -> bool:
    if not alignment_model:
        return False
    normalized = alignment_model.strip().lower()
    return normalized == QURAN_UTHMANI_ALIGNMENT_MODEL.lower() or "arabic-quran" in normalized


def choose_normalization_profile(
    profile: NormalizationConfig | str | None = None,
    *,
    alignment_model: str | None = None,
) -> NormalizationConfig | str | None:
    if profile is not None:
        return profile
    if is_quran_alignment_model(alignment_model):
        return QURAN_UTHMANI_NORMALIZATION.profile_name
    return LIGHT_NORMALIZATION.profile_name


def resolve_normalization_config(config: NormalizationConfig | str | None = None) -> NormalizationConfig:
    if config is None:
        return LIGHT_NORMALIZATION
    if isinstance(config, NormalizationConfig):
        return config
    try:
        return NORMALIZATION_PROFILES[config]
    except KeyError as exc:
        raise ValueError(f"Unknown normalization profile: {config}") from exc


def normalize_quranic_text(text: str, config: NormalizationConfig | None = None) -> str:
    active = resolve_normalization_config(config)
    normalized = text.strip()
    if active.remove_decorative_marks:
        normalized = "".join(
            char if (not DECORATIVE_RE.fullmatch(char) or char in active.preserved_marks) else " "
            for char in normalized
        )
    if active.remove_diacritics:
        normalized = ARABIC_DIACRITICS_RE.sub("", normalized)
    if active.remove_punctuation:
        normalized = ARABIC_PUNCTUATION_RE.sub(" ", normalized)
    if active.normalize_alif_variants:
        normalized = (
            normalized.replace("ٱ", "ا")
            .replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
        )
    if active.normalize_alif_maqsura:
        normalized = normalized.replace("ى", "ي")
    if active.normalize_ta_marbuta:
        normalized = normalized.replace("ة", "ه")
    if active.normalize_hamza_on_waw_ya:
        normalized = normalized.replace("ؤ", "و").replace("ئ", "ي")
    if active.remove_punctuation:
        normalized = PUNCTUATION_RE.sub(" ", normalized)
    normalized = WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def split_words(text: str, config: NormalizationConfig | None = None) -> list[str]:
    normalized = normalize_quranic_text(text, config)
    return [part for part in normalized.split(" ") if part]


def split_original_words(text: str) -> list[str]:
    cleaned = ARABIC_PUNCTUATION_RE.sub(" ", text.strip())
    cleaned = PUNCTUATION_RE.sub(" ", cleaned)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    return [part for part in cleaned.split(" ") if part]


def flatten_surah_to_tokens(surah: SurahText, config: NormalizationConfig | None = None) -> list[TokenRef]:
    active = resolve_normalization_config(config)
    tokens: list[TokenRef] = []
    for ayah in surah.ayahs:
        for word_index, word in enumerate(ayah.words, start=1):
            normalized_word = normalize_quranic_text(word, active)
            if not normalized_word:
                continue
            tokens.append(
                TokenRef(
                    ayah_number=ayah.ayah_number,
                    word_index_in_ayah=word_index,
                    original_word=word,
                    normalized_word=normalized_word,
                    normalization_profile=active.profile_name,
                )
            )
    return tokens


def filter_text_for_tokenizer(text: str, *, is_supported) -> str:
    filtered_chars = [char for char in text if char.isspace() or is_supported(char)]
    filtered = "".join(filtered_chars)
    return WHITESPACE_RE.sub(" ", filtered).strip()


def split_text_to_graphemes(text: str) -> list[str]:
    graphemes: list[str] = []
    current = ""
    for char in text:
        if not char.strip():
            if current:
                graphemes.append(current)
                current = ""
            continue
        is_combining = unicodedata.combining(char) > 0 or bool(ARABIC_DIACRITICS_RE.fullmatch(char)) or bool(DECORATIVE_RE.fullmatch(char))
        if is_combining and current:
            current += char
            continue
        if current:
            graphemes.append(current)
        current = char
    if current:
        graphemes.append(current)
    return graphemes


def flatten_tokens_to_align_units(tokens: list[TokenRef], mode: str = "grapheme") -> list[AlignUnit]:
    if mode not in {"char", "grapheme"}:
        raise ValueError("Only char and grapheme alignment units are supported in this version.")
    units: list[AlignUnit] = []
    global_unit_index = 0
    for global_word_index, token in enumerate(tokens):
        unit_texts = list(token.normalized_word) if mode == "char" else split_text_to_graphemes(token.normalized_word)
        for unit_text in unit_texts:
            if not unit_text.strip():
                continue
            units.append(
                AlignUnit(
                    global_unit_index=global_unit_index,
                    global_word_index=global_word_index,
                    ayah_number=token.ayah_number,
                    text=unit_text,
                    kind=mode,
                )
            )
            global_unit_index += 1
    return units


def make_bismillah_ayah() -> Ayah:
    return Ayah(ayah_number=0, text=BISMILLAH_TEXT, words=split_original_words(BISMILLAH_TEXT))


def split_bismillah_prefix(text: str, config: NormalizationConfig | None = None) -> tuple[bool, str]:
    active = resolve_normalization_config(config)
    original_words = split_original_words(text)
    bismillah_words = split_original_words(BISMILLAH_TEXT)
    if len(original_words) < len(bismillah_words):
        return False, text.strip()

    candidate_prefix = " ".join(original_words[: len(bismillah_words)])
    match_config = NormalizationConfig(
        profile_name=active.profile_name,
        remove_diacritics=True,
        remove_decorative_marks=active.remove_decorative_marks,
        remove_punctuation=active.remove_punctuation,
        normalize_alif_variants=True,
        normalize_alif_maqsura=active.normalize_alif_maqsura,
        normalize_ta_marbuta=active.normalize_ta_marbuta,
        normalize_hamza_on_waw_ya=active.normalize_hamza_on_waw_ya,
    )
    if normalize_quranic_text(candidate_prefix, match_config) == normalize_quranic_text(BISMILLAH_TEXT, match_config):
        return True, " ".join(original_words[len(bismillah_words) :]).strip()
    return False, text.strip()


def _strip_bismillah_from_first_ayah(surah: SurahText, config: NormalizationConfig | None = None) -> SurahText:
    if not surah.ayahs:
        return surah
    first, *rest = surah.ayahs
    has_bismillah, remainder = split_bismillah_prefix(first.text, config)
    if not has_bismillah:
        return surah
    updated_first = Ayah(
        ayah_number=first.ayah_number,
        text=remainder,
        words=split_original_words(remainder),
    )
    return SurahText(surah_number=surah.surah_number, ayahs=[updated_first, *rest])


def prepare_target_text(
    surah: SurahText,
    include_bismillah_mode: str,
    config: NormalizationConfig | None = None,
) -> list[SurahText]:
    if include_bismillah_mode not in {"auto", "force", "off"}:
        raise ValueError("include_bismillah_mode must be one of: auto, force, off")

    plain = _strip_bismillah_from_first_ayah(
        SurahText(surah_number=surah.surah_number, ayahs=list(surah.ayahs)),
        config,
    )
    with_bismillah = SurahText(
        surah_number=surah.surah_number,
        ayahs=[make_bismillah_ayah(), *plain.ayahs],
    )

    if include_bismillah_mode == "off":
        return [plain]
    if include_bismillah_mode == "force":
        return [with_bismillah]
    return [plain, with_bismillah]
