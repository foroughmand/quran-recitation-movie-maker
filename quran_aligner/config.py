from __future__ import annotations

from pathlib import Path


DEFAULT_QURAN_API_BASE_URL = "https://api.quran.com/api/v4"
BISMILLAH_TEXT = "بسم الله الرحمن الرحيم"


def default_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"
