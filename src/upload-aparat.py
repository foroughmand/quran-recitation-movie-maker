#!/usr/bin/env python3
"""
Upload a video to Aparat (aparat.com) from the command line.

Credentials (cookies):
  Aparat uses browser cookies to authenticate. You do not create an "API key";
  you export cookies while logged in.

  1. Install a "cookies.txt" browser extension:
     - Chrome: https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
     - Firefox: https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/
     - Or: https://github.com/hrdl-github/cookies-txt

  2. In the browser, log in to https://www.aparat.com with your account.

  3. Go to https://www.aparat.com/dashboard (or stay on aparat.com).

  4. Use the extension to export cookies for aparat.com. Save the file as
     e.g. www.aparat.com_cookies.txt or cookies.txt in the project root.

  5. Run this script with --cookies path/to/cookies.txt (or leave default).

Usage:
  python3 src/upload-aparat.py --file out/video.mp4 --title "عنوان" --description "توضیحات" --visibility public --playlist "17208565"
  python3 src/upload-aparat.py -f out/video.mp4 -t "عنوان" -d "توضیحات" -v public -p 17208565
  python3 src/upload-aparat.py --file out/video.mp4 59   # auto title/description from sura 59
"""
import argparse
import os
import sys

# Add repo root so AparatUploader can be imported
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from AparatUploader.aparat import AparatUploader


def to_hindi_numerals(number):
    """Convert Western digits to Eastern Arabic (Hindi) numerals."""
    hindi_digits = "۰١٢٣۴۵۶٧٨٩"
    return "".join(hindi_digits[int(d)] if d.isdigit() else d for d in str(number))


def fetch_surah_data():
    """Fetch surah metadata from Quran.com API (v4)."""
    import requests
    url = "https://api.quran.com/api/v4/chapters"
    response = requests.get(url, headers={"Accept": "application/json"}, timeout=15)
    response.raise_for_status()
    chapters = response.json().get("chapters", [])
    return {
        ch["id"]: {
            "name": ch["name_arabic"],
            "latin": ch["name_simple"],
            "english": ch["translated_name"]["name"],
        }
        for ch in chapters
    }


def get_video_config_from_sura(file_path: str, sura_index: int, reciter: str = "ادریس ابکر") -> dict:
    """Build video metadata from sura index (Quran.com API)."""
    sura_data = fetch_surah_data()
    sura = sura_data.get(sura_index)
    if not sura:
        raise ValueError(f"Surah index {sura_index} not found.")
    sura_name = sura["name"]
    title = f"تلاوت سوره {sura_name} - {reciter}"
    description = (
        f"تلاوت سوره {sura_name} ({to_hindi_numerals(sura_index)}) - ترتیل\n"
        f"قاری: {reciter}\n"
        f"با تصویر پس‌زمینه طبیعت"
    )
    return {
        "video_path": file_path,
        "title": title,
        "description": description,
        "tags": ["تلاوت قرآن", f"سوره {sura_name}", reciter],
        "playlist": "17208565",
        "visibility": "public",
    }


def progress_callback(file_chunk, fraction_completed):
    print(f"\rPercent complete: {fraction_completed:.1%}", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Upload a video to Aparat. See script docstring for how to get cookies.",
    )
    parser.add_argument("--file", "-f", help="Video file path to upload.")
    parser.add_argument("--title", "-t", help="Video title.")
    parser.add_argument("--description", "-d", default="", help="Video description.")
    parser.add_argument(
        "--visibility",
        "-v",
        choices=("public", "private"),
        default="public",
        help="public = share video, private = do not share (default: public).",
    )
    parser.add_argument(
        "--playlist",
        "-p",
        default="",
        help="Aparat playlist ID (numeric) or name to add the video to.",
    )
    parser.add_argument(
        "--category",
        default="",
        help="Aparat category ID (e.g. 6 for مذهبی). Empty = default.",
    )
    parser.add_argument(
        "--tags",
        default="",
        help="Tags separated by hyphen, e.g. تلاوت-قرآن-سوره (minimum 3 tags recommended).",
    )
    parser.add_argument(
        "--cookies",
        "-c",
        default=None,
        help="Path to cookies.txt (default: www.aparat.com_cookies.txt or cookies.txt in repo root).",
    )
    parser.add_argument(
        "sura_index",
        nargs="?",
        type=int,
        default=None,
        help="Optional: sura number for auto title/description (use with --file).",
    )
    parser.add_argument(
        "file_positional",
        nargs="?",
        default=None,
        help="Video file path (alternative to --file).",
    )
    args = parser.parse_args()

    file_path = args.file or args.file_positional
    if not file_path:
        parser.error("Provide video file via --file or as positional argument.")
    if not os.path.isfile(file_path):
        parser.error(f"File not found: {file_path}")

    if args.sura_index is not None and not args.title:
        config = get_video_config_from_sura(file_path, args.sura_index)
    else:
        config = {
            "video_path": file_path,
            "title": args.title or os.path.splitext(os.path.basename(file_path))[0],
            "description": args.description or "",
            "tags": args.tags if args.tags else "فیلم-آپارات-ویدیو",
            "playlist": args.playlist or "",
            "visibility": args.visibility,
        }

    # video_pass: '0' = share (public), '1' = do not share (private)
    video_pass = "0" if config["visibility"] == "public" else "1"

    cookies_path = args.cookies
    if not cookies_path:
        for name in ("www.aparat.com_cookies.txt", "cookies.txt"):
            candidate = os.path.join(REPO_ROOT, name)
            if os.path.isfile(candidate):
                cookies_path = candidate
                break
    if not cookies_path or not os.path.isfile(cookies_path):
        print("Missing cookies file. Export cookies from browser (see script docstring).", file=sys.stderr)
        print("Default paths: www.aparat.com_cookies.txt or cookies.txt in project root.", file=sys.stderr)
        print("Or pass --cookies path/to/cookies.txt", file=sys.stderr)
        sys.exit(1)

    ap = AparatUploader(cookies_path)
    tags_str = config["tags"] if isinstance(config["tags"], str) else "-".join(config["tags"])
    playlist_val = config.get("playlist", "")
    # Aparat API: use new_playlist for playlist name (create/add); use playlistid only for numeric ID
    is_numeric_id = playlist_val.isdigit() if isinstance(playlist_val, str) else False
    if is_numeric_id:
        ap.upload(
            videopath=config["video_path"],
            title=config["title"],
            description=config["description"],
            progress_callback=progress_callback,
            tags=tags_str,
            playlist=playlist_val,
            playlistid=[playlist_val],
            video_pass=video_pass,
            category=args.category or "",
        )
    else:
        ap.upload(
            videopath=config["video_path"],
            title=config["title"],
            description=config["description"],
            progress_callback=progress_callback,
            tags=tags_str,
            new_playlist=playlist_val or "",
            playlist_temp=playlist_val or "",
            playlistid="",
            video_pass=video_pass,
            category=args.category or "",
        )
    print("\nUpload finished.")


if __name__ == "__main__":
    main()
