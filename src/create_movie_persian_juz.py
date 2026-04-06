#!/usr/bin/env python3
"""
Create a Persian recitation movie JUZ-BY-JUZ.

For a given juz number (1–30), this script:
- Fetches which surahs/ayahs belong to that juz (Quran.com API).
- For each ayah:
  - Fetches Arabic text (glyphs) + page number from Quran.com API.
  - Reads Persian translation text from data/persian-recitation/sura_XX/translation_text.
  - Renders a frame: Arabic ayah, optional Besmellah, sura name (top-right), page (top-left), translation below.
  - Plays recitation audio (default: Tanzil Parhizgar) at configurable speed (atempo).
  - Optionally appends Persian translation voice from translation_audio/{ayah}.mp3.
- Concatenates all ayah segments into one MP4.

Requirements:
- pip install ffmpeg-python pillow requests
- Translation text: data/persian-recitation/sura_{N}/translation_text/{ayah}.txt
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

import ffmpeg
import requests
from PIL import Image, ImageDraw, ImageFont


# --- Juz verse list via Quran.com API ---
def fetch_juz_verses(juz_number: int) -> list[tuple[int, int]]:
    """Return list of (surah, ayah) for the juz (1-based). API allows max 50 per page."""
    out = []
    page = 1
    per_page = 50  # API max; see api-docs.quran.foundation verses-by-juz-number
    while True:
        r = requests.get(
            "https://api.quran.com/api/v4/verses/by_juz/%d" % juz_number,
            params={"per_page": per_page, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        verses = data.get("verses") or []
        for v in verses:
            key = v.get("verse_key") or ""
            m = re.match(r"^(\d+):(\d+)$", key)
            if m:
                out.append((int(m.group(1)), int(m.group(2))))
        if len(verses) < per_page:
            break
        pagination = data.get("pagination") or {}
        next_page = pagination.get("next_page")
        if next_page is None or next_page == page:
            break
        page = next_page
    return out


def fetch_verses_by_page(page_number: int) -> list[tuple[int, int]]:
    """Return list of (surah, ayah) for the given Quran page (1–604)."""
    out = []
    page = 1
    per_page = 20
    while True:
        r = requests.get(
            "https://api.quran.com/api/v4/verses/by_page/%d" % page_number,
            params={"per_page": per_page, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        verses = data.get("verses") or []
        for v in verses:
            key = v.get("verse_key") or ""
            m = re.match(r"^(\d+):(\d+)$", key)
            if m:
                out.append((int(m.group(1)), int(m.group(2))))
        pagination = data.get("pagination") or {}
        if not pagination.get("next_page"):
            break
        page = pagination["next_page"]
    return out


_sura_names_cache: dict[int, str] | None = None
_sura_names_fa_cache: dict[int, str] | None = None


def load_sura_names_fa(repo_root: str | None = None) -> dict[int, str]:
    """Load Persian sura names from data/sura_names_fa.txt (index -> name). Cached after first call."""
    global _sura_names_fa_cache
    if _sura_names_fa_cache is not None:
        return _sura_names_fa_cache
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo_root, "data", "sura_names_fa.txt")
    names = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    names[int(parts[0])] = parts[1]
    _sura_names_fa_cache = names
    return _sura_names_fa_cache


def fetch_sura_names() -> dict[int, str]:
    """Return dict of sura_id -> name_arabic (1–114). Cached after first call."""
    global _sura_names_cache
    if _sura_names_cache is not None:
        return _sura_names_cache
    r = requests.get("https://api.quran.com/api/v4/chapters", timeout=15)
    r.raise_for_status()
    data = r.json()
    chapters = data.get("chapters") or []
    _sura_names_cache = {}
    for c in chapters:
        sid = c.get("id")
        if sid is not None:
            _sura_names_cache[sid] = c.get("name_arabic") or c.get("name_simple") or ""
    return _sura_names_cache


def format_juz_sura_list(verses: list[tuple[int, int]], max_names: int = 10, use_persian_names: bool = True, repo_root: str | None = None) -> str:
    """Build sura list string for juz (e.g. first page): first max_names names, then '...' and total count in Persian.
    When use_persian_names is True, use data/sura_names_fa.txt; else use API Arabic names."""
    unique = sorted(set(s for s, _ in verses))
    if use_persian_names:
        names_fa = load_sura_names_fa(repo_root)
        fallback = fetch_sura_names()
        names = {s: names_fa.get(s) or fallback.get(s, str(s)) for s in unique}
    else:
        names = fetch_sura_names()
        names = {s: names.get(s, str(s)) for s in unique}
    part = [names.get(s, str(s)) for s in unique[:max_names]]
    if len(unique) <= max_names:
        return "، ".join(part)
    return "، ".join(part) + " … " + to_persian_numerals(len(unique)) + " سوره"


def fetch_ayah_words(surah: int, ayah: int) -> tuple[str, int]:
    """Fetch Arabic glyph text and page number for one verse. Returns (text, page_number)."""
    r = requests.get(
        "https://api.quran.com/api/v4/verses/by_key/%d:%d?words=true" % (surah, ayah),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    verse = data.get("verse") or {}
    words = verse.get("words") or []
    if not words:
        return "", verse.get("page_number") or 1
    # code_v1 for Uthmani script
    codes = [w.get("code_v1") or w.get("text", "") for w in words]
    text = " ".join(codes)
    # Fix trailing character as in create_movie.py
    if len(text) >= 2:
        text = text[: (len(text) - 2)] + text[(len(text) - 1) :]
    return text, verse.get("page_number") or 1


def fetch_besmellah() -> tuple[str, int]:
    """Fetch Bismillah verse (1:1) text and page."""
    return fetch_ayah_words(1, 1)


def _word_to_code(w: dict | str) -> str:
    """Extract display code from a word: either a JSON object (dict) or a JSON string. Returns code_v1 or text."""
    if isinstance(w, str):
        try:
            w = json.loads(w)
        except (json.JSONDecodeError, TypeError):
            return ""
    if not isinstance(w, dict):
        return ""
    return w.get("code_v1") or w.get("text") or ""


def _is_verse_number_token(w: dict | str) -> bool:
    """True if this word object is the verse-number token (char_type_name 'end')."""
    if isinstance(w, str):
        try:
            w = json.loads(w)
        except (json.JSONDecodeError, TypeError):
            return False
    if not isinstance(w, dict):
        return False
    return (w.get("char_type_name") or "").lower() == "end"


def fetch_besmellah_no_verse_number() -> tuple[str, int]:
    """Fetch bismillah only (no verse number) from 1:1: use all words except the verse-number token (char_type_name 'end')."""
    r = requests.get(
        "https://api.quran.com/api/v4/verses/by_key/1:1?words=true",
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    verse = data.get("verse") or {}
    words = verse.get("words") or []
    if isinstance(words, str):
        try:
            words = json.loads(words)
        except (json.JSONDecodeError, TypeError):
            words = []
    if not words:
        return "", verse.get("page_number") or 1
    # print(words)
    # Exclude verse-number token (char_type_name "end"); use only content words so no ayah number appears.
    content_words = [w for w in words if not _is_verse_number_token(w)]
    if not content_words:
        return "", verse.get("page_number") or 1
    codes = [_word_to_code(w) for w in content_words]
    text = " ".join(codes)
    # Do not apply trailing-char fix here; it can corrupt or leave verse-number glyph. Use joined codes as-is.
    return text, verse.get("page_number") or 1


def to_hindi_numerals(n: int) -> str:
    """Convert integer to Arabic-Indic (Hindi) numeral string."""
    return "".join(chr(0x0660 + int(d)) for d in str(n))


def to_persian_numerals(n: int) -> str:
    """Convert integer to Persian/Extended Arabic-Indic numeral string (۰۱۲۳۴۵۶۷۸۹)."""
    return "".join(chr(0x06F0 + int(d)) for d in str(n))


@dataclass
class TextInfo:
    text: str
    font: str
    font_size: int
    font_color: str
    stroke_width: int
    stroke_color: str


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap text into lines that fit within max_width."""
    words = text.split()
    if not words:
        return []
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def create_full_text_image_persian(
    size: tuple[int, int],
    margin_h: int,
    margin_v: int,
    interline: int,
    main_text: TextInfo,
    translation_below: TextInfo | None,
    short_text_right: str | None,
    short_font_path: str | None,
    short_font_size: int,
    short_text_left: str | None,
    short_left_font_path: str | None,
    short_left_font_size: int,
    besmellah: TextInfo | None,
    filename: str,
    short_text_center: str | None = None,
    short_center_font_path: str | None = None,
    short_center_font_size: int = 48,
    short_text_left_extra: str | None = None,
    highlight_main_word_index: int | None = None,
    highlight_main_word_color: str = "#FFFF00",
) -> None:
    """Draw one frame: optional left/center/right headers, optional Besmellah, main Arabic, wrapped translation below. Shrinks ayah and translation fonts to fit."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    min_top = margin_v

    if short_text_left and short_left_font_path:
        left_font = ImageFont.truetype(short_left_font_path, short_left_font_size)
        draw.text(
            (margin_h, margin_v),
            short_text_left,
            font=left_font,
            fill=(255, 255, 255),
            stroke_fill=main_text.stroke_color,
            stroke_width=main_text.stroke_width,
            anchor="la",
        )
        min_top = max(min_top, margin_v + draw.textbbox((0, 0), short_text_left, font=left_font)[3])
        if short_text_left_extra:
            left_box = draw.textbbox((0, 0), short_text_left, font=left_font)
            extra_x = margin_h + left_box[2] + max(12, interline // 2)
            draw.text(
                (extra_x, margin_v),
                short_text_left_extra,
                font=left_font,
                fill=(255, 255, 255),
                stroke_fill=main_text.stroke_color,
                stroke_width=main_text.stroke_width,
                anchor="la",
            )
            min_top = max(min_top, margin_v + draw.textbbox((0, 0), short_text_left_extra, font=left_font)[3])

    if short_text_center and short_center_font_path:
        center_font = ImageFont.truetype(short_center_font_path, short_center_font_size)
        draw.text(
            (size[0] // 2, margin_v),
            short_text_center,
            font=center_font,
            fill=(255, 255, 255),
            stroke_fill=main_text.stroke_color,
            stroke_width=main_text.stroke_width,
            anchor="ma",
        )
        min_top = max(min_top, margin_v + draw.textbbox((0, 0), short_text_center, font=center_font)[3])

    if short_text_right and short_font_path:
        try:
            right_font = ImageFont.truetype(short_font_path, short_font_size)
        except Exception as e:
            print('Error: ', e, short_font_path)
            raise e
        draw.text(
            (size[0] - margin_h, margin_v),
            short_text_right,
            font=right_font,
            fill=(255, 255, 255),
            stroke_fill=main_text.stroke_color,
            stroke_width=main_text.stroke_width,
            anchor="ra",
        )
        min_top = max(min_top, margin_v + draw.textbbox((0, 0), short_text_right, font=right_font)[3])

    max_width = size[0] - 2 * margin_h
    # Use copies so we can shrink without affecting caller
    main_font_size = main_text.font_size
    trans_font_size = translation_below.font_size if translation_below else 0
    besm_font_size = int(besmellah.font_size * 1.0) if besmellah and besmellah.text else 0
    inter = interline

    while True:
        main_font = ImageFont.truetype(main_text.font, main_font_size)
        main_lines = _wrap_text(draw, main_text.text, main_font, max_width)
        main_heights = [draw.textbbox((0, 0), ln, font=main_font)[3] for ln in main_lines]
        total_main_h = sum(main_heights) + (len(main_lines) - 1) * inter if main_lines else 0

        trans_lines: list[str] = []
        total_trans_h = 0
        if translation_below and translation_below.text.strip():
            trans_font = ImageFont.truetype(translation_below.font, trans_font_size)
            trans_lines = _wrap_text(draw, translation_below.text, trans_font, max_width)
            trans_heights = [draw.textbbox((0, 0), ln, font=trans_font)[3] for ln in trans_lines]
            total_trans_h = sum(trans_heights) + (len(trans_lines) - 1) * inter if trans_lines else 0

        besm_h = 0
        if besmellah and besmellah.text:
            bfont = ImageFont.truetype(besmellah.font, besm_font_size)
            besm_h = draw.textbbox((0, 0), besmellah.text, font=bfont)[3] + inter

        total_center = total_main_h + total_trans_h + besm_h
        y_cur = (size[1] - total_center) // 2
        if y_cur >= min_top and total_center <= size[1] - 2 * margin_v:
            break
        if main_font_size < 8:
            break
        main_font_size = max(8, int(main_font_size * 0.9))
        if trans_font_size:
            trans_font_size = max(8, int(trans_font_size * 0.9))
        if besm_font_size:
            besm_font_size = max(8, int(besm_font_size * 0.9))
        inter = max(4, int(inter * 0.9))

    # Recompute final fonts and wrapped lines with chosen sizes
    main_font = ImageFont.truetype(main_text.font, main_font_size)
    main_lines = _wrap_text(draw, main_text.text, main_font, max_width)
    main_heights = [draw.textbbox((0, 0), ln, font=main_font)[3] for ln in main_lines]
    total_main_h = sum(main_heights) + (len(main_lines) - 1) * inter if main_lines else 0

    trans_lines = []
    trans_heights: list[int] = []
    if translation_below and translation_below.text.strip():
        trans_font = ImageFont.truetype(translation_below.font, trans_font_size)
        trans_lines = _wrap_text(draw, translation_below.text, trans_font, max_width)
        trans_heights = [draw.textbbox((0, 0), ln, font=trans_font)[3] for ln in trans_lines]
    total_trans_h = sum(trans_heights) + (len(trans_lines) - 1) * inter if trans_lines else 0

    besm_h = 0
    if besmellah and besmellah.text:
        besm_font = ImageFont.truetype(besmellah.font, besm_font_size)
        besm_h = draw.textbbox((0, 0), besmellah.text, font=besm_font)[3] + inter

    total_center = total_main_h + total_trans_h + besm_h
    y_cur = (size[1] - total_center) // 2
    if y_cur < min_top:
        y_cur = min_top

    if besmellah and besmellah.text:
        besm_font = ImageFont.truetype(besmellah.font, besm_font_size)
        draw.text(
            (size[0] // 2, y_cur + besm_font.size // 2),
            besmellah.text,
            font=besm_font,
            fill=(255, 255, 255),
            stroke_fill=besmellah.stroke_color,
            stroke_width=besmellah.stroke_width,
            anchor="mm",
        )
        y_cur += besm_h

    def _draw_highlighted_main_line(line: str, top_y: int, line_height: int, start_word_index: int) -> int:
        words = line.split()
        if not words:
            return start_word_index
        segments: list[tuple[str, str]] = []
        idx = 0
        global_word_index = start_word_index
        for word in words:
            if idx > 0:
                segments.append((" ", "white"))
            color = highlight_main_word_color if global_word_index == highlight_main_word_index else "white"
            segments.append((word, color))
            idx += 1
            global_word_index += 1
        total_w = sum(draw.textbbox((0, 0), seg_text, font=main_font)[2] for seg_text, _ in segments)
        x_cur = size[0] // 2 + total_w // 2
        for seg_text, color in segments:
            seg_w = draw.textbbox((0, 0), seg_text, font=main_font)[2]
            x_cur -= seg_w
            draw.text(
                (x_cur + seg_w // 2, top_y + line_height // 2),
                seg_text,
                font=main_font,
                fill=color,
                stroke_fill=main_text.stroke_color,
                stroke_width=main_text.stroke_width,
                anchor="mm",
            )
        return global_word_index

    main_word_index = 0
    for i, line in enumerate(main_lines):
        lh = main_heights[i]
        if highlight_main_word_index is None:
            draw.text(
                (size[0] // 2, y_cur + lh // 2),
                line,
                font=main_font,
                fill=(255, 255, 255),
                stroke_fill=main_text.stroke_color,
                stroke_width=main_text.stroke_width,
                anchor="mm",
            )
            main_word_index += len(line.split())
        else:
            main_word_index = _draw_highlighted_main_line(line, y_cur, lh, main_word_index)
        y_cur += lh + inter

    if trans_lines:
        trans_font = ImageFont.truetype(translation_below.font, trans_font_size)
        for i, line in enumerate(trans_lines):
            lh = trans_heights[i]
            draw.text(
                (size[0] // 2, y_cur + lh // 2),
                line,
                font=trans_font,
                fill=(255, 255, 255),
                stroke_fill=translation_below.stroke_color,
                stroke_width=translation_below.stroke_width,
                anchor="mm",
            )
            y_cur += lh + inter

    img.save(filename, format="PNG")


def recitation_url_for_ayah(template: str, surah: int, ayah: int) -> str:
    """Fill template with {sura} and {ayah} (3-digit)."""
    return template.replace("{sura}", "%03d" % surah).replace("{ayah}", "%03d" % ayah)


def create_juz_intro_image(
    juz_number: int,
    reciter_name: str,
    page_start: int,
    page_end: int,
    args: argparse.Namespace,
    repo_root: str,
    filename: str,
    custom_text: str | None = None,
) -> None:
    """Draw intro frame. If custom_text is set, draw it line by line (\\n-separated); else juz, reciter, pages."""
    img = Image.new("RGBA", (args.size_x, args.size_y), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    trans_font_path = args.translation_font
    if not os.path.isabs(trans_font_path):
        trans_font_path = os.path.join(repo_root, trans_font_path)
    title_font_path = args.title_font
    if not os.path.isabs(title_font_path):
        title_font_path = os.path.join(repo_root, title_font_path)
    cx = args.size_x // 2
    stroke_w = args.stroke_width
    stroke_c = "black"

    if custom_text and custom_text.strip():
        lines = [ln.strip() for ln in custom_text.strip().split("\n") if ln.strip()]
        if not lines:
            lines = ["جزء " + to_persian_numerals(juz_number)]
        font_size = max(28, min(72, args.title_font_size))
        font = ImageFont.truetype(trans_font_path, font_size)
        line_heights = [draw.textbbox((0, 0), ln, font=font)[3] for ln in lines]
        total_h = sum(line_heights) + (len(lines) - 1) * args.interline
        y = (args.size_y - total_h) // 2
        for i, line in enumerate(lines):
            lh = line_heights[i]
            draw.text((cx, y + lh // 2), line, font=font, fill="white", stroke_fill=stroke_c, stroke_width=stroke_w, anchor="mm")
            y += lh + args.interline
        img.save(filename, format="PNG")
        return

    juz_font_size = max(72, args.title_font_size)
    name_font_size = max(36, args.translation_font_size)
    line_font_size = max(28, args.translation_font_size)
    juz_font = ImageFont.truetype(trans_font_path, juz_font_size)
    name_font = ImageFont.truetype(trans_font_path, name_font_size)
    line_font = ImageFont.truetype(trans_font_path, line_font_size)
    margin_v = args.margin_v
    y = args.size_y // 2 - (juz_font_size + name_font_size + line_font_size + 2 * args.interline) // 2
    juz_label = "جزء " + to_persian_numerals(juz_number)
    draw.text((cx, y), juz_label, font=juz_font, fill="white", stroke_fill=stroke_c, stroke_width=stroke_w, anchor="mm")
    y += juz_font_size + args.interline
    if reciter_name:
        draw.text((cx, y), reciter_name, font=name_font, fill="white", stroke_fill=stroke_c, stroke_width=stroke_w, anchor="mm")
        y += name_font_size + args.interline
    pages_label = "صفحه " + to_persian_numerals(page_start) + " تا " + to_persian_numerals(page_end)
    draw.text((cx, y), pages_label, font=line_font, fill="white", stroke_fill=stroke_c, stroke_width=stroke_w, anchor="mm")
    img.save(filename, format="PNG")


def _is_valid_video_file(path: str) -> bool:
    """Return True if path is a valid video file (ffprobe can read duration). Use to detect corrupt clips."""
    return _get_video_duration_seconds(path) > 0


def _get_video_duration_seconds(path: str) -> float:
    """Return duration in seconds of a video file via ffprobe, or 0.0 on error."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout and out.stdout.strip():
            return float(out.stdout.strip())
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        pass
    return 0.0


def _download_recitation_to_cache(url: str, local_path: str) -> None:
    """Download URL to local_path (overwrite if exists)."""
    r = requests.get(url, timeout=60, stream=True)
    r.raise_for_status()
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)


def _get_audio_duration_seconds(audio_path: str) -> float:
    """Return duration in seconds of an audio file (e.g. MP3) via ffprobe."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        pass
    return 0.0


def build_ayah_segments(
    juz_number: int,
    verses: list[tuple[int, int]],
    args: argparse.Namespace,
    segments: list[str],
) -> list[str]:
    """For each (surah, ayah): render frame, build segment with recitation (+ optional translation) audio. Append segment path to segments."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font_base = args.font.format(h_page=1)
    if not os.path.isabs(font_base):
        font_base = os.path.join(repo_root, font_base)
    title_font = args.title_font
    if not os.path.isabs(title_font):
        title_font = os.path.join(repo_root, title_font)
    trans_font = args.translation_font
    if not os.path.isabs(trans_font):
        trans_font = os.path.join(repo_root, trans_font)

    besm_text, besm_page = fetch_besmellah_no_verse_number()
    besm_font_path = args.font.format(h_page=besm_page)
    if not os.path.isabs(besm_font_path):
        besm_font_path = os.path.join(repo_root, besm_font_path)

    # Recitation cache: avoid ffmpeg opening the same URL 148 times (slow). Download once per ayah to local cache.
    recitation_cache_dir = os.path.join(tempfile.gettempdir(), "juz_recitation_cache", "juz%d" % juz_number)
    os.makedirs(recitation_cache_dir, exist_ok=True)

    # If using a long background video, extract one clip (e.g. 2h) so we don't open the 10h file 148 times.
    # Use subprocess so -ss/-t are passed correctly (ffmpeg-python can mis-apply t= and produce empty output).
    bg_video_path = args.background_video
    bg_clip_start = args.bg_clip_start
    t_bg_extract = 0.0
    if args.background_video and os.path.isfile(args.background_video):
        safe_name = os.path.basename(args.background_video).replace(" ", "_")[:80]
        # Include start offset in clip path so we don't reuse a clip extracted for a different start.
        clip_path = os.path.join(tempfile.gettempdir(), "juz_bg_clip_%d_%s_start%d.mp4" % (juz_number, safe_name, int(args.bg_clip_start)))
        if os.path.isfile(clip_path):
            clip_dur = _get_video_duration_seconds(clip_path)
            print("  [bg] reusing_existing_clip=1 path=%s duration=%.2f s" % (clip_path, clip_dur))
        if not os.path.isfile(clip_path):
            t0 = time.perf_counter()
            print("  Extracting 2h background clip (once)...")
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-ss", str(args.bg_clip_start),
                        "-t", "7200",
                        "-i", args.background_video,
                        "-c", "copy",
                        clip_path,
                    ],
                    check=True,
                    capture_output=True,
                    timeout=600,
                )
                t_bg_extract = time.perf_counter() - t0
                print("  bg_extract=%.1fs" % t_bg_extract)
                clip_dur = _get_video_duration_seconds(clip_path)
                print("  [bg] extracted_clip_duration=%.2f s" % clip_dur)
                if not _is_valid_video_file(clip_path):
                    print("  Warning: extracted clip invalid (corrupt?), using original background video.")
                    try:
                        os.remove(clip_path)
                    except OSError:
                        pass
                    clip_path = ""
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                clip_path = ""
        if clip_path and os.path.isfile(clip_path):
            if not _is_valid_video_file(clip_path):
                print("  Warning: extracted clip invalid (corrupt?), using original background video.")
                try:
                    os.remove(clip_path)
                except OSError:
                    pass
                clip_path = ""
            else:
                bg_video_path = clip_path
                bg_clip_start = 0.0  # 0 within the clip; clip content = original from args.bg_clip_start
                print("  [bg] using_extracted_clip=1 path=%s (original range %.0f–%.0f s)" % (clip_path, args.bg_clip_start, args.bg_clip_start + 7200))

    if bg_video_path and os.path.isfile(bg_video_path):
        print("  [bg] path=%s" % os.path.abspath(bg_video_path))
        dur = _get_video_duration_seconds(bg_video_path)
        print("  [bg] file_duration=%.2f s" % dur)
        remaining = (dur - bg_clip_start) if (dur > 0 and dur > bg_clip_start) else 0.0
        if bg_clip_start > 0:
            print("  [bg] using_original_file=1 (remaining_from_start=%.2f s)" % remaining)

        # Required duration = intro + sum of all segment durations (recitation + optional translation per ayah).
        first_ayah_is_sura_start = verses[0][1] == 1
        full_bismillah = getattr(args, "full_bismillah_intro", False)
        bismillah_url = recitation_url_for_ayah(args.recitation_template, 1, 1)
        bismillah_local = os.path.join(recitation_cache_dir, "001_001.mp3")
        if not os.path.isfile(bismillah_local):
            _download_recitation_to_cache(bismillah_url, bismillah_local)
        intro_audio_dur = _get_audio_duration_seconds(bismillah_local)
        intro_required = (intro_audio_dur if full_bismillah else min(3.0, intro_audio_dur)) if first_ayah_is_sura_start else intro_audio_dur
        if args.speed != 1.0 and intro_required > 0:
            intro_required = intro_required / args.speed
        total_required_sec = intro_required
        for surah, ayah in verses:
            rec_url = recitation_url_for_ayah(args.recitation_template, surah, ayah)
            rec_local = os.path.join(recitation_cache_dir, "%03d_%03d.mp3" % (surah, ayah))
            if not os.path.isfile(rec_local):
                _download_recitation_to_cache(rec_url, rec_local)
            rec_d = _get_audio_duration_seconds(rec_local)
            if getattr(args, "debug_limit_recitation_sec", None) is not None and args.debug_limit_recitation_sec > 0:
                rec_d = min(rec_d, args.debug_limit_recitation_sec)
            if args.speed != 1.0 and rec_d > 0:
                rec_d = rec_d / args.speed
            if rec_d <= 0:
                rec_d = 1.0
            total_required_sec += rec_d
            if args.include_translation_audio:
                trans_file = os.path.join(args.translation_root, "sura_%d" % surah, "translation_audio", "%d.mp3" % ayah)
                if os.path.isfile(trans_file):
                    trans_d = _get_audio_duration_seconds(trans_file)
                    if getattr(args, "debug_limit_translation_sec", None) is not None and args.debug_limit_translation_sec > 0:
                        trans_d = min(trans_d, args.debug_limit_translation_sec)
                    if args.speed != 1.0 and trans_d > 0:
                        trans_d = trans_d / args.speed
                    if trans_d > 0:
                        total_required_sec += trans_d
        print("  [bg] required_duration=%.2f s (intro + %d ayahs)" % (total_required_sec, len(verses)))

        if remaining < total_required_sec:
            print("Error: not enough remaining time in background video (remaining=%.1f s, required=%.1f s). Exit so caller can switch to next bg." % (remaining, total_required_sec), file=sys.stderr)
            sys.exit(2)
        print("  [bg] start_offset=%.2f s" % bg_clip_start)

    # Juz intro page (before first ayah): juz number, reciter name, pages (or custom --first_page).
    # Intro audio: always auzobellah (first 3 s of 1:1). Then bismillah (rest of 1:1) only if the first ayah is NOT the start of a sura.
    page_start = fetch_ayah_words(verses[0][0], verses[0][1])[1]
    page_end = fetch_ayah_words(verses[-1][0], verses[-1][1])[1]
    first_ayah_is_sura_start = verses[0][1] == 1  # first ayah of juz is ayah 1 of a sura
    full_bismillah = getattr(args, "full_bismillah_intro", False)
    reciter_name = getattr(args, "reciter_name", "") or ""
    first_page_template = getattr(args, "first_page", "") or ""
    custom_intro_text = None
    if first_page_template.strip():
        sura_list_str = format_juz_sura_list(verses, max_names=10)
        custom_intro_text = (
            first_page_template.replace("{JOZ}", to_persian_numerals(juz_number))
            .replace("{SURELIST}", sura_list_str)
        )
    fd_intro, intro_img_path = tempfile.mkstemp(suffix=".png", prefix="juz_intro_")
    os.close(fd_intro)
    try:
        create_juz_intro_image(juz_number, reciter_name, page_start, page_end, args, repo_root, intro_img_path, custom_text=custom_intro_text)
    except Exception:
        os.remove(intro_img_path)
        raise
    bismillah_url = recitation_url_for_ayah(args.recitation_template, 1, 1)
    bismillah_local = os.path.join(recitation_cache_dir, "001_001.mp3")
    if not os.path.isfile(bismillah_local):
        _download_recitation_to_cache(bismillah_url, bismillah_local)
    intro_audio = ffmpeg.input(bismillah_local).audio
    if first_ayah_is_sura_start and not full_bismillah:
        intro_audio = intro_audio.filter("atrim", duration=3.0).filter("asetpts", "PTS-STARTPTS")
    if abs(args.speed - 1.0) > 1e-6:
        intro_audio = intro_audio.filter("atempo", args.speed)
    intro_audio_dur_file = _get_audio_duration_seconds(bismillah_local)
    if first_ayah_is_sura_start and not full_bismillah:
        intro_dur = min(3.0, intro_audio_dur_file)
    else:
        intro_dur = intro_audio_dur_file
    if args.speed != 1.0 and intro_dur > 0:
        intro_dur = intro_dur / args.speed
    print("  [intro] voice file=%s file_duration=%.2f s segment_dur=%.2f s" % (os.path.basename(bismillah_local), intro_audio_dur_file, intro_dur))
    intro_seg_path = intro_img_path.replace(".png", "_intro.mp4")
    if bg_video_path and os.path.isfile(bg_video_path):
        print("  [intro] ffmpeg_input ss=%.2f trim duration=%.2f" % (bg_clip_start, intro_dur))
        intro_video = ffmpeg.input(bg_video_path, ss=bg_clip_start).video
        intro_video = intro_video.filter("trim", duration=intro_dur).filter("setpts", "PTS-STARTPTS")
    else:
        intro_video = ffmpeg.input("color=c=black:s=%dx%d:d=%.2f" % (args.size_x, args.size_y, intro_dur), f="lavfi").video
    intro_video = intro_video.filter("scale", args.size_x, args.size_y)
    intro_img_in = ffmpeg.input(intro_img_path).video
    intro_video = ffmpeg.overlay(intro_video, intro_img_in, x="(main_w-overlay_w)/2", y="(main_h-overlay_h)/2")
    out = ffmpeg.output(intro_video, intro_audio, intro_seg_path, vcodec="libx264", acodec="aac", r=args.fps, pix_fmt="yuv420p", shortest=None)
    out = out.overwrite_output()
    intro_cmd = out.compile()
    print("  [intro] ffmpeg cmd (how out is created): %s" % " ".join(intro_cmd))
    print("  [intro] out path=%s" % intro_seg_path)
    try:
        out.run(quiet=True)
    except ffmpeg.Error as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr or "")
        os.remove(intro_img_path)
        raise RuntimeError("FFmpeg failed for juz intro: %s" % err) from e
    segments.append(intro_seg_path)
    intro_seg_size = os.path.getsize(intro_seg_path) if os.path.isfile(intro_seg_path) else 0
    print("  [intro] out size_bytes=%d (after run)" % intro_seg_size)
    # Log raw ffprobe duration to verify actual_dur.
    try:
        probe_out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", intro_seg_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw_duration = (probe_out.stdout or "").strip() if probe_out.stdout else ""
        print("  [intro] ffprobe format=duration raw_stdout=%r returncode=%s" % (raw_duration, probe_out.returncode))
        intro_seg_dur = float(raw_duration) if raw_duration else 0.0
        print("  [intro] parsed actual_dur=%.2f s" % intro_seg_dur)
    except (ValueError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        intro_seg_dur = _get_video_duration_seconds(intro_seg_path)
        print("  [intro] ffprobe parse failed (%s), used _get_video_duration_seconds -> %.2f s" % (e, intro_seg_dur))
    print("  [intro] expected_dur=%.2f s actual_dur=%.2f s — جزء %s — %s — صفحه %s تا %s (%s)" % (
        intro_dur, intro_seg_dur,
        to_persian_numerals(juz_number), reciter_name or "—", to_persian_numerals(page_start), to_persian_numerals(page_end),
        "full bismillah" if full_bismillah else ("auzobellah only (3 s)" if first_ayah_is_sura_start else "auzobellah + bismillah")))
    # [seg_params] intro: how each value is obtained:
    #   video_src   = os.path.basename(bg_video_path)  — background file name
    #   video_ss    = bg_clip_start  — from args.bg_clip_start (or 0 if using extracted clip)
    #   video_trim  = intro_dur  — from bismillah audio: _get_audio_duration_seconds(bismillah_local), or min(3.0, that) if first ayah is sura start; then / args.speed
    #   bg_file_duration = dur  — _get_video_duration_seconds(bg_video_path), i.e. ffprobe -show_entries format=duration
    #   audio_src   = os.path.basename(bismillah_local)  — e.g. 001_001.mp3
    #   audio_dur   = intro_dur  — same as video_trim
    #   out         = os.path.basename(intro_seg_path)  — written segment path
    #   actual_dur  = intro_seg_dur  — _get_video_duration_seconds(intro_seg_path) after out.run(), i.e. ffprobe on the written MP4
    if bg_video_path and os.path.isfile(bg_video_path):
        print("  [seg_params] intro video_src=%s video_ss=%.2f video_trim=%.2f bg_file_duration=%.2f audio_src=%s audio_dur=%.2f out=%s actual_dur=%.2f" % (
            os.path.basename(bg_video_path), bg_clip_start, intro_dur, dur, os.path.basename(bismillah_local), intro_dur, os.path.basename(intro_seg_path), intro_seg_dur))
    else:
        print("  [seg_params] intro video_src=lavfi video_trim=%.2f audio_src=%s audio_dur=%.2f out=%s actual_dur=%.2f" % (
            intro_dur, os.path.basename(bismillah_local), intro_dur, os.path.basename(intro_seg_path), intro_seg_dur))

    # Per-step timings (seconds) for summary
    tot_api, tot_render, tot_download, tot_ffmpeg = 0.0, 0.0, 0.0, 0.0
    idx = 0
    for surah, ayah in verses:
        idx += 1
        t_ayah_start = time.perf_counter()

        t0 = time.perf_counter()
        arabic_text, page = fetch_ayah_words(surah, ayah)
        t_api = time.perf_counter() - t0
        tot_api += t_api
        main_font_path = args.font.format(h_page=page)
        if not os.path.isabs(main_font_path):
            main_font_path = os.path.join(repo_root, main_font_path)

        trans_path = os.path.join(
            args.translation_root,
            "sura_%d" % surah,
            "translation_text",
            "%d.txt" % ayah,
        )
        trans_text = ""
        if os.path.isfile(trans_path):
            with open(trans_path, "r", encoding="utf-8") as f:
                trans_text = f.read().strip()

        page_label = "صفحه " + to_persian_numerals(page) if args.show_page else ""
        # (translation read is negligible, not timed separately)
        sura_label = "%03d surah" % surah
        juz_label = ("جزء " + to_persian_numerals(args.juz_number)) if getattr(args, "show_juz", False) else None

        add_besmellah = ayah == 1 and surah != 1 and surah != 9
        besmellah_info = None
        if add_besmellah and besm_text:
            besmellah_info = TextInfo(
                besm_text,
                besm_font_path,
                int(args.font_size * 1.3),
                "white",
                args.stroke_width,
                "black",
            )

        main_info = TextInfo(
            arabic_text,
            main_font_path,
            args.font_size,
            "white",
            args.stroke_width,
            "black",
        )
        trans_info = TextInfo(
            trans_text,
            trans_font,
            args.translation_font_size,
            "white",
            args.stroke_width,
            "black",
        ) if trans_text else None

        fd, temp_img = tempfile.mkstemp(suffix=".png", prefix="juz_")
        os.close(fd)
        t0 = time.perf_counter()
        try:
            create_full_text_image_persian(
                size=(args.size_x, args.size_y),
                margin_h=args.margin_h,
                margin_v=args.margin_v,
                interline=args.interline,
                main_text=main_info,
                translation_below=trans_info,
                short_text_right=sura_label,
                short_font_path=title_font if sura_label else None,
                short_font_size=args.title_font_size,
                short_text_left=page_label,
                short_left_font_path=trans_font if page_label else None,
                short_left_font_size=args.translation_font_size,
                besmellah=besmellah_info,
                filename=temp_img,
                short_text_center=juz_label,
                short_center_font_path=trans_font if juz_label else None,
                short_center_font_size=args.translation_font_size,
            )
        except Exception:
            os.remove(temp_img)
            raise
        t_render = time.perf_counter() - t0
        tot_render += t_render

        t_download = 0.0
        rec_url = recitation_url_for_ayah(args.recitation_template, surah, ayah)
        rec_local = os.path.join(recitation_cache_dir, "%03d_%03d.mp3" % (surah, ayah))
        if not os.path.isfile(rec_local):
            t0 = time.perf_counter()
            _download_recitation_to_cache(rec_url, rec_local)
            t_download = time.perf_counter() - t0
            tot_download += t_download
        rec_audio = ffmpeg.input(rec_local).audio
        if abs(args.speed - 1.0) > 1e-6:
            rec_audio = rec_audio.filter("atempo", args.speed)
        limit_rec = getattr(args, "debug_limit_recitation_sec", None)
        if limit_rec is not None and limit_rec > 0:
            rec_audio = rec_audio.filter("atrim", duration=limit_rec).filter("asetpts", "PTS-STARTPTS")

        rec_dur_file = _get_audio_duration_seconds(rec_local)
        rec_dur = rec_dur_file
        if limit_rec is not None and limit_rec > 0:
            rec_dur = min(rec_dur, limit_rec)
        if args.speed != 1.0 and rec_dur > 0:
            rec_dur = rec_dur / args.speed
        if rec_dur <= 0:
            rec_dur = 1.0
        print("  [voice] ayah %d_%d file=%s file_duration=%.2f s segment_dur=%.2f s" % (surah, ayah, os.path.basename(rec_local), rec_dur_file, rec_dur))
        rec_seg_basename = os.path.basename(temp_img).replace(".png", "_r_%d.mp4" % idx)
        if bg_video_path and os.path.isfile(bg_video_path):
            print("  [seg_params] ayah_%d_%d video_src=%s video_ss=%.2f video_trim=%.2f bg_file_duration=%.2f audio_src=%s audio_dur=%.2f out=%s" % (
                surah, ayah, os.path.basename(bg_video_path), bg_clip_start, rec_dur, dur, os.path.basename(rec_local), rec_dur, rec_seg_basename))
        else:
            print("  [seg_params] ayah_%d_%d video_src=lavfi video_trim=%.2f audio_src=%s audio_dur=%.2f out=%s" % (
                surah, ayah, rec_dur, os.path.basename(rec_local), rec_dur, rec_seg_basename))

        t_ffmpeg_ayah = [0.0]  # use list so nested function can update

        def make_segment(label: str, audio_input, segment_dur: float):
            nonlocal bg_clip_start
            seg_path = temp_img.replace(".png", "_%s_%d.mp4" % (label, idx))
            if bg_video_path and os.path.isfile(bg_video_path):
                print("  [seg] ffmpeg_input ss=%.2f trim duration=%.2f -> %s" % (bg_clip_start, segment_dur, os.path.basename(seg_path)))
                # Use trim filter so video is exactly segment_dur (input t= can be mis-applied by ffmpeg-python and yield empty stream)
                video_stream = ffmpeg.input(bg_video_path, ss=bg_clip_start).video
                video_stream = video_stream.filter("trim", duration=segment_dur).filter("setpts", "PTS-STARTPTS")
            else:
                video_stream = ffmpeg.input(
                    "color=c=black:s=%dx%d:d=%.2f" % (args.size_x, args.size_y, segment_dur),
                    f="lavfi",
                ).video
            video_stream = video_stream.filter("scale", args.size_x, args.size_y)
            # Single image as overlay (background video is long; shortest=1 makes output = min(video, audio) = audio length)
            img = ffmpeg.input(temp_img).video
            video_stream = ffmpeg.overlay(
                video_stream,
                img,
                x="(main_w-overlay_w)/2",
                y="(main_h-overlay_h)/2",
            )
            out = ffmpeg.output(
                video_stream,
                audio_input,
                seg_path,
                vcodec="libx264",
                acodec="aac",
                r=args.fps,
                pix_fmt="yuv420p",
                shortest=None,  # flag only: stop at shortest stream (no value, or "1" is misparsed as output)
            )
            out = out.overwrite_output()
            try:
                t0 = time.perf_counter()
                out.run(quiet=True)
                t_ffmpeg_ayah[0] += time.perf_counter() - t0
            except ffmpeg.Error as e:
                err = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or str(e))
                raise RuntimeError("FFmpeg failed for segment %s: %s" % (seg_path, err)) from e
            segments.append(seg_path)
            seg_actual_dur = _get_video_duration_seconds(seg_path)
            print("  [seg] %s expected_dur=%.2f s actual_dur=%.2f s" % (os.path.basename(seg_path), segment_dur, seg_actual_dur))
            bg_clip_start += segment_dur

        make_segment("r", rec_audio, rec_dur)
        tot_ffmpeg += t_ffmpeg_ayah[0]

        if args.include_translation_audio:
            trans_audio_dir = os.path.join(
                args.translation_root,
                "sura_%d" % surah,
                "translation_audio",
            )
            trans_file = os.path.join(trans_audio_dir, "%d.mp3" % ayah)
            if os.path.isfile(trans_file):
                trans_audio = ffmpeg.input(trans_file).audio
                if abs(args.speed - 1.0) > 1e-6:
                    trans_audio = trans_audio.filter("atempo", args.speed)
                limit_trans = getattr(args, "debug_limit_translation_sec", None)
                if limit_trans is not None and limit_trans > 0:
                    trans_audio = trans_audio.filter("atrim", duration=limit_trans).filter("asetpts", "PTS-STARTPTS")
                trans_dur = _get_audio_duration_seconds(trans_file)
                if limit_trans is not None and limit_trans > 0:
                    trans_dur = min(trans_dur, limit_trans)
                if args.speed != 1.0 and trans_dur > 0:
                    trans_dur = trans_dur / args.speed
                if trans_dur <= 0:
                    trans_dur = 1.0
                make_segment("t", trans_audio, trans_dur)
                tot_ffmpeg += t_ffmpeg_ayah[0]

        t_ayah = time.perf_counter() - t_ayah_start
        print("  [%d/%d] Sura %d, Ayah %d   api=%.2fs  render=%.2fs  download=%.2fs  ffmpeg=%.2fs  total=%.2fs" % (
            idx, len(verses), surah, ayah, t_api, t_render, t_download, t_ffmpeg_ayah[0], t_ayah))

        try:
            os.remove(temp_img)
        except OSError:
            pass

    if t_bg_extract > 0 or tot_api > 0 or tot_render > 0 or tot_download > 0 or tot_ffmpeg > 0:
        print("  --- Step totals: api=%.1fs  render=%.1fs  download=%.1fs  ffmpeg=%.1fs  (bg_extract=%.1fs)" % (
            tot_api, tot_render, tot_download, tot_ffmpeg, t_bg_extract))
    return segments


def run_juz(args: argparse.Namespace) -> None:
    """Create juz-by-juz Persian recitation movie (ayah-by-ayah). Expects args from parse_juz_args() or compat."""
    # Debug overrides
    if getattr(args, "debug_no_background", False):
        args.background_video = ""

    if not (1 <= args.juz_number <= 30):
        print("Error: juz_number must be 1–30.", file=sys.stderr)
        sys.exit(1)

    # Normalize template: support {sura:03d} style by replacing with {sura} and formatting ourselves
    if "{sura:03d}" in args.recitation_template or "{ayah:03d}" in args.recitation_template:
        args.recitation_template = args.recitation_template.replace("{sura:03d}", "{sura}").replace("{ayah:03d}", "{ayah}")

    debug_pages_arg = getattr(args, "debug_pages", None)
    if debug_pages_arg:
        debug_pages = [int(x.strip()) for x in str(debug_pages_arg).split(",") if x.strip()]
        verses = []
        for p in debug_pages:
            verses.extend(fetch_verses_by_page(p))
        print("Debug mode: pages %s — %d ayahs." % (debug_pages, len(verses)))
    elif args.debug:
        verses = [(2, 282)]
        print("Debug mode: single ayah only — Sura 2, Ayah 282.")
    else:
        print("Juz %d: fetching verse list..." % args.juz_number)
        verses = fetch_juz_verses(args.juz_number)
        print("Juz %d: %d ayahs." % (args.juz_number, len(verses)))
        # Debug: limit to begin_page or limit_ayahs
        begin_page = getattr(args, "debug_begin_page", None)
        if begin_page is not None:
            verses = [(s, a) for s, a in verses if fetch_ayah_words(s, a)[1] >= begin_page]
            print("  After debug_begin_page=%d: %d ayahs." % (begin_page, len(verses)))
        limit = getattr(args, "debug_limit_ayahs", None)
        if limit is not None and len(verses) > limit:
            verses = verses[: limit]
            print("  After debug_limit_ayahs=%d: %d ayahs." % (limit, len(verses)))
    if not verses:
        print("No verses to process.", file=sys.stderr)
        sys.exit(1)

    segments = []
    build_ayah_segments(args.juz_number, verses, args, segments)

    if not segments:
        print("No segments produced.", file=sys.stderr)
        sys.exit(1)

    # Concat: list file must be in the same directory as segment files so the demuxer finds them (relative paths).
    def run_concat(list_path: str, output_path: str) -> None:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path],
            check=True,
            capture_output=True,
            timeout=3600,
        )

    print("  [concat] %d segments:" % len(segments))
    total_seg_dur = 0.0
    for i, s in enumerate(segments):
        d = _get_video_duration_seconds(s)
        total_seg_dur += d
        print("    [%d] %s dur=%.2f s" % (i, os.path.basename(s), d))
    print("  [concat] total_segments_duration=%.2f s" % total_seg_dur)

    concat_ok = False
    list_dir = os.path.dirname(os.path.abspath(segments[0])) if segments else tempfile.gettempdir()
    fd, list_path = tempfile.mkstemp(suffix=".concat_list.txt", prefix="juz_concat_", dir=list_dir)
    os.close(fd)
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for s in segments:
                abs_s = os.path.abspath(s)
                if os.path.dirname(abs_s) == list_dir:
                    entry = os.path.basename(abs_s)
                else:
                    entry = abs_s
                f.write("file '%s'\n" % entry.replace("'", "'\\''"))
        run_concat(list_path, args.output_path)
        concat_ok = True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        print("FFmpeg concat failed. stderr:", file=sys.stderr)
        print(err[-4000:] if len(err) > 4000 else err, file=sys.stderr)
        raise RuntimeError("FFmpeg concat failed. Run: ffmpeg -y -f concat -safe 0 -i %s -c copy %s" % (list_path, args.output_path)) from e
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found in PATH") from None
    finally:
        if concat_ok:
            try:
                os.remove(list_path)
            except OSError:
                pass
            for s in segments:
                try:
                    os.remove(s)
                except OSError:
                    pass
        else:
            print("Segment files left in place. To retry concat: ffmpeg -y -f concat -safe 0 -i %s -c copy %s" % (list_path, args.output_path), file=sys.stderr)

    out_dur = _get_video_duration_seconds(args.output_path) if concat_ok and os.path.isfile(args.output_path) else 0.0
    print("Wrote %s [concat] output_duration=%.2f s" % (args.output_path, out_dur))


def parse_juz_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Create juz-by-juz Persian recitation movie (Arabic + Persian translation on screen).",
    )
    ap.add_argument("juz_number", type=int, help="Juz number (1-30).")
    ap.add_argument("output_path", help="Output MP4 path.")
    ap.add_argument("--translation_root", default="data/persian-recitation", help="Root for sura_N/translation_text and translation_audio.")
    ap.add_argument("--fps", type=int, default=30, help="Output FPS.")
    ap.add_argument("--background_video", default="", help="Background video path (optional).")
    ap.add_argument("--bg_clip_start", type=float, default=0.0, help="Start time (seconds) in background video. If segments are short or empty, the file may have a keyframe boundary at this time; try 0 or another value.")
    ap.add_argument("--speed", type=float, default=1.0, help="Playback speed (1.0 = normal; 2.0 = 2x). At 1.0 no atempo is applied.")
    ap.add_argument("--include_translation_audio", action="store_true", help="Append translation voice from translation_audio/{ayah}.mp3 when present.")
    ap.add_argument(
        "--recitation_template",
        default="https://tanzil.net/res/audio/parhizgar/{sura}{ayah}.mp3",
        help="URL template for recitation; use {sura} and {ayah} as 3-digit placeholders (e.g. 001 001).",
    )
    ap.add_argument("--font", default="quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf", help="Arabic font path; {h_page} for page number.")
    ap.add_argument("--font_size", type=int, default=100)
    ap.add_argument("--title_font", default="quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf",
        help="Font for sura label (e.g. '001 surah') shown per ayah; changes with each sura in the juz.")
    ap.add_argument("--title_font_size", type=int, default=100)
    ap.add_argument("--translation_font", default="font/HM_XNiloofar.ttf")
    ap.add_argument("--translation_font_size", type=int, default=48)
    ap.add_argument("--show_page", action="store_true", default=True, help="Show page number (top-left).")
    ap.add_argument("--show_juz", action="store_true", default=False, help="Show juz number (top center).")
    ap.add_argument("--size_x", type=int, default=1920)
    ap.add_argument("--size_y", type=int, default=1080)
    ap.add_argument("--margin_h", type=int, default=200)
    ap.add_argument("--margin_v", type=int, default=20)
    ap.add_argument("--interline", type=int, default=30)
    ap.add_argument("--stroke_width", type=int, default=5)
    ap.add_argument("--reciter_name", default="", help="Reciter name shown on juz intro page (e.g. طنزیل پرہیزگار).")
    ap.add_argument("--first_page", default="", help="Custom intro template: use {JOZ} for juz number, {SURELIST} for sura names (first 10 then ... and count). Newlines as \\n.")
    ap.add_argument("--debug", action="store_true", help="Run for a single ayah only: Sura 2, Ayah 282 (for debugging layout/wrap). Intro page included.")
    ap.add_argument("--debug_no_background", action="store_true", help="Use black background (no video file).")
    ap.add_argument("--debug_begin_page", type=int, default=None, metavar="N", help="Only ayahs on pages >= N (debug).")
    ap.add_argument("--debug_limit_ayahs", type=int, default=None, metavar="N", help="Process only first N ayahs (debug).")
    ap.add_argument("--debug_limit_recitation_sec", type=float, default=None, metavar="SEC", help="Trim recitation audio to SEC seconds per ayah (debug).")
    ap.add_argument("--debug_limit_translation_sec", type=float, default=None, metavar="SEC", help="Trim translation audio to SEC seconds per ayah (debug).")
    return ap.parse_args()


def main() -> None:
    args = parse_juz_args()
    run_juz(args)


if __name__ == "__main__":
    main()
