#!/usr/bin/env python3
"""
Create a Quran recitation movie from one full-surah audio file plus word-level alignment.

This mode reuses the existing ayah-layout renderer from create_movie_persian_juz.py.
Only the timeline generation is new: we derive ayah/word state from quran_aligner output.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass

import ffmpeg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from create_movie_persian_juz import (
    TextInfo,
    _get_audio_duration_seconds,
    _get_video_duration_seconds,
    create_full_text_image_persian,
    fetch_ayah_words,
    fetch_besmellah_no_verse_number,
    to_persian_numerals,
)
from create_movie_persian_juz_by_page import fetch_juz_for_page


@dataclass
class WordRun:
    global_word_index: int
    ayah_number: int
    word_index_in_ayah: int
    start_ms: int
    end_ms: int


@dataclass
class AyahDisplay:
    ayah_number: int
    arabic_text: str
    page_number: int
    translation_text: str


def _read_alignment_debug(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_word_runs(alignment_debug: dict) -> list[WordRun]:
    tokens = alignment_debug.get("tokens") or []
    out: list[WordRun] = []
    for item in alignment_debug.get("result", {}).get("word_runs") or []:
        global_index = int(item["global_word_index"])
        if global_index < 0 or global_index >= len(tokens):
            continue
        token = tokens[global_index]
        out.append(
            WordRun(
                global_word_index=global_index,
                ayah_number=int(token["ayah_number"]),
                word_index_in_ayah=int(token["word_index_in_ayah"]),
                start_ms=int(item["start_ms"]),
                end_ms=int(item["end_ms"]),
            )
        )
    return out


def _load_translation_text(translation_dir: str, ayah_number: int) -> str:
    if ayah_number <= 0:
        return ""
    path = os.path.join(translation_dir, "%d.txt" % ayah_number)
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _build_ayah_displays(args, repo_root: str, ayah_count: int) -> dict[int, AyahDisplay]:
    translation_dir = args.translation_dir or os.path.join(
        repo_root, "data", "persian-recitation", "sura_%d" % args.surah_number, "translation_text"
    )
    out: dict[int, AyahDisplay] = {}
    for ayah in range(1, ayah_count + 1):
        arabic_text, page_number = fetch_ayah_words(args.surah_number, ayah)
        out[ayah] = AyahDisplay(
            ayah_number=ayah,
            arabic_text=arabic_text,
            page_number=page_number,
            translation_text=_load_translation_text(translation_dir, ayah),
        )
    return out


def _timeline_segments(word_runs: list[WordRun], audio_duration_ms: int) -> list[tuple[int, int, WordRun | None]]:
    out: list[tuple[int, int, WordRun | None]] = []
    cursor = 0
    for run in word_runs:
        if run.start_ms > cursor:
            out.append((cursor, run.start_ms, None))
        out.append((run.start_ms, run.end_ms, run))
        cursor = run.end_ms
    if audio_duration_ms > cursor:
        out.append((cursor, audio_duration_ms, None))
    return [item for item in out if item[1] > item[0]]


def _is_valid_video_file(path: str) -> bool:
    return _get_video_duration_seconds(path) > 0


def _display_ayah_number(run: WordRun | None, fallback_ayah: int) -> int:
    if run is None:
        return fallback_ayah
    if run.ayah_number <= 0:
        return fallback_ayah
    return run.ayah_number


def _print_progress(current: int, total: int, label: str) -> None:
    total = max(total, 1)
    width = min(40, max(10, shutil.get_terminal_size((80, 20)).columns - 40))
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    sys.stderr.write("\r[%s] %d/%d %s" % (bar, current, total, label[:60]))
    sys.stderr.flush()
    if current >= total:
        sys.stderr.write("\n")


def _render_ayah_segment(
    display: AyahDisplay,
    active_word_index_in_ayah: int | None,
    is_backtracking: bool,
    args,
    repo_root: str,
    frame_count: int,
    bg_video_path: str,
    bg_clip_start_ref: list[float],
    temp_dir: str,
    besm_text: str,
    besm_font_path: str,
) -> str:
    duration_sec = max(1.0 / args.fps, frame_count / float(args.fps))
    page_font_path = args.font.format(h_page=display.page_number)
    if not os.path.isabs(page_font_path):
        page_font_path = os.path.join(repo_root, page_font_path)
    title_font_path = args.title_font if os.path.isabs(args.title_font) else os.path.join(repo_root, args.title_font)
    trans_font_path = args.translation_font if os.path.isabs(args.translation_font) else os.path.join(repo_root, args.translation_font)

    besmellah_info = None
    if display.ayah_number == 1 and args.surah_number not in (1, 9) and besm_text:
        besmellah_info = TextInfo(
            besm_text,
            besm_font_path,
            int(args.font_size * 1.3),
            "white",
            args.stroke_width,
            "black",
        )

    fd, temp_img = tempfile.mkstemp(suffix=".png", prefix="aligned_ayah_", dir=temp_dir)
    os.close(fd)
    create_full_text_image_persian(
        size=(args.size_x, args.size_y),
        margin_h=args.margin_h,
        margin_v=args.margin_v,
        interline=args.interline,
        main_text=TextInfo(display.arabic_text, page_font_path, args.font_size, "white", args.stroke_width, "black"),
        translation_below=TextInfo(display.translation_text, trans_font_path, args.translation_font_size, "white", args.stroke_width, "black") if display.translation_text else None,
        short_text_right="%03d surah" % args.surah_number if getattr(args, "show_sura_name", True) else None,
        short_font_path=title_font_path if getattr(args, "show_sura_name", True) else None,
        short_font_size=args.title_font_size,
        short_text_left=("صفحه " + to_persian_numerals(display.page_number)) if getattr(args, "show_page", True) else None,
        short_left_font_path=trans_font_path if getattr(args, "show_page", True) else None,
        short_left_font_size=args.translation_font_size,
        besmellah=besmellah_info,
        filename=temp_img,
        short_text_center=("جزء " + to_persian_numerals(args.juz_number_by_ayah[display.ayah_number])) if getattr(args, "show_juz", True) else None,
        short_center_font_path=trans_font_path if getattr(args, "show_juz", True) else None,
        short_center_font_size=args.translation_font_size,
        short_text_left_extra="≫" if is_backtracking and getattr(args, "show_page", True) else None,
        highlight_main_word_index=(active_word_index_in_ayah - 1) if active_word_index_in_ayah is not None else None,
        highlight_main_word_color=args.highlight_color,
    )

    seg_path = temp_img.replace(".png", ".mp4")
    bg_start = bg_clip_start_ref[0]
    if bg_video_path and os.path.isfile(bg_video_path):
        video_stream = ffmpeg.input(bg_video_path, ss=bg_start, t=duration_sec).video
    else:
        video_stream = ffmpeg.input("color=c=black:s=%dx%d:d=%.3f" % (args.size_x, args.size_y, duration_sec), f="lavfi").video
    video_stream = video_stream.filter("scale", args.size_x, args.size_y)
    img_in = ffmpeg.input(temp_img).video
    video_stream = ffmpeg.overlay(video_stream, img_in, x="(main_w-overlay_w)/2", y="(main_h-overlay_h)/2")
    ffmpeg.output(
        video_stream,
        seg_path,
        vcodec="libx264",
        an=None,
        r=args.fps,
        pix_fmt="yuv420p",
        vframes=frame_count,
    ).overwrite_output().run(quiet=True)
    bg_clip_start_ref[0] = bg_start + duration_sec
    try:
        os.remove(temp_img)
    except OSError:
        pass
    return seg_path


def run_aligned_sura(args) -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alignment_dir = args.alignment_dir
    audio_path = args.audio_file or os.path.join(alignment_dir, "audio.mp3")
    debug_path = args.alignment_debug_json or os.path.join(alignment_dir, "alignment.debug.json")

    if not os.path.isfile(audio_path):
        raise FileNotFoundError("Audio file not found: %s" % audio_path)
    if not os.path.isfile(debug_path):
        raise FileNotFoundError("Word-level alignment debug JSON not found: %s" % debug_path)

    alignment_debug = _read_alignment_debug(debug_path)
    word_runs = _build_word_runs(alignment_debug)
    if not word_runs:
        raise RuntimeError("No word_runs found in %s" % debug_path)

    ayah_count = max(run.ayah_number for run in word_runs if run.ayah_number > 0)
    ayah_displays = _build_ayah_displays(args, repo_root, ayah_count)
    args.juz_number_by_ayah = {ayah: fetch_juz_for_page(display.page_number) for ayah, display in ayah_displays.items()}

    besm_text, besm_page = fetch_besmellah_no_verse_number()
    besm_font_path = args.font.format(h_page=besm_page)
    if not os.path.isabs(besm_font_path):
        besm_font_path = os.path.join(repo_root, besm_font_path)

    bg_video_path = args.background_video
    bg_clip_start = args.bg_clip_start
    if bg_video_path and os.path.isfile(bg_video_path):
        safe_name = os.path.basename(bg_video_path).replace(" ", "_")[:80]
        clip_path = os.path.join(tempfile.gettempdir(), "aligned_bg_clip_%s.mp4" % safe_name)
        if not os.path.isfile(clip_path):
            try:
                inp = ffmpeg.input(bg_video_path, ss=args.bg_clip_start, t=7200)
                ffmpeg.output(inp, clip_path, c="copy").overwrite_output().run(quiet=True)
                if _is_valid_video_file(clip_path):
                    bg_video_path = clip_path
                    bg_clip_start = 0.0
            except Exception:
                pass
        elif _is_valid_video_file(clip_path):
            bg_video_path = clip_path
            bg_clip_start = 0.0

    audio_duration_ms = int(round(_get_audio_duration_seconds(audio_path) * 1000))
    timeline = _timeline_segments(word_runs, audio_duration_ms)
    if args.debug_limit_sec:
        limit_ms = int(args.debug_limit_sec * 1000)
        timeline = [(s, min(e, limit_ms), run) for s, e, run in timeline if s < limit_ms and min(e, limit_ms) > s]

    temp_dir = tempfile.mkdtemp(prefix="aligned_sura_")
    bg_clip_start_ref = [bg_clip_start]
    video_segments: list[str] = []
    max_ayah_seen = 0
    first_real_ayah = next((run.ayah_number for run in word_runs if run.ayah_number > 0), 1)
    current_ayah = first_real_ayah
    total_segments = len(timeline)
    prev_frame_boundary = 0
    for idx, (start_ms, end_ms, run) in enumerate(timeline, start=1):
        current_ayah = _display_ayah_number(run, current_ayah)
        display = ayah_displays[current_ayah]
        is_backtracking = False
        active_word_index_in_ayah = None
        if run is not None and run.ayah_number > 0:
            active_word_index_in_ayah = run.word_index_in_ayah
            is_backtracking = run.ayah_number < max_ayah_seen
            max_ayah_seen = max(max_ayah_seen, run.ayah_number)
        next_frame_boundary = max(prev_frame_boundary + 1, round(end_ms * args.fps / 1000.0))
        frame_count = next_frame_boundary - prev_frame_boundary
        video_segments.append(
            _render_ayah_segment(
                display=display,
                active_word_index_in_ayah=active_word_index_in_ayah,
                is_backtracking=is_backtracking,
                args=args,
                repo_root=repo_root,
                frame_count=frame_count,
                bg_video_path=bg_video_path,
                bg_clip_start_ref=bg_clip_start_ref,
                temp_dir=temp_dir,
                besm_text=besm_text,
                besm_font_path=besm_font_path,
            )
        )
        prev_frame_boundary = next_frame_boundary
        label = "ayah %d  %.2fs" % (current_ayah, max(0.001, (end_ms - start_ms) / 1000.0))
        _print_progress(idx, total_segments, label)

    concat_list = os.path.join(temp_dir, "segments.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for path in video_segments:
            f.write("file '%s'\n" % path.replace("'", "'\\''"))
    video_only_path = os.path.join(temp_dir, "video_only.mp4")
    ffmpeg.output(ffmpeg.input(concat_list, format="concat", safe=0), video_only_path, c="copy").overwrite_output().run(quiet=True)

    audio_input = ffmpeg.input(audio_path).audio
    if args.debug_limit_sec:
        audio_input = audio_input.filter("atrim", duration=args.debug_limit_sec).filter("asetpts", "PTS-STARTPTS")
    ffmpeg.output(
        ffmpeg.input(video_only_path).video,
        audio_input,
        args.output_path,
        vcodec="copy",
        acodec="aac",
        shortest=None,
    ).overwrite_output().run(quiet=True)

    print("Aligned sura movie written to %s" % args.output_path)
