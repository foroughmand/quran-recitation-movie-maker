#!/usr/bin/env python3
"""
Unified Quran recitation movie script: sura (one sura, translation/recitation from combined.wav)
or juz (ayah-by-ayah or page-by-page) with recitation/translation template URLs.

Modes:
  sura   — One sura: mapping file + combined.wav, Persian translation on screen (like create_movie_persian).
  juz    — One juz: --view ayah (one ayah per frame) or --view page (full page, current ayah highlighted).

Options: sura name (top-right), juz (center), page (top-left), Persian translation, recitation/translation
template URLs, first/last page templates, bismillah for suras 2–8 and 10–114, background, fonts/sizes.
Debug: --debug_5_sec (5 s per ayah in juz/page mode), --debug_no_background, --debug_pages,
--debug_begin_page, --debug_limit_ayahs, --debug_limit_recitation_sec, --debug_limit_translation_sec.
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _add_common_display(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--font", default="quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf", help="Arabic font; {h_page} for page.")
    ap.add_argument("--font_size", type=int, default=100)
    ap.add_argument("--title_font", default="quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf")
    ap.add_argument("--title_font_size", type=int, default=100)
    ap.add_argument("--translation_font", default="font/HM_XNiloofar.ttf")
    ap.add_argument("--translation_font_size", type=int, default=48)
    ap.add_argument("--size_x", type=int, default=1920)
    ap.add_argument("--size_y", type=int, default=1080)
    ap.add_argument("--margin_h", type=int, default=200)
    ap.add_argument("--margin_v", type=int, default=20)
    ap.add_argument("--interline", type=int, default=30)
    ap.add_argument("--stroke_width", type=int, default=5)
    ap.add_argument("--show_page", action="store_true", default=True, help="Show page number (top-left).")
    ap.add_argument("--show_sura_name", action="store_true", default=True, help="Show sura name (top-right).")
    ap.add_argument("--show_juz", action="store_true", default=False, help="Show juz number (center).")


def _add_background(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--background_video", default="", help="Background video path (empty = black).")
    ap.add_argument("--bg_clip_start", type=float, default=0.0, help="Start time (sec) in background video.")
    ap.add_argument("--fps", type=int, default=30)


def _add_first_last_page(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--first_page", default="", help="Intro template: {JOZ}, {SURELIST}. Newlines as \\n. Empty = default intro.")
    ap.add_argument("--add_first_page", action="store_true", default=True, help="Add intro page (Bismillah audio).")
    ap.add_argument("--last_page", default="", help="Outro template text (optional).")
    ap.add_argument("--add_last_page", action="store_true", default=False, help="Add last page segment.")


def _add_recitation_translation_templates(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--recitation_template",
        default="https://tanzil.net/res/audio/parhizgar/{sura}{ayah}.mp3",
        help="URL template for recitation; {sura}, {ayah} = 3-digit.",
    )
    ap.add_argument(
        "--translation_audio_template",
        default="",
        help="URL or path template for translation audio per ayah (e.g. local translation_audio/{ayah}.mp3). Empty = use local translation_audio when --include_translation_audio.",
    )
    ap.add_argument("--include_translation_audio", action="store_true", help="Append translation voice when available.")


def _add_debug(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--debug", action="store_true", help="Short run (few ayahs / one page) for quick preview.")
    ap.add_argument("--debug_5_sec", action="store_true", help="Limit each ayah to 5 seconds (juz/page mode). Without this, full recitation is used even in debug mode.")
    ap.add_argument("--debug_no_background", action="store_true", help="Force black background (ignore --background_video).")
    ap.add_argument("--debug_pages", default=None, metavar="LIST", help="Comma-separated pages to render only (juz/page mode).")
    ap.add_argument("--debug_begin_page", type=int, default=None, metavar="N", help="Only content on pages >= N.")
    ap.add_argument("--debug_limit_ayahs", type=int, default=None, metavar="N", help="Process only first N ayahs.")
    ap.add_argument("--debug_limit_recitation_sec", type=float, default=None, metavar="SEC", help="Trim recitation to SEC sec per ayah.")
    ap.add_argument("--debug_limit_translation_sec", type=float, default=None, metavar="SEC", help="Trim translation audio to SEC sec.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Unified Quran recitation movie: sura (one sura) or juz (ayah or page view).",
    )
    sub = ap.add_subparsers(dest="mode", required=True, help="sura | juz")

    # --- sura ---
    sura_p = sub.add_parser("sura", help="One sura: mapping + combined.wav, translation on screen.")
    sura_p.add_argument("text_file", help="Path to quran-simple-plain-{sura}.txt (unused; compat).")
    sura_p.add_argument("mapping_file", help="Path to segment_mapping.txt.")
    sura_p.add_argument("audio_file", help="Path to combined.wav.")
    sura_p.add_argument("output_path", help="Output MP4 path.")
    sura_p.add_argument("background_video", help="Background video path (or 'none').")
    sura_p.add_argument("surah_number", type=int, help="Sura number (1–114).")
    sura_p.add_argument("--translation_dir", default="", help="Directory with 1.txt, 2.txt, ...")
    sura_p.add_argument("--title", default="", help="Sura title (e.g. 059 surah).")
    sura_p.add_argument("--bg_clip_start", type=float, default=0.0)
    sura_p.add_argument("--audio_skip", type=float, default=0.0)
    sura_p.add_argument("--audio", default="translation")
    _add_common_display(sura_p)
    _add_debug(sura_p)

    # --- juz ---
    juz_p = sub.add_parser("juz", help="One juz: ayah-by-ayah or page-by-page.")
    juz_p.add_argument("juz_number", type=int, help="Juz number (1–30).")
    juz_p.add_argument("output_path", help="Output MP4 path.")
    juz_p.add_argument("--view", choices=("ayah", "page"), default="ayah",
                       help="ayah = one ayah per frame; page = full page with current ayah highlighted.")
    juz_p.add_argument("--translation_root", default="data/persian-recitation")
    juz_p.add_argument("--speed", type=float, default=1.0)
    juz_p.add_argument("--reciter_name", default="")
    juz_p.add_argument("--highlight_color", default="#FFFF00", help="Highlight color for page view.")
    _add_common_display(juz_p)
    _add_background(juz_p)
    _add_first_last_page(juz_p)
    juz_p.add_argument(
        "--full_bismillah_intro",
        action="store_true",
        help="On the intro page, play the full bismillah (1:1) instead of only the first 3 s when the juz starts at a sura start (e.g. Shateri).",
    )
    _add_recitation_translation_templates(juz_p)
    _add_debug(juz_p)

    aligned_p = sub.add_parser("aligned_sura", help="One sura from full-audio + word alignment debug JSON.")
    aligned_p.add_argument("alignment_dir", help="Directory containing audio.mp3 and alignment.debug.json.")
    aligned_p.add_argument("output_path", help="Output MP4 path.")
    aligned_p.add_argument("background_video", help="Background video path (or 'none').")
    aligned_p.add_argument("surah_number", type=int, help="Sura number (1–114).")
    aligned_p.add_argument("--audio_file", default="", help="Optional override for aligned audio file.")
    aligned_p.add_argument("--alignment_debug_json", default="", help="Optional override for alignment.debug.json.")
    aligned_p.add_argument("--translation_dir", default="", help="Directory with 1.txt, 2.txt, ...")
    aligned_p.add_argument("--highlight_color", default="#FFFF00", help="Word highlight color.")
    aligned_p.add_argument("--debug_limit_sec", type=float, default=None, help="Trim preview to first SEC seconds.")
    aligned_p.add_argument("--bg_clip_start", type=float, default=0.0, help="Start time (sec) in background video.")
    aligned_p.add_argument("--fps", type=int, default=30)
    _add_common_display(aligned_p)

    args = ap.parse_args()

    if args.mode == "sura":
        # Optional: force no background for debug
        if getattr(args, "debug_no_background", False) and args.background_video:
            args.background_video = "none"
        if args.background_video and args.background_video.lower() == "none":
            args.background_video = ""
        import create_movie_persian
        create_movie_persian.run_sura(args)
        return

    if args.mode == "juz":
        if getattr(args, "debug_no_background", False):
            args.background_video = ""
        if args.view == "ayah":
            import create_movie_persian_juz
            create_movie_persian_juz.run_juz(args)
        else:
            import create_movie_persian_juz_by_page
            create_movie_persian_juz_by_page.run_juz_by_page(args)
        return

    if args.mode == "aligned_sura":
        if args.background_video and args.background_video.lower() == "none":
            args.background_video = ""
        import create_movie_quran_aligned
        create_movie_quran_aligned.run_aligned_sura(args)
        return

    ap.error("Unknown mode %s" % args.mode)


if __name__ == "__main__":
    main()
