#!/usr/bin/env python3
"""
Create Persian recitation movie: Arabic ayah + Persian translation on screen,
with segment-based timing (recitation then translation per ayah).
"""
import argparse
import os
import random
import re
import sys

import ffmpeg
import requests
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont


@dataclass
class TextInfo:
    text: str
    font: str
    font_size: int
    font_color: str
    stroke_width: int
    stroke_color: str


def wrap_text_to_lines(draw, text: str, font, max_width: int):
    """Split text into lines that fit within max_width (word wrap)."""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip() if current_line else word
        if draw.textbbox((0, 0), test_line, font=font)[2] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


def create_full_text_image_persian(
    main_text_info,
    additional_text_info,
    short_text_info,
    size,
    margin,
    filename,
    translation_below_info=None,
    interline_ratio=0.28,
):
    """Draw main (Arabic), optional above (besmellah), short (title), optional below (translation, wrapped).
    Line spacing (interline) is derived from main font size * interline_ratio so it scales with text size.
    """
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    short_font = (
        ImageFont.truetype(short_text_info.font, short_text_info.font_size)
        if short_text_info
        else None
    )
    min_top = margin[1]
    if short_text_info is not None:
        draw.text(
            (size[0] - margin[0], margin[1]),
            short_text_info.text,
            font=short_font,
            fill=(255, 255, 255),
            stroke_fill=short_text_info.stroke_color,
            stroke_width=short_text_info.stroke_width,
            anchor="ra",
        )
        min_top += draw.textbbox((0, 0), short_text_info.text, font=short_font)[3]

    max_width = size[0] - 2 * margin[0]

    while True:
        interline = max(2, int(main_text_info.font_size * interline_ratio))
        main_font = ImageFont.truetype(main_text_info.font, main_text_info.font_size)
        words = main_text_info.text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if draw.textbbox((0, 0), test_line, font=main_font)[2] < max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        total_text_height = sum(
            draw.textbbox((0, 0), line, font=main_font)[3] for line in lines
        ) + (len(lines) - 1) * interline

        trans_lines = []
        trans_height = 0
        if translation_below_info is not None:
            trans_font = ImageFont.truetype(
                translation_below_info.font, translation_below_info.font_size
            )
            trans_lines = wrap_text_to_lines(
                draw, translation_below_info.text, trans_font, max_width
            )
            trans_height = sum(
                draw.textbbox((0, 0), ln, font=trans_font)[3] for ln in trans_lines
            ) + (len(trans_lines) - 1) * interline if trans_lines else 0
            trans_height += interline  # gap above translation block

        y_main_text = (
            size[1]
            - total_text_height
            + draw.textbbox((0, 0), lines[0], font=main_font)[3]
            - trans_height
        ) // 2
        y_min = y_main_text - draw.textbbox((0, 0), lines[0], font=main_font)[3] // 2
        if additional_text_info is not None:
            additional_font = ImageFont.truetype(
                additional_text_info.font, additional_text_info.font_size
            )
            y_min -= (
                draw.textbbox((0, 0), additional_text_info.text, font=additional_font)[3]
                + interline
            )
        y_min = min(
            y_min,
            size[1] - margin[1] - (total_text_height + trans_height),
        )
        if y_min > min_top or main_text_info.font_size < 1:
            break
        main_text_info.font_size = int(main_text_info.font_size * 0.9)
        if additional_text_info is not None:
            additional_text_info.font_size = int(additional_text_info.font_size * 0.9)
        if translation_below_info is not None:
            translation_below_info.font_size = int(
                translation_below_info.font_size * 0.9
            )

    interline = max(2, int(main_text_info.font_size * interline_ratio))
    main_font = ImageFont.truetype(main_text_info.font, main_text_info.font_size)
    if translation_below_info is not None:
        trans_font = ImageFont.truetype(
            translation_below_info.font, translation_below_info.font_size
        )
        trans_lines = wrap_text_to_lines(
            draw, translation_below_info.text, trans_font, max_width
        )
    else:
        trans_lines = []

    if additional_text_info is not None:
        additional_font = ImageFont.truetype(
            additional_text_info.font, additional_text_info.font_size
        )
        y_additional_text = (
            y_main_text
            - draw.textbbox((0, 0), additional_text_info.text, font=additional_font)[3]
            // 2
            - draw.textbbox((0, 0), lines[0], font=main_font)[3] // 2
            - interline
        )
        draw.text(
            (size[0] // 2, y_additional_text),
            additional_text_info.text,
            font=additional_font,
            fill=(255, 255, 255),
            stroke_fill=additional_text_info.stroke_color,
            stroke_width=additional_text_info.stroke_width,
            anchor="mm",
        )
    y_text = y_main_text
    for line in lines:
        draw.text(
            (size[0] // 2, y_text),
            line,
            font=main_font,
            fill=(255, 255, 255),
            stroke_width=main_text_info.stroke_width,
            stroke_fill=main_text_info.stroke_color,
            anchor="mm",
        )
        y_text += draw.textbbox((0, 0), line, font=main_font)[3] + interline
    if trans_lines:
        y_trans = y_text + interline
        for ln in trans_lines:
            draw.text(
                (size[0] // 2, y_trans),
                ln,
                font=trans_font,
                fill=(255, 255, 255),
                stroke_width=translation_below_info.stroke_width,
                stroke_fill=translation_below_info.stroke_color,
                anchor="mm",
            )
            y_trans += draw.textbbox((0, 0), ln, font=trans_font)[3] + interline
    img.save(filename, format="PNG")
    return filename


def time_to_seconds(time_str):
    if isinstance(time_str, (int, float)):
        return float(time_str)
    match = re.match(r"(?:(\d+):)?(?:(\d+):)?(\d+)(?:\.(\d+))?", str(time_str))
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
    hh = int(match.group(1)) if match.group(1) else 0
    mm = int(match.group(2)) if match.group(2) else 0
    ss = int(match.group(3)) if match.group(3) else 0
    ms = match.group(4) if match.group(4) else "0"
    ms = int(ms.ljust(3, "0"))
    return hh * 3600 + mm * 60 + ss + ms / 1000


def parse_segment_mapping(path):
    """Return list of (start_sec, end_sec, ayah_number)."""
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


def fetch_ayah_text(surah_number: int, ayah_number: int, font_pattern: str):
    """Get Arabic ayah text and font path from Quran.com API (code_v1 words)."""
    api_url = f"https://api.quran.com/api/v4/verses/by_key/{surah_number}:{ayah_number}?words=true"
    r = requests.get(api_url, timeout=15)
    r.raise_for_status()
    data = r.json()
    words = data["verse"]["words"]
    page = data["verse"]["page_number"]
    h_text = " ".join(w["code_v1"] for w in words)
    h_text = h_text[: (len(h_text) - 2)] + h_text[len(h_text) - 1]
    font = font_pattern.format(h_page=page)
    return h_text, font


def fetch_besmellah(font_pattern: str):
    """Besmellah (1:1) for first ayah."""
    r = requests.get(
        "https://api.quran.com/api/v4/verses/by_key/1:1?words=true", timeout=15
    )
    r.raise_for_status()
    data = r.json()
    words = data["verse"]["words"]
    page = data["verse"]["page_number"]
    h_text = " ".join(w["code_v1"] for w in words[:-1])
    font = font_pattern.format(h_page=page)
    return h_text, font


def main():
    p = argparse.ArgumentParser(
        description="Create Persian recitation movie (Arabic + translation, segment-based)."
    )
    p.add_argument("text_file", help="Arabic text file (one ayah per line; used for count only if no API).")
    p.add_argument("segment_mapping", help="Segment mapping: start_sec end_sec ayah_number per line.")
    p.add_argument("audio_file", help="Combined WAV (recitation+translation per ayah).")
    p.add_argument("output", help="Output video path.")
    p.add_argument("background_video", help="Background video path.")
    p.add_argument("surah_number", type=int, help="Sura number (1–114).")
    p.add_argument("--translation_dir", required=True, help="Directory with translation_text/1.txt, 2.txt, ...")
    p.add_argument("--font", default="quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf")
    p.add_argument("--font_size", type=int, default=100)
    p.add_argument("--title", default="")
    p.add_argument("--title_font", default="quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf")
    p.add_argument("--title_font_size", type=int, default=100)
    p.add_argument("--translation_font", default="font/HM_XNiloofar.ttf")
    p.add_argument("--translation_font_size", type=int, default=48)
    p.add_argument("--size_x", type=int, default=1920)
    p.add_argument("--size_y", type=int, default=1080)
    p.add_argument("--margin_h", type=int, default=200)
    p.add_argument("--margin_v", type=int, default=20)
    p.add_argument("--interline", type=int, default=30, help="Unused when --interline_ratio is used (default).")
    p.add_argument("--interline_ratio", type=float, default=0.28, help="Line spacing = font_size * this (reduces gap when font is small).")
    p.add_argument("--stroke_width", type=int, default=5)
    p.add_argument("--stroke_color", default="black")
    p.add_argument("--bg_clip_start", default="0")
    p.add_argument("--audio_skip", type=float, default=0.0)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument(
        "--ayes",
        "--pages",
        dest="ayes",
        type=str,
        default=None,
        help="Only include these ayahs (e.g. 1:5:10 for ayahs 1, 5, 10). Colon-separated.",
    )
    p.add_argument(
        "--audio",
        choices=("both", "recitation", "translation"),
        default="both",
        help="Which voice to include: both (default), only recitation, or only translation.",
    )
    args = p.parse_args()

    segments = parse_segment_mapping(args.segment_mapping)
    if not segments:
        print("No segments in mapping file.")
        sys.exit(1)

    if args.ayes:
        aye_set = {int(x.strip()) for x in args.ayes.split(":") if x.strip()}
        segments = [(s, e, a) for s, e, a in segments if a in aye_set]
        if not segments:
            print("No segments left after filtering by --ayes.")
            sys.exit(1)
        segments.sort(key=lambda x: x[0])
        print(f"Filtered to ayahs {sorted(aye_set)}: {len(segments)} segments")

    # Filter by voice: segment order is rec_1, trans_1, rec_2, trans_2, ... (even index = recitation)
    trim_ranges = None  # (start, end) per kept segment for building concat audio
    if args.audio != "both":
        if args.audio == "recitation":
            segments_kept = [(s, e, a) for i, (s, e, a) in enumerate(segments) if i % 2 == 0]
        else:  # translation
            segments_kept = [(s, e, a) for i, (s, e, a) in enumerate(segments) if i % 2 == 1]
        if not segments_kept:
            print(f"No segments left for --audio {args.audio}.")
            sys.exit(1)
        print(f"Audio: {args.audio} only ({len(segments_kept)} segments)")
        trim_ranges = [(s, e) for s, e, a in segments_kept]
        new_segments = []
        t = 0.0
        for (s, e, a) in segments_kept:
            dur = e - s
            new_segments.append((t, t + dur, a))
            t += dur
        segments = new_segments
    else:
        segments_kept = None

    audio_start_sec = segments[0][0]
    audio_end_sec = segments[-1][1]
    if trim_ranges is None and args.ayes:
        for i in range(len(segments)):
            s, e, a = segments[i]
            segments[i] = (s - audio_start_sec, e - audio_start_sec, a)
        audio_end_sec = audio_end_sec - audio_start_sec
        audio_start_sec = 0

    need_concat_audio = trim_ranges is not None

    translation_dir = args.translation_dir.rstrip("/")
    if not os.path.isdir(translation_dir):
        print(f"Translation dir not found: {translation_dir}")
        sys.exit(1)

    bg_clip_start_seconds = time_to_seconds(args.bg_clip_start)
    img_overlays = []

    for seg_start, seg_end, ayah_number in segments:
        # Ayah Arabic text from API
        h_text, h_font = fetch_ayah_text(
            args.surah_number, ayah_number, args.font
        )
        aye_text_info = TextInfo(
            h_text, h_font, args.font_size, "white",
            args.stroke_width, args.stroke_color
        )
        # Show Bismillah above first ayah only for suras that start with it:
        # not sura 1 (Al-Hamd: first ayah is already Bismillah) and not sura 9 (no Bismillah).
        besmellah_text_info = None
        if ayah_number == 1 and args.surah_number != 1 and args.surah_number != 9:
            b_text, b_font = fetch_besmellah(args.font)
            besmellah_text_info = TextInfo(
                b_text, b_font, int(args.font_size * 1.3), "white",
                args.stroke_width, args.stroke_color
            )
        sure_name_text_info = TextInfo(
            args.title or "", args.title_font, args.title_font_size,
            "white", 3, "#0a0a0a"
        )
        # Translation text from file
        trans_path = os.path.join(translation_dir, f"{ayah_number}.txt")
        translation_text = ""
        if os.path.isfile(trans_path):
            with open(trans_path, "r", encoding="utf-8") as f:
                translation_text = f.read().strip()
        translation_below_info = None
        if translation_text:
            translation_below_info = TextInfo(
                translation_text,
                args.translation_font,
                args.translation_font_size,
                "white",
                max(1, args.stroke_width // 2),
                args.stroke_color,
            )

        r = random.randint(100000, 999999)
        temp_img = f"tmp/temp_text_persian_{ayah_number}_{r}.png"
        os.makedirs("tmp", exist_ok=True)
        create_full_text_image_persian(
            aye_text_info,
            besmellah_text_info,
            sure_name_text_info,
            (args.size_x, args.size_y),
            (args.margin_h, args.margin_v),
            temp_img,
            translation_below_info=translation_below_info,
            interline_ratio=args.interline_ratio,
        )
        img_overlays.append((temp_img, seg_start, seg_end))

    # Single output with overlays and audio (trimmed when --ayes or concat when --audio recitation/translation)
    input_video = ffmpeg.input(
        args.background_video, ss=bg_clip_start_seconds
    ).video
    resized = input_video.filter("scale", args.size_x, args.size_y)
    if need_concat_audio:
        # Concat only the kept segments (recitation or translation) from full combined.wav
        full_audio = ffmpeg.input(args.audio_file).audio
        trimmed = [
            full_audio.filter("atrim", start=s, end=e).filter("asetpts", "PTS-STARTPTS")
            for s, e in trim_ranges
        ]
        input_audio = ffmpeg.concat(*trimmed, n=len(trimmed), v=0, a=1)
    elif args.ayes:
        input_audio = ffmpeg.input(
            args.audio_file,
            ss=audio_start_sec,
            t=audio_end_sec - audio_start_sec,
        )
    else:
        input_audio = ffmpeg.input(args.audio_file)
    overlays = resized
    for img_fn, start_t, end_t in img_overlays:
        img = ffmpeg.input(img_fn)
        overlays = ffmpeg.overlay(
            overlays,
            img,
            enable=f"between(t,{start_t + args.audio_skip},{end_t + args.audio_skip})",
            x="(main_w-overlay_w)/2",
            y="(main_h-overlay_h)/2",
        )
    total_duration = (
        (audio_end_sec - audio_start_sec + args.audio_skip)
        if (args.ayes or need_concat_audio)
        else (img_overlays[-1][2] + args.audio_skip)
    )
    out = ffmpeg.output(
        overlays,
        input_audio,
        args.output,
        t=total_duration,
        shortest=None,
        vcodec="libx264",
        acodec="aac",
        r=args.fps,
        pix_fmt="yuv420p",
    )
    out.run(overwrite_output=True)
    for img_fn, _, _ in img_overlays:
        try:
            os.remove(img_fn)
        except OSError:
            pass
    print("Generated", args.output)


if __name__ == "__main__":
    main()
