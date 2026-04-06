#!/usr/bin/env python3
"""
Create a Persian translation-only-voice movie for one sura: ayah-by-ayah content
(Arabic text + translation, same wrapping and font shrinkage as juz script) but
audio is only Persian translation (no Arabic recitation).

- Plays only the translation segments from combined.wav (no recitation).
- Each frame shows Arabic ayah + translation (create_full_text_image_persian), with optional bismillah on first ayah.
- For suras 2–8 and 10–114: optional first segment = bismillah (Arabic + translation on screen, translation audio only; no ayah number).

  How to run debug (first 3 ayahs, black background, 5 s per ayah; no background file needed):
    From repo root (pass a placeholder for background, e.g. none):
      python3 src/create_movie_persian.py \\
        data/quran-simple-plain-59.txt \\
        data/persian-recitation/sura_59/segment_mapping.txt \\
        data/persian-recitation/sura_59/combined.wav \\
        out/debug-p59.mp4 \\
        none \\
        59 \\
        --translation_dir data/persian-recitation/sura_59/translation_text \\
        --title "059 surah" --translation_font font/HM_XNiloofar.ttf \\
        --translation_font_size 48 --show_page --audio translation --debug
    Or from persian-recitation.sh: add --debug to the python3 line in Step 4 (background is still
    passed but ignored in debug).
"""

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from create_movie_persian_juz import (
    TextInfo,
    create_full_text_image_persian,
    fetch_ayah_words,
    fetch_besmellah_no_verse_number,
    to_persian_numerals,
    _get_audio_duration_seconds,
)

import re

import ffmpeg


def _strip_leading_ayah_number(text: str) -> str:
    """Remove leading ayah number from translation text (e.g. '۱. ' or '1. '). Used for added bismillah so no ayah number is shown."""
    if not text or not text.strip():
        return text
    # Strip optional spaces, then digits (ASCII 0-9 or Arabic-Indic ۰-۹), then optional period/dot and space
    return re.sub(r"^\s*[\d۰-۹]+\s*[.\u06D4]?\s*", "", text).strip()


def _strip_any_ayah_number(text: str) -> str:
    """Remove any leading or trailing ayah number (Arabic ٠-٩, Arabic-Indic ۰-۹, ASCII 0-9, with optional period/parens). For bismillah display."""
    if not text or not text.strip():
        return text
    # Leading: digits + optional period/parens + space
    text = re.sub(r"^\s*[\d۰-۹٠-٩]+\s*[.\u06D4()\[\]]?\s*", "", text)
    # Trailing: space + optional parens + digits + optional period
    text = re.sub(r"\s*[(\[]?\s*[\d۰-۹٠-٩]+\s*[.)\]\u06D4]?\s*$", "", text)
    return text.strip()


def parse_segment_mapping(path: str) -> list[tuple[float, float, int]]:
    """Return list of (start_sec, end_sec, ayah_number) from segment_mapping.txt."""
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                out.append((float(parts[0]), float(parts[1]), int(parts[2])))
    return out


def translation_only_segments(
    segments: list[tuple[float, float, int]],
) -> list[tuple[float, float, int]]:
    """From rec1, trans1, rec2, trans2, ... keep only translation segments (indices 1, 3, 5, ...)."""
    return [seg for i, seg in enumerate(segments) if i % 2 == 1]


def recitation_only_segments(
    segments: list[tuple[float, float, int]],
) -> list[tuple[float, float, int]]:
    """Keep only recitation segments.
    If mapping is rec+trans per ayah (2*N segments): use even indices (0, 2, 4, ...).
    If mapping is rec-only (N segments, one per ayah): use all segments (no translation gaps).
    """
    num_ayas = max(seg[2] for seg in segments) if segments else 0
    layout = "unknown"
    if num_ayas and len(segments) == 2 * num_ayas:
        layout = "rec+trans"
        chosen = [seg for i, seg in enumerate(segments) if i % 2 == 0]
    else:
        layout = "rec-only-or-mixed"
        chosen = list(segments)
    print(
        "  [segments] total=%d, num_ayas=%d, layout=%s, using=%d"
        % (len(segments), num_ayas, layout, len(chosen)),
        file=sys.stderr,
    )
    # Log a few sample segments for debugging
    for i, (s, e, ay) in enumerate(chosen[:5]):
        print(
            "    [seg%02d] ayah=%d start=%.3f end=%.3f dur=%.3f"
            % (i, ay, s, e, e - s),
            file=sys.stderr,
        )
    return chosen


def run_sura(args: argparse.Namespace) -> None:
    """Create Persian sura movie: Arabic + translation text on screen; audio = translation voice or recitation (--audio)."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    segments = parse_segment_mapping(args.mapping_file)
    if not segments:
        print("No segments in mapping file.", file=sys.stderr)
        sys.exit(1)
    # High-level mapping info
    num_ayas = max(seg[2] for seg in segments) if segments else 0
    print(
      "[mapping] file=%s total_segments=%d num_ayas=%d first=%s last=%s"
      % (
          args.mapping_file,
          len(segments),
          num_ayas,
          ("%.3f-%.3f ayah=%d" % segments[0]) if segments else "n/a",
          ("%.3f-%.3f ayah=%d" % segments[-1]) if segments else "n/a",
        ),
        file=sys.stderr,
    )

    audio_mode = (getattr(args, "audio", None) or "translation").strip().lower()
    if audio_mode == "recitation":
        active_segments = recitation_only_segments(segments)
        if not active_segments:
            print("No recitation segments in mapping file.", file=sys.stderr)
            sys.exit(1)
        print("  Audio: recitation only (Arabic recitation, no translation voice)")
    else:
        active_segments = translation_only_segments(segments)
        if not active_segments:
            print("No translation segments in mapping file.", file=sys.stderr)
            sys.exit(1)
        print("  Audio: translation only (Persian translation voice)")
    if args.debug:
        active_segments = active_segments[:3]
        print("Debug mode: only first 3 segments.", file=sys.stderr)

    def path_or_repo(p: str) -> str:
        return p if os.path.isabs(p) else os.path.join(repo_root, p)

    title_font = path_or_repo(args.title_font)
    trans_font = path_or_repo(args.translation_font)
    translation_dir = args.translation_dir or os.path.join(
        repo_root, "data", "persian-recitation", "sura_%d" % args.surah_number, "translation_text"
    )
    sura_dir = os.path.dirname(translation_dir)
    data_root = os.path.join(repo_root, "data", "persian-recitation")

    # Optional bismillah translation segment: suras 2–8 and 10–114 only (not 1, not 9)
    add_bismillah_trans = args.surah_number in (*range(2, 9), *range(10, 115))
    bismillah_trans_audio = os.path.join(sura_dir, "translation_audio", "0.mp3")
    bismillah_trans_text_path = os.path.join(data_root, "sura_1", "translation_text", "1.txt")
    besm_arabic_text, besm_page = "", 1
    if add_bismillah_trans and os.path.isfile(bismillah_trans_audio) and os.path.isfile(bismillah_trans_text_path):
        besm_arabic_text, besm_page = fetch_besmellah_no_verse_number()
        with open(bismillah_trans_text_path, "r", encoding="utf-8") as f:
            bismillah_trans_text = f.read().strip()
    else:
        bismillah_trans_text = None
        bismillah_trans_audio = None

    # Build list of clips: (kind, img_path, audio_src, ayah_or_none)
    clips = []
    # Bismillah clip only for translation mode (recitation mode has bismillah inside first recitation segment)
    if audio_mode != "recitation" and besm_arabic_text and bismillah_trans_text and os.path.isfile(bismillah_trans_audio):
        fd = tempfile.mkstemp(suffix=".png", prefix="persian_bismillah_")
        os.close(fd[0])
        bism_img = fd[1]
        besm_font_path = path_or_repo(args.font.format(h_page=besm_page))
        besm_arabic_display = _strip_any_ayah_number(besm_arabic_text)
        bismillah_trans_display = _strip_any_ayah_number(bismillah_trans_text)
        create_full_text_image_persian(
            size=(args.size_x, args.size_y),
            margin_h=args.margin_h,
            margin_v=args.margin_v,
            interline=args.interline,
            main_text=TextInfo(besm_arabic_display, besm_font_path, args.font_size, "white", args.stroke_width, "black"),
            translation_below=TextInfo(bismillah_trans_display, trans_font, args.translation_font_size, "white", args.stroke_width, "black"),
            short_text_right=(args.title or "%03d surah" % args.surah_number).strip(),
            short_font_path=title_font,
            short_font_size=args.title_font_size,
            short_text_left="",
            short_left_font_path=None,
            short_left_font_size=args.translation_font_size,
            besmellah=None,
            filename=bism_img,
        )
        clips.append(("bismillah", bism_img, bismillah_trans_audio, None))
        print("  Bismillah (Arabic + translation; no ayah number, no page number)")

    # Prefetch besmellah for first-ayah segments (suras 2–8, 10–114); use no-verse-number so besmellah line has no ayah number
    besm_text, besm_font_path = "", ""
    if args.surah_number not in (1, 9):
        besm_text, besm_page_num = fetch_besmellah_no_verse_number()
        besm_font_path = path_or_repo(args.font.format(h_page=besm_page_num))

    for start, end, ayah in active_segments:
        arabic_text, page = fetch_ayah_words(args.surah_number, ayah)
        main_font_path = path_or_repo(args.font.format(h_page=page))

        trans_path = os.path.join(translation_dir, "%d.txt" % ayah)
        trans_text = ""
        if os.path.isfile(trans_path):
            with open(trans_path, "r", encoding="utf-8") as f:
                trans_text = f.read().strip()

        page_label = "صفحه " + to_persian_numerals(page) if args.show_page else ""
        sura_label = (args.title or "%03d surah" % args.surah_number).strip()
        add_besmellah_here = ayah == 1 and args.surah_number not in (1, 9) and besm_text
        besmellah_info = None
        if add_besmellah_here:
            besmellah_info = TextInfo(
                besm_text,
                besm_font_path,
                int(args.font_size * 1.3),
                "white",
                args.stroke_width,
                "black",
            )

        fd = tempfile.mkstemp(suffix=".png", prefix="persian_ayah_")
        os.close(fd[0])
        img_path = fd[1]
        create_full_text_image_persian(
            size=(args.size_x, args.size_y),
            margin_h=args.margin_h,
            margin_v=args.margin_v,
            interline=args.interline,
            main_text=TextInfo(arabic_text, main_font_path, args.font_size, "white", args.stroke_width, "black"),
            translation_below=TextInfo(trans_text, trans_font, args.translation_font_size, "white", args.stroke_width, "black") if trans_text else None,
            short_text_right=sura_label,
            short_font_path=title_font,
            short_font_size=args.title_font_size,
            short_text_left=page_label,
            short_left_font_path=trans_font if page_label else None,
            short_left_font_size=args.translation_font_size,
            besmellah=besmellah_info,
            filename=img_path,
        )
        clips.append(("ayah", img_path, (start, end), ayah))
        print("  Ayah %d (Arabic + translation): %.1f–%.1fs" % (ayah, start, end))

    # Build one video per clip (image + audio), then concat
    segment_mp4s = []
    debug_sec = 5.0  # in debug mode, cap each segment to this many seconds
    use_bg = not args.debug and args.background_video and (not isinstance(args.background_video, str) or args.background_video.strip().lower() != "none")
    bg_pos = float(args.bg_clip_start) if use_bg else 0.0

    for i, item in enumerate(clips):
        kind, img_path, audio_src, ayah = item
        if kind == "bismillah":
            audio_in = ffmpeg.input(audio_src).audio
            seg_dur = _get_audio_duration_seconds(audio_src) if os.path.isfile(audio_src) else 0.0
            if args.debug:
                audio_in = audio_in.filter("atrim", duration=debug_sec)
                seg_dur = min(seg_dur, debug_sec) if seg_dur else debug_sec
        else:
            start, end = audio_src
            dur = end - start
            if args.debug:
                dur = min(dur, debug_sec)
            audio_in = ffmpeg.input(args.audio_file, ss=start + args.audio_skip, t=dur).audio
            seg_dur = dur

        # Reset audio timestamps so each segment starts at t=0 (concat stays correct).
        audio_in = audio_in.filter("asetpts", "PTS-STARTPTS")

        if not use_bg:
            video_stream = ffmpeg.input(
                "color=c=black:s=%dx%d:d=3600" % (args.size_x, args.size_y),
                f="lavfi",
            ).video
        else:
            # Advance background per segment so it stays continuous across ayahs
            video_stream = ffmpeg.input(args.background_video, ss=bg_pos).video
            if seg_dur and seg_dur > 0:
                video_stream = video_stream.filter("trim", duration=seg_dur).filter("setpts", "PTS-STARTPTS")
        video_stream = video_stream.filter("scale", args.size_x, args.size_y)

        img_in = ffmpeg.input(img_path).video
        vid = ffmpeg.overlay(
            video_stream,
            img_in,
            x="(main_w-overlay_w)/2",
            y="(main_h-overlay_h)/2",
        )
        seg_mp4 = args.output_path + ".seg_%d.mp4" % i
        segment_mp4s.append(seg_mp4)
        out = ffmpeg.output(
            vid,
            audio_in,
            seg_mp4,
            vcodec="libx264",
            acodec="aac",
            r=30,
            pix_fmt="yuv420p",
            # Flag only; when present, ffmpeg stops at shortest stream.
            shortest=None,
        )
        out = out.overwrite_output()
        try:
            out.run(quiet=True)
        except ffmpeg.Error as e:
            err = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr or "")
            for _c in clips:
                try:
                    os.remove(_c[1])
                except OSError:
                    pass
            for p in segment_mp4s:
                try:
                    os.remove(p)
                except OSError:
                    pass
            raise RuntimeError("FFmpeg failed: %s" % err) from e
        if use_bg and seg_dur and seg_dur > 0:
            bg_pos += seg_dur

    # Concat all segment mp4s with a very short audio crossfade so boundaries sound continuous
    CROSSFADE_DUR = 0.02  # 20 ms overlap at each boundary (keeps audio smooth, minimizes A/V offset)
    inputs = [ffmpeg.input(seg) for seg in segment_mp4s]
    video_out = ffmpeg.concat(*[inp.video for inp in inputs], n=len(inputs), v=1, a=0)
    audio_out = inputs[0].audio
    for i in range(1, len(inputs)):
        audio_out = ffmpeg.filter(
            [audio_out, inputs[i].audio],
            "acrossfade",
            d=CROSSFADE_DUR,
            c1="tri",
            c2="tri",
        )
    try:
        out = ffmpeg.output(
            video_out,
            audio_out,
            args.output_path,
            vcodec="libx264",
            acodec="aac",
            r=30,
            pix_fmt="yuv420p",
        )
        out = out.overwrite_output()
        out.run(quiet=True)
    except ffmpeg.Error as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr or "")
        raise RuntimeError("FFmpeg concat failed: %s" % err) from e
    finally:
        for img_path in [c[1] for c in clips]:
            try:
                os.remove(img_path)
            except OSError:
                pass
        for seg in segment_mp4s:
            try:
                os.remove(seg)
            except OSError:
                pass

    print("Wrote %s" % args.output_path)


def parse_sura_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Create Persian translation-only movie (translation voice + text only, no Arabic)."
    )
    ap.add_argument("text_file", help="Path to quran-simple-plain-{sura}.txt (unused; kept for compat).")
    ap.add_argument("mapping_file", help="Path to segment_mapping.txt (start end ayah per line).")
    ap.add_argument("audio_file", help="Path to combined.wav.")
    ap.add_argument("output_path", help="Output MP4 path.")
    ap.add_argument("background_video", help="Background video path.")
    ap.add_argument("surah_number", type=int, help="Sura number (1–114).")
    ap.add_argument("--translation_dir", default="", help="Directory with 1.txt, 2.txt, ... (and 0.txt for bismillah if used).")
    ap.add_argument("--font", default="quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf")
    ap.add_argument("--font_size", type=int, default=100)
    ap.add_argument("--title", default="", help="Sura title (e.g. 059 surah).")
    ap.add_argument("--title_font", default="quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf")
    ap.add_argument("--title_font_size", type=int, default=100)
    ap.add_argument("--size_x", type=int, default=1920)
    ap.add_argument("--size_y", type=int, default=1080)
    ap.add_argument("--margin_h", type=int, default=200)
    ap.add_argument("--margin_v", type=int, default=20)
    ap.add_argument("--interline", type=int, default=30)
    ap.add_argument("--stroke_width", type=int, default=5)
    ap.add_argument("--translation_font", default="font/HM_XNiloofar.ttf")
    ap.add_argument("--translation_font_size", type=int, default=48)
    ap.add_argument("--show_page", action="store_true", help="Show page number (top-left).")
    ap.add_argument("--bg_clip_start", type=float, default=0.0, help="Start time (sec) in background video.")
    ap.add_argument("--audio_skip", type=float, default=0.0, help="Add this to overlay times to sync with audio.")
    ap.add_argument("--audio", default="translation", help="Unused; kept for compatibility.")
    ap.add_argument("--debug", action="store_true", help="First 3 ayahs only; no background (black); 5 s per ayah. No background file needed.")
    return ap.parse_args()


def main() -> None:
    args = parse_sura_args()
    run_sura(args)


if __name__ == "__main__":
    main()
