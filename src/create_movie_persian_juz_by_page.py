#!/usr/bin/env python3
"""
Create a Persian recitation movie PAGE-BY-PAGE (juz style).

For each page: show the full page (all ayahs), highlight the ayah being recited,
and show only that ayah's translation below. Same wrapping and font-size fit as
create_movie_persian_juz.py. Per page: one main Arabic font size (all ayahs),
one translation font size (based on longest translation on the page).

Usage:
  python3 src/create_movie_persian_juz_by_page.py JUZ_NUMBER OUTPUT.mp4 [options]
  python3 src/create_movie_persian_juz_by_page.py 10 out/debug_pages.mp4 --debug --debug_5_sec  # pages 1, 2, 182, 48; 5 sec per ayah
"""

import argparse
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass

# Reuse ffmpeg loader and helpers from the ayah-by-ayah juz script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from create_movie_persian_juz import (
    _download_recitation_to_cache,
    _is_valid_video_file,
    create_juz_intro_image,
    fetch_ayah_words,
    fetch_besmellah_no_verse_number,
    format_juz_sura_list,
    recitation_url_for_ayah,
    to_persian_numerals,
)

import requests
from PIL import Image, ImageDraw, ImageFont

import ffmpeg


def _space_from_ayah_text(arabic_text: str) -> str:
    """Find the first run of space/separator characters in ayah text (same font as page). Use between ayahs."""
    if not arabic_text:
        return " "
    i = 0
    n = len(arabic_text)
    while i < n and not arabic_text[i].isspace():
        i += 1
    if i >= n:
        return " "
    start = i
    while i < n and arabic_text[i].isspace():
        i += 1
    return arabic_text[start:i] if start < i else " "


def fetch_verses_by_page(page_number: int) -> list[tuple[int, int]]:
    """Return list of (surah, ayah) for the given Quran page (1-604)."""
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


def fetch_juz_for_page(page_number: int) -> int:
    """Return juz number (1–30) for the given Quran page. Uses API verses by_page first verse."""
    r = requests.get(
        "https://api.quran.com/api/v4/verses/by_page/%d" % page_number,
        params={"per_page": 1, "page": 1},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    verses = data.get("verses") or []
    if verses:
        juz = verses[0].get("juz_number")
        if juz is not None:
            return int(juz)
    return 1


def fetch_juz_verses_with_pages(juz_number: int) -> list[tuple[int, int, int]]:
    """Return list of (surah, ayah, page_number) for the juz. API allows max 50 per page."""
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
            pg = v.get("page_number") or 1
            m = re.match(r"^(\d+):(\d+)$", key)
            if m:
                out.append((int(m.group(1)), int(m.group(2)), pg))
        if len(verses) < per_page:
            break
        pagination = data.get("pagination") or {}
        next_page = pagination.get("next_page")
        if next_page is None or next_page == page:
            break
        page = next_page
    return out


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
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


def _words_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Return [(word, start, end), ...] for each word in text (by whitespace)."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        start = i
        while i < n and not text[i].isspace():
            i += 1
        out.append((text[start:i], start, i))
    return out


def _wrap_text_with_spans(
    draw: ImageDraw.ImageDraw,
    full_text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[tuple[str, int, int]]:
    """Wrap full_text; return [(line_str, start_char, end_char), ...] for mapping to ayah boundaries."""
    words_with_pos = _words_with_spans(full_text)
    if not words_with_pos:
        return []
    lines_with_spans = []
    current_str = ""
    line_start = line_end = 0
    for w, s, e in words_with_pos:
        test = (current_str + " " + w).strip() if current_str else w
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current_str = test
            line_end = e
        else:
            if current_str:
                lines_with_spans.append((current_str, line_start, line_end))
            current_str = w
            line_start, line_end = s, e
    if current_str:
        lines_with_spans.append((current_str, line_start, line_end))
    return lines_with_spans


def _split_line_by_ayah(
    line: str, line_start: int, line_end: int,
    ayah_boundaries: list[tuple[int, int]],
    highlight_index: int,
    normal_color: str,
    highlight_color: str,
) -> list[tuple[str, str, int]]:
    """Split a line into segments (substring, color, boundary_index) by ayah boundaries overlapping [line_start, line_end)."""
    segments = []
    for i, (ah_start, ah_end) in enumerate(ayah_boundaries):
        seg_start = max(line_start, ah_start)
        seg_end = min(line_end, ah_end)
        if seg_start >= seg_end:
            continue
        sub = line[seg_start - line_start : seg_end - line_start]
        if not sub.strip():
            continue
        color = highlight_color if i == highlight_index else normal_color
        segments.append((sub, color, i))
    if not segments:
        segments = [(line, normal_color, 0)]
    return segments


def create_page_frame(
    size: tuple[int, int],
    margin_h: int,
    margin_v: int,
    interline: int,
    page_number: int,
    main_flow_lines: list[list[tuple[str, str, int]]],  # per line: [(segment_text, color, boundary_index), ...]
    line_ends_ayah: list[bool],  # True if this line ends at an ayah boundary (extra gap after)
    main_font: ImageFont.FreeTypeFont,
    ayah_entries: list[tuple[str, str, str, int]],  # for translation only: (_, _, trans_text, surah)
    highlight_index: int,
    trans_font_size: int,
    trans_font_path: str,
    title_font_path: str,
    title_font_size: int,
    sura_label: str,
    juz_number: int,
    max_trans_h: float,  # max vertical space for translation block (from fit loop)
    stroke_width: int,
    stroke_color: str,
    filename: str,
    bismillah_font: ImageFont.FreeTypeFont | None = None,  # font for boundary_index 0 (1:1 page font)
    top_left_marker: str | None = None,
) -> None:
    """Draw one frame: juz (top center), page (left), sura (right), main text, then current ayah's translation."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    max_width = size[0] - 2 * margin_h
    min_top = margin_v
    center_x = size[0] // 2

    # Juz number top center (e.g. "جزء ۲")
    juz_label = "جزء " + to_persian_numerals(juz_number)
    juz_font = ImageFont.truetype(trans_font_path, max(8, title_font_size // 3))
    draw.text(
        (center_x, margin_v),
        juz_label,
        font=juz_font,
        fill=(255, 255, 255),
        stroke_fill=stroke_color,
        stroke_width=stroke_width,
        anchor="ma",
    )
    juz_h = draw.textbbox((0, 0), juz_label, font=juz_font)[3]
    min_top = margin_v + juz_h

    # Page label (left) and sura label (right, in sura-names font)
    page_label = "صفحه " + to_persian_numerals(page_number)
    page_label_font = ImageFont.truetype(trans_font_path, max(8, title_font_size // 3))
    draw.text(
        (margin_h, margin_v),
        page_label,
        font=page_label_font,
        fill=(255, 255, 255),
        stroke_fill=stroke_color,
        stroke_width=stroke_width,
        anchor="la",
    )
    min_top = max(min_top, margin_v + draw.textbbox((0, 0), page_label, font=page_label_font)[3])
    if top_left_marker:
        marker_font = ImageFont.truetype(trans_font_path, max(8, title_font_size // 3))
        page_box = draw.textbbox((0, 0), page_label, font=page_label_font)
        marker_x = margin_h + page_box[2] + max(12, interline // 2)
        draw.text(
            (marker_x, margin_v),
            top_left_marker,
            font=marker_font,
            fill=(255, 255, 255),
            stroke_fill=stroke_color,
            stroke_width=stroke_width,
            anchor="la",
        )
        min_top = max(min_top, margin_v + draw.textbbox((0, 0), top_left_marker, font=marker_font)[3])

    if sura_label:
        sura_font = ImageFont.truetype(title_font_path, title_font_size)
        draw.text(
            (size[0] - margin_h, margin_v),
            sura_label,
            font=sura_font,
            fill=(255, 255, 255),
            stroke_fill=stroke_color,
            stroke_width=stroke_width,
            anchor="ra",
        )
        sura_h = draw.textbbox((0, 0), sura_label, font=sura_font)[3]
        min_top = max(min_top, margin_v + sura_h)

    min_top += interline

    def _font_for_seg(seg: tuple[str, str, int]) -> ImageFont.FreeTypeFont:
        _, _, bi = seg
        return bismillah_font if (bi == 0 and bismillah_font is not None) else main_font

    main_heights = []
    for line_segments in main_flow_lines:
        line_h = max(draw.textbbox((0, 0), s[0], font=_font_for_seg(s))[3] for s in line_segments)
        main_heights.append(line_h)

    trans_text = ayah_entries[highlight_index][2]
    trans_font = ImageFont.truetype(trans_font_path, trans_font_size)
    trans_lines = _wrap_text(draw, trans_text, trans_font, max_width) if trans_text.strip() else []
    trans_heights = [draw.textbbox((0, 0), ln, font=trans_font)[3] for ln in trans_lines]

    y_cur = min_top
    for i, (line_segments, lh) in enumerate(zip(main_flow_lines, main_heights)):
        total_line_w = sum(draw.textbbox((0, 0), s[0], font=_font_for_seg(s))[2] for s in line_segments)
        x_cur = center_x + total_line_w // 2
        for seg_text, color, boundary_index in line_segments:
            seg_font = _font_for_seg((seg_text, color, boundary_index))
            seg_w = draw.textbbox((0, 0), seg_text, font=seg_font)[2]
            x_cur -= seg_w
            draw.text(
                (x_cur + seg_w // 2, y_cur + lh // 2),
                seg_text,
                font=seg_font,
                fill=color,
                stroke_fill=stroke_color,
                stroke_width=stroke_width,
                anchor="mm",
            )
        y_cur += lh + interline
        if i < len(line_ends_ayah) and line_ends_ayah[i]:
            y_cur += interline  # extra gap between ayahs when line ends at ayah boundary

    y_cur += interline
    # Only draw as many translation lines as fit in max_trans_h (stay on page)
    trans_space = min(max_trans_h, size[1] - margin_v - y_cur)
    used_trans_h = 0
    for i, line in enumerate(trans_lines):
        lh = trans_heights[i]
        line_and_gap = lh + interline
        if used_trans_h + lh > trans_space:
            break
        draw.text(
            (center_x, y_cur + lh // 2),
            line,
            font=trans_font,
            fill=(255, 255, 255),
            stroke_fill=stroke_color,
            stroke_width=stroke_width,
            anchor="mm",
        )
        y_cur += line_and_gap
        used_trans_h += line_and_gap

    img.save(filename, format="PNG")


def _get_audio_duration_seconds(audio_path: str) -> float:
    """Return duration in seconds of an audio file (e.g. MP3) via ffprobe."""
    import subprocess
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


def build_page_segments(
    pages_data: list[tuple[int, list[tuple[int, int]]]],  # [(page_num, [(surah, ayah), ...]), ...]
    args: argparse.Namespace,
    segments: list[str],
    repo_root: str,
    recitation_cache_dir: str,
    bg_video_path: str,
    bg_clip_start_ref: list[float],  # [current position]; updated after each segment
) -> None:
    """For each page: flow layout (ayahs after each other), then for each ayah on page create segment (full recitation).
    When a page contains the start of a sura (ayah 1, except suras 1 and 9), bismillah is shown on the page (via fetch_besmellah_no_verse_number for correct font/glyphs).
    Recitation files for the first ayah of a sura already include bismillah; we only add bismillah text on the page. Intro plays only first 3 s of 1:1 (auzobellah)."""
    max_width = args.size_x - 2 * args.margin_h
    trans_font_path = args.translation_font
    if not os.path.isabs(trans_font_path):
        trans_font_path = os.path.join(repo_root, trans_font_path)
    title_font_path = args.title_font
    if not os.path.isabs(title_font_path):
        title_font_path = os.path.join(repo_root, title_font_path)

    besm_text, besm_page = fetch_besmellah_no_verse_number()

    for page_number, page_verses in pages_data:
        if not page_verses:
            continue
        juz_for_page = fetch_juz_for_page(page_number)
        # Load Arabic and translation for all ayahs on the page
        ayah_data = []
        for surah, ayah in page_verses:
            arabic_text, _ = fetch_ayah_words(surah, ayah)
            main_font_path = args.font.format(h_page=_)
            if not os.path.isabs(main_font_path):
                main_font_path = os.path.join(repo_root, main_font_path)
            trans_path = os.path.join(
                args.translation_root, "sura_%d" % surah, "translation_text", "%d.txt" % ayah
            )
            trans_text = ""
            if os.path.isfile(trans_path):
                with open(trans_path, "r", encoding="utf-8") as f:
                    trans_text = f.read().strip()
            ayah_data.append((arabic_text, main_font_path, trans_text, surah))

        # Full page text: prepend bismillah (no verse number) before first ayah of suras 2–8, 10–114
        sep = " "
        texts = []
        for i, (surah, ayah) in enumerate(page_verses):
            arabic_text = ayah_data[i][0]
            if ayah == 1 and surah not in (1, 9) and besm_text:
                texts.append(besm_text + sep + arabic_text)
            else:
                texts.append(arabic_text)
        full_text = sep.join(texts)
        leading_bismillah = bool(besm_text and page_verses and page_verses[0][1] == 1 and page_verses[0][0] not in (1, 9))
        pos = 0
        ayah_boundaries = []
        if leading_bismillah:
            ayah_boundaries.append((0, len(besm_text)))
            ayah_boundaries.append((len(besm_text) + len(sep), len(besm_text) + len(sep) + len(ayah_data[0][0])))
            pos = len(texts[0]) + len(sep)
            for i in range(1, len(texts)):
                start = pos
                pos += len(texts[i])
                ayah_boundaries.append((start, pos))
                if i < len(texts) - 1:
                    pos += len(sep)
        else:
            for t in texts:
                start = pos
                pos += len(t)
                ayah_boundaries.append((start, pos))
                if pos < len(full_text):
                    pos += len(sep)

        # Fit: use actual header height so main + translation stay within page
        page_font_path = ayah_data[0][1]
        img_tmp = Image.new("RGBA", (args.size_x, args.size_y), (0, 0, 0, 0))
        draw_tmp = ImageDraw.Draw(img_tmp)
        page_label_font_tmp = ImageFont.truetype(trans_font_path, max(8, args.title_font_size // 3))
        juz_font_tmp = ImageFont.truetype(trans_font_path, max(8, args.title_font_size // 2))
        sura_font_tmp = ImageFont.truetype(title_font_path, args.title_font_size)
        page_label = "صفحه " + to_persian_numerals(page_number)
        juz_label = "جزء " + to_persian_numerals(juz_for_page)
        sura_sample = "042 surah"
        header_h = args.margin_v + max(
            draw_tmp.textbbox((0, 0), page_label, font=page_label_font_tmp)[3],
            draw_tmp.textbbox((0, 0), juz_label, font=juz_font_tmp)[3],
            draw_tmp.textbbox((0, 0), sura_sample, font=sura_font_tmp)[3],
        ) + args.interline
        available_h = args.size_y - header_h - args.margin_v

        main_font_size_base = args.font_size
        trans_font_size_base = args.translation_font_size
        inter_base = args.interline
        min_scale = max(8 / main_font_size_base, 8 / trans_font_size_base, 0.01)
        lo, hi = min_scale, 1.0
        for _ in range(50):
            scale = (lo + hi) / 2
            main_font_size = max(8, int(main_font_size_base * scale))
            trans_font_size = max(8, int(trans_font_size_base * scale))
            # Scale line spacing with fonts; scale a bit more so smaller fonts get tighter spacing
            inter = max(2, int(inter_base * scale * scale))
            main_font = ImageFont.truetype(page_font_path, main_font_size)
            lines_with_spans = _wrap_text_with_spans(draw_tmp, full_text, main_font, max_width)
            ayah_ends = {b[1] for b in ayah_boundaries}
            line_ends_ayah = [line_end in ayah_ends for (_, _, line_end) in lines_with_spans]
            total_main_h = 0
            for line_str, _, _ in lines_with_spans:
                total_main_h += draw_tmp.textbbox((0, 0), line_str, font=main_font)[3]
            total_main_h += (len(lines_with_spans) - 1) * inter if lines_with_spans else 0
            total_main_h += sum(inter for e in line_ends_ayah if e)  # extra gap after lines that end an ayah

            trans_font = ImageFont.truetype(trans_font_path, trans_font_size)
            max_trans_lines = 0
            max_trans_line_h = 0
            for _, _, trans_text, _ in ayah_data:
                if trans_text.strip():
                    trans_lines = _wrap_text(draw_tmp, trans_text, trans_font, max_width)
                    max_trans_lines = max(max_trans_lines, len(trans_lines))
                    for ln in trans_lines:
                        max_trans_line_h = max(max_trans_line_h, draw_tmp.textbbox((0, 0), ln, font=trans_font)[3])
            total_trans_h = max_trans_lines * (max_trans_line_h + inter) - (inter if max_trans_lines else 0)

            if total_main_h + inter + total_trans_h <= available_h:
                lo = scale
            else:
                hi = scale
            if hi - lo < 0.005:
                break
        scale = lo
        main_font_size = max(8, int(main_font_size_base * scale))
        trans_font_size = max(8, int(trans_font_size_base * scale))
        inter = max(2, int(inter_base * scale * scale))  # line spacing scaled with fonts (tighter when font smaller)

        main_font = ImageFont.truetype(page_font_path, main_font_size)
        lines_with_spans = _wrap_text_with_spans(draw_tmp, full_text, main_font, max_width)
        ayah_ends = {b[1] for b in ayah_boundaries}
        line_ends_ayah = [line_end in ayah_ends for (_, _, line_end) in lines_with_spans]

        # Max height reserved for translation block (same for all ayahs on this page)
        trans_font_final = ImageFont.truetype(trans_font_path, trans_font_size)
        max_trans_lines_final = 0
        max_trans_line_h_final = 0
        for _, _, trans_text, _ in ayah_data:
            if trans_text.strip():
                tl = _wrap_text(draw_tmp, trans_text, trans_font_final, max_width)
                max_trans_lines_final = max(max_trans_lines_final, len(tl))
                for ln in tl:
                    max_trans_line_h_final = max(max_trans_line_h_final, draw_tmp.textbbox((0, 0), ln, font=trans_font_final)[3])
        max_trans_h = max_trans_lines_final * (max_trans_line_h_final + inter) - (inter if max_trans_lines_final else 0)

        # Bismillah text uses quran.com font of 1:1 (page besm_page)
        bismillah_font = None
        if leading_bismillah:
            bismillah_font_path = args.font.format(h_page=besm_page)
            if not os.path.isabs(bismillah_font_path):
                bismillah_font_path = os.path.join(repo_root, bismillah_font_path)
            if os.path.isfile(bismillah_font_path):
                bismillah_font = ImageFont.truetype(bismillah_font_path, main_font_size)

        # Create one segment per ayah on the page
        for idx, (surah, ayah) in enumerate(page_verses):
            boundary_highlight = idx + (1 if leading_bismillah else 0)  # highlight first ayah, not bismillah
            main_flow_lines = []
            for line_str, line_start, line_end in lines_with_spans:
                segs = _split_line_by_ayah(
                    line_str, line_start, line_end,
                    ayah_boundaries, boundary_highlight,
                    "white", args.highlight_color,
                )
                main_flow_lines.append(segs)

            fd, temp_img = tempfile.mkstemp(suffix=".png", prefix="juz_page_")
            os.close(fd)
            create_page_frame(
                size=(args.size_x, args.size_y),
                margin_h=args.margin_h,
                margin_v=args.margin_v,
                interline=inter,
                page_number=page_number,
                main_flow_lines=main_flow_lines,
                line_ends_ayah=line_ends_ayah,
                main_font=main_font,
                ayah_entries=ayah_data,
                highlight_index=idx,
                trans_font_size=trans_font_size,
                trans_font_path=trans_font_path,
                title_font_path=title_font_path,
                title_font_size=args.title_font_size,
                sura_label="%03d surah" % surah,
                juz_number=juz_for_page,
                max_trans_h=max_trans_h,
                stroke_width=args.stroke_width,
                stroke_color="black",
                filename=temp_img,
                bismillah_font=bismillah_font,
            )

            rec_url = recitation_url_for_ayah(args.recitation_template, surah, ayah)
            rec_local = os.path.join(recitation_cache_dir, "%03d_%03d.mp3" % (surah, ayah))
            if not os.path.isfile(rec_local):
                _download_recitation_to_cache(rec_url, rec_local)
            rec_audio = ffmpeg.input(rec_local).audio
            if abs(args.speed - 1.0) > 1e-6:
                rec_audio = rec_audio.filter("atempo", args.speed)
            limit_rec = getattr(args, "debug_limit_recitation_sec", None)
            if limit_rec is not None and limit_rec > 0:
                rec_audio = rec_audio.filter("atrim", duration=limit_rec).filter("asetpts", "PTS-STARTPTS")

            # Recitation files for first ayah of a sura already include bismillah; we only add bismillah text on the page.
            if getattr(args, "debug_5_sec", False):
                audio_dur = 5.0
                rec_audio = rec_audio.filter("atrim", duration=5.0)
            else:
                audio_dur = _get_audio_duration_seconds(rec_local)
                if args.speed != 1.0 and audio_dur > 0:
                    audio_dur = audio_dur / args.speed
                if audio_dur <= 0:
                    audio_dur = 1.0

            seg_path = temp_img.replace(".png", "_%d_%d_%d.mp4" % (page_number, surah, ayah))
            bg_start = bg_clip_start_ref[0]
            if bg_video_path and os.path.isfile(bg_video_path):
                video_stream = ffmpeg.input(bg_video_path, ss=bg_start, t=audio_dur).video
            else:
                video_stream = ffmpeg.input(
                    "color=c=black:s=%dx%d:d=%.2f" % (args.size_x, args.size_y, audio_dur), f="lavfi"
                ).video
            video_stream = video_stream.filter("scale", args.size_x, args.size_y)
            img_in = ffmpeg.input(temp_img).video
            video_stream = ffmpeg.overlay(
                video_stream, img_in, x="(main_w-overlay_w)/2", y="(main_h-overlay_h)/2"
            )
            out = ffmpeg.output(
                video_stream, rec_audio, seg_path,
                vcodec="libx264", acodec="aac", r=args.fps, pix_fmt="yuv420p", shortest=None
            )
            bg_clip_start_ref[0] = bg_start + audio_dur
            out = out.overwrite_output()
            try:
                out.run(quiet=True)
            except ffmpeg.Error as e:
                err = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or str(e))
                raise RuntimeError("FFmpeg failed for segment %s: %s" % (seg_path, err)) from e
            segments.append(seg_path)
            try:
                os.remove(temp_img)
            except OSError:
                pass

            print("  Page %d  Sura %d, Ayah %d" % (page_number, surah, ayah))


def run_juz_by_page(args: argparse.Namespace) -> None:
    """Create juz movie page-by-page (full page, highlight current ayah). Expects args from parse_juz_by_page_args() or compat."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if getattr(args, "debug_no_background", False):
        args.background_video = ""

    if "{sura:03d}" in args.recitation_template or "{ayah:03d}" in args.recitation_template:
        args.recitation_template = args.recitation_template.replace("{sura:03d}", "{sura}").replace("{ayah:03d}", "{ayah}")

    debug_pages_arg = getattr(args, "debug_pages", None)
    if args.debug or debug_pages_arg:
        debug_pages = [1]
        if debug_pages_arg:
            debug_pages = [int(x.strip()) for x in str(debug_pages_arg).split(",") if x.strip()]
        debug_5_sec = getattr(args, "debug_5_sec", False)
        print("Debug mode: pages %s%s." % (debug_pages, "; 5 sec per ayah" if debug_5_sec else ""))
        pages_data = []
        for p in debug_pages:
            verses = fetch_verses_by_page(p)
            if verses:
                pages_data.append((p, verses))
                print("  Page %d: %d ayahs" % (p, len(verses)))
    else:
        print("Juz %d: fetching verses with page numbers..." % args.juz_number)
        juz_verses = fetch_juz_verses_with_pages(args.juz_number)
        from collections import OrderedDict
        by_page = OrderedDict()
        for surah, ayah, pg in juz_verses:
            by_page.setdefault(pg, []).append((surah, ayah))
        pages_data = [(pg, list(v)) for pg, v in by_page.items()]
        if getattr(args, "debug_begin_page", None) is not None:
            begin = args.debug_begin_page
            pages_data = [(p, v) for p, v in pages_data if p >= begin]
            print("  After debug_begin_page=%d: %d pages." % (begin, len(pages_data)))
        limit = getattr(args, "debug_limit_ayahs", None)
        if limit is not None and limit > 0:
            out = []
            n = 0
            for p, verses in pages_data:
                if n >= limit:
                    break
                take = verses[: limit - n]
                n += len(take)
                out.append((p, take))
            pages_data = out
            print("  After debug_limit_ayahs=%d: %d pages." % (limit, len(pages_data)))
        print("  %d pages." % len(pages_data))

    if not pages_data:
        print("No pages to process.", file=sys.stderr)
        sys.exit(1)

    recitation_cache_dir = os.path.join(tempfile.gettempdir(), "juz_recitation_cache", "juz%d" % args.juz_number)
    os.makedirs(recitation_cache_dir, exist_ok=True)

    bg_video_path = args.background_video
    bg_clip_start = args.bg_clip_start
    if args.background_video and os.path.isfile(args.background_video):
        safe_name = os.path.basename(args.background_video).replace(" ", "_")[:80]
        clip_path = os.path.join(tempfile.gettempdir(), "juz_page_bg_clip_%s.mp4" % safe_name)
        if not os.path.isfile(clip_path):
            try:
                inp = ffmpeg.input(args.background_video, ss=args.bg_clip_start, t=7200)
                out = ffmpeg.output(inp, clip_path, c="copy")
                out = out.overwrite_output()
                out.run(quiet=True)
                if _is_valid_video_file(clip_path):
                    bg_video_path = clip_path
                    bg_clip_start = 0.0
                else:
                    try:
                        os.remove(clip_path)
                    except OSError:
                        pass
            except Exception:
                pass
        elif os.path.isfile(clip_path) and _is_valid_video_file(clip_path):
            bg_video_path = clip_path
            bg_clip_start = 0.0
        elif os.path.isfile(clip_path):
            print("  Warning: cached clip invalid (corrupt?), using original background video.")
            try:
                os.remove(clip_path)
            except OSError:
                pass

    segments = []
    bg_clip_start_ref = [bg_clip_start]  # mutable so each segment advances for next page

    # Juz intro page: juz/reciter/pages or custom --first_page. Audio = first 3 s of 1:1 (auzobellah); bismillah is played on the next (content) page when it starts a sura.
    page_start = pages_data[0][0]
    page_end = pages_data[-1][0]
    juz_for_intro = args.juz_number if not (args.debug or getattr(args, "debug_pages", None)) else fetch_juz_for_page(page_start)
    reciter_name = getattr(args, "reciter_name", "") or ""
    verses_for_list = [(s, a) for _pn, pv in pages_data for s, a in pv]
    first_page_template = getattr(args, "first_page", "") or ""
    custom_intro_text = None
    if first_page_template.strip():
        sura_list_str = format_juz_sura_list(verses_for_list, max_names=10)
        custom_intro_text = (
            first_page_template.replace("{JOZ}", to_persian_numerals(juz_for_intro))
            .replace("{SURELIST}", sura_list_str)
        )
    fd_intro, intro_img_path = tempfile.mkstemp(suffix=".png", prefix="juz_intro_")
    os.close(fd_intro)
    try:
        create_juz_intro_image(juz_for_intro, reciter_name, page_start, page_end, args, repo_root, intro_img_path, custom_text=custom_intro_text)
    except Exception:
        os.remove(intro_img_path)
        raise
    # Intro audio: always auzobellah (first 3 s of 1:1). Then bismillah (rest of 1:1) only if the next page is NOT the start of a sura (so bismillah is not played on that page). Unless --full_bismillah_intro.
    first_content_page_verses = pages_data[0][1]
    next_page_starts_sura = bool(first_content_page_verses and first_content_page_verses[0][1] == 1)
    full_bismillah = getattr(args, "full_bismillah_intro", False)
    intro_audio_local = os.path.join(recitation_cache_dir, "001_001.mp3")
    if not os.path.isfile(intro_audio_local):
        _download_recitation_to_cache(recitation_url_for_ayah(args.recitation_template, 1, 1), intro_audio_local)
    # Compute intro duration so we can trim video to match (avoids shortest=1 which ffmpeg-python misparses)
    if next_page_starts_sura and not full_bismillah:
        intro_dur = min(3.0, _get_audio_duration_seconds(intro_audio_local))
    else:
        intro_dur = _get_audio_duration_seconds(intro_audio_local)
    if args.speed != 1.0 and intro_dur > 0:
        intro_dur = intro_dur / args.speed
    intro_audio = ffmpeg.input(intro_audio_local).audio
    if next_page_starts_sura and not full_bismillah:
        intro_audio = intro_audio.filter("atrim", duration=3.0).filter("asetpts", "PTS-STARTPTS")
    if abs(args.speed - 1.0) > 1e-6:
        intro_audio = intro_audio.filter("atempo", args.speed)
    intro_seg_path = intro_img_path.replace(".png", "_intro.mp4")
    if bg_video_path and os.path.isfile(bg_video_path):
        intro_video = ffmpeg.input(bg_video_path, ss=bg_clip_start_ref[0], t=intro_dur).video
    else:
        intro_video = ffmpeg.input("color=c=black:s=%dx%d:d=%.2f" % (args.size_x, args.size_y, intro_dur), f="lavfi").video
    intro_video = intro_video.filter("scale", args.size_x, args.size_y)
    intro_img_in = ffmpeg.input(intro_img_path).video
    intro_video = ffmpeg.overlay(intro_video, intro_img_in, x="(main_w-overlay_w)/2", y="(main_h-overlay_h)/2")
    out = ffmpeg.output(intro_video, intro_audio, intro_seg_path, vcodec="libx264", acodec="aac", r=args.fps, pix_fmt="yuv420p", shortest=None)
    out = out.overwrite_output()
    try:
        out.run(quiet=True)
    except ffmpeg.Error as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr or "")
        os.remove(intro_img_path)
        raise RuntimeError("FFmpeg failed for juz intro: %s" % err) from e
    segments.append(intro_seg_path)
    try:
        os.remove(intro_img_path)
    except OSError:
        pass
    bg_clip_start_ref[0] += intro_dur
    print("  [intro] جزء %s — %s — صفحه %s تا %s (%s)" % (
        to_persian_numerals(juz_for_intro), reciter_name or "—", to_persian_numerals(page_start), to_persian_numerals(page_end),
        "auzobellah only (3 s)" if next_page_starts_sura else "auzobellah + bismillah"))

    for page_number, page_verses in pages_data:
        build_page_segments(
            [(page_number, page_verses)],
            args, segments, repo_root, recitation_cache_dir, bg_video_path, bg_clip_start_ref,
        )

    if not segments:
        print("No segments.", file=sys.stderr)
        sys.exit(1)

    list_path = args.output_path + ".concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for s in segments:
            f.write("file '%s'\n" % os.path.abspath(s).replace("'", "'\\''"))
    try:
        inp = ffmpeg.input(list_path, format="concat", safe=0)
        out = ffmpeg.output(inp, args.output_path, c="copy")
        out = out.overwrite_output()
        out.run(quiet=True)
    finally:
        try:
            os.remove(list_path)
        except OSError:
            pass
        for s in segments:
            try:
                os.remove(s)
            except OSError:
                pass
    print("Wrote %s" % args.output_path)


def parse_juz_by_page_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Create juz movie page-by-page (full page, highlight current ayah, translation for current only).")
    ap.add_argument("juz_number", type=int, help="Juz number (1-30). Ignored when --debug or --debug_pages.")
    ap.add_argument("output_path", help="Output MP4 path.")
    ap.add_argument("--translation_root", default="data/persian-recitation")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--background_video", default="")
    ap.add_argument("--bg_clip_start", type=float, default=0.0)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--recitation_template", default="https://tanzil.net/res/audio/parhizgar/{sura}{ayah}.mp3")
    ap.add_argument("--font", default="quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf")
    ap.add_argument("--font_size", type=int, default=100)
    ap.add_argument("--title_font", default="quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf",
                    help="Font for sura label (uses special sura-name glyphs).")
    ap.add_argument("--title_font_size", type=int, default=100)
    ap.add_argument("--translation_font", default="font/HM_XNiloofar.ttf")
    ap.add_argument("--translation_font_size", type=int, default=48)
    ap.add_argument("--size_x", type=int, default=1920)
    ap.add_argument("--size_y", type=int, default=1080)
    ap.add_argument("--margin_h", type=int, default=200)
    ap.add_argument("--margin_v", type=int, default=20)
    ap.add_argument("--interline", type=int, default=30)
    ap.add_argument("--stroke_width", type=int, default=5)
    ap.add_argument("--highlight_color", default="#FFFF00", help="Color for the reciting ayah (e.g. #FFFF00 yellow).")
    ap.add_argument("--reciter_name", default="", help="Reciter name shown on juz intro page (e.g. پرهیزگار).")
    ap.add_argument("--first_page", default="", help="Custom intro template: {JOZ} = juz number, {SURELIST} = sura names (first 10 then ... and count). Newlines as \\n.")
    ap.add_argument("--debug", action="store_true", help="Run for page 1 only (faster preview). Intro page included.")
    ap.add_argument("--debug_5_sec", action="store_true", help="Limit each ayah to 5 seconds. Without this, full recitation is used even in debug mode.")
    ap.add_argument("--debug_no_background", action="store_true", help="Use black background (no video file).")
    ap.add_argument("--debug_pages", default=None, metavar="LIST", help="Comma-separated page numbers to render only (e.g. 1,2,182). Overrides full juz.")
    ap.add_argument("--debug_begin_page", type=int, default=None, metavar="N", help="Only pages >= N (debug).")
    ap.add_argument("--debug_limit_ayahs", type=int, default=None, metavar="N", help="Process only first N ayahs across all pages (debug).")
    ap.add_argument("--debug_limit_recitation_sec", type=float, default=None, metavar="SEC", help="Trim recitation to SEC seconds per ayah (debug).")
    ap.add_argument("--debug_limit_translation_sec", type=float, default=None, metavar="SEC", help="Trim translation audio to SEC seconds (debug).")
    return ap.parse_args()


def main() -> None:
    args = parse_juz_by_page_args()
    run_juz_by_page(args)


if __name__ == "__main__":
    main()
