from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import DEFAULT_QURAN_API_BASE_URL, default_data_dir
from .models import Ayah, SurahText
from .normalizer import split_original_words


class SurahTextError(RuntimeError):
    pass


def _local_surah_path(surah_number: int, data_dir: Path | None = None) -> Path:
    root = default_data_dir() if data_dir is None else data_dir
    return root / f"quran-simple-plain-{surah_number}.txt"


def _load_local_surah_text(surah_number: int, data_dir: Path | None = None) -> SurahText:
    path = _local_surah_path(surah_number, data_dir)
    if not path.exists():
        raise SurahTextError(f"Local surah text not found: {path}")

    ayahs: list[Ayah] = []
    for ayah_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        ayahs.append(Ayah(ayah_number=ayah_number, text=text, words=split_original_words(text)))
    if not ayahs:
        raise SurahTextError(f"No ayahs found in {path}")
    return SurahText(surah_number=surah_number, ayahs=ayahs)


def _coerce_verse_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("verses", "data"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, dict):
            nested = candidate.get("verses")
            if isinstance(nested, list):
                return nested
    raise SurahTextError("Quran.com response did not contain a verses list.")


def _extract_verse_text(row: dict[str, Any]) -> str:
    for key in ("text_uthmani", "text_imlaei", "text_indopak", "verse_text", "text"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise SurahTextError("Verse row did not contain usable text.")


def _extract_words(row: dict[str, Any], fallback_text: str) -> list[str]:
    words_payload = row.get("words")
    if isinstance(words_payload, list) and words_payload:
        words: list[str] = []
        for item in words_payload:
            if not isinstance(item, dict):
                continue
            for key in ("text_uthmani", "text_imlaei", "text", "char_type_name"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    words.append(value.strip())
                    break
        if words:
            return words
    return split_original_words(fallback_text)


def _parse_remote_surah(surah_number: int, payload: dict[str, Any]) -> SurahText:
    ayahs: list[Ayah] = []
    for row in _coerce_verse_rows(payload):
        if not isinstance(row, dict):
            continue
        text = _extract_verse_text(row)
        verse_key = row.get("verse_number") or row.get("id") or len(ayahs) + 1
        ayah_number = int(verse_key)
        ayahs.append(Ayah(ayah_number=ayah_number, text=text, words=_extract_words(row, text)))
    if not ayahs:
        raise SurahTextError(f"No ayahs returned from Quran.com for surah {surah_number}")
    ayahs.sort(key=lambda ayah: ayah.ayah_number)
    return SurahText(surah_number=surah_number, ayahs=ayahs)


def fetch_surah_text(
    surah_number: int,
    *,
    timeout: float = 20.0,
    session: object | None = None,
    api_base_url: str = DEFAULT_QURAN_API_BASE_URL,
    prefer_remote: bool = True,
    data_dir: Path | None = None,
) -> SurahText:
    if surah_number < 1 or surah_number > 114:
        raise ValueError("surah_number must be between 1 and 114")

    if prefer_remote:
        try:
            import requests

            client = session or requests.Session()
            url = f"{api_base_url}/verses/by_chapter/{surah_number}"
            params = {
                "words": "true",
                "word_fields": "text_uthmani,text_imlaei",
                "per_page": "300",
            }
            response = client.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return _parse_remote_surah(surah_number, response.json())
        except Exception:
            # This repo already ships local surah text, so fall back to it when
            # the API is unavailable or unreachable.
            pass

    return _load_local_surah_text(surah_number, data_dir=data_dir)
