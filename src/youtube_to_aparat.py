#!/usr/bin/env python3
"""
Download a video from YouTube and upload it to Aparat with the same metadata.

Uses the video's YouTube title, description, and tags (when available) and
uploads to Aparat with the same title, description, tags, and optional
playlist. Requires yt-dlp for download and Aparat cookies (see upload-aparat.py).

Usage:
  python3 src/youtube_to_aparat.py "https://www.youtube.com/watch?v=VIDEO_ID"
  python3 src/youtube_to_aparat.py "https://www.youtube.com/watch?v=VIDEO_ID" --playlist "17208565"
  python3 src/youtube_to_aparat.py "https://youtu.be/VIDEO_ID" --playlist "تلاوت قرآن" --visibility public

Options:
  --playlist    Aparat playlist ID (numeric) or playlist name (same as on YouTube if you mirror).
  --visibility  public (default) or private.
  --output-dir  Where to save the downloaded file (default: tmp/).
  --keep        Keep the downloaded file after upload (default: delete it).
  --cookies     Path to Aparat cookies.txt (default: www.aparat.com_cookies.txt or cookies.txt).
  --yt-dlp      Path to yt-dlp (default: yt-dlp from PATH).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from AparatUploader.aparat import AparatUploader


def get_yt_dlp_metadata(yt_dlp: str, url: str) -> dict:
    """Run yt-dlp --dump-json and return title, description, tags."""
    out = subprocess.run(
        [yt_dlp, "--dump-json", "--no-download", "--", url],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO_ROOT,
    )
    if out.returncode != 0:
        raise RuntimeError("yt-dlp metadata failed: %s" % (out.stderr or out.stdout or "unknown"))
    data = json.loads(out.stdout)
    title = (data.get("title") or "").strip() or "Untitled"
    description = (data.get("description") or "").strip()
    tags_raw = data.get("tags") or []
    if isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if t]
    else:
        tags = []
    return {"title": title, "description": description, "tags": tags}


def download_with_yt_dlp(yt_dlp: str, url: str, out_path_base: str) -> str:
    """Download url to out_path_base.%(ext)s using yt-dlp. Returns path to the created file."""
    cmd = [
        yt_dlp,
        "-f", "bv*[ext=mp4]+ba/bv*+ba/best[ext=mp4]/best",
        "--no-part",
        "-o", out_path_base + ".%(ext)s",
        "--",
        url,
    ]
    r = subprocess.run(cmd, cwd=REPO_ROOT, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError("yt-dlp download failed (exit %d)" % r.returncode)
    for ext in (".mp4", ".mkv", ".webm"):
        p = out_path_base + ext
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("Downloaded file not found under %s" % out_path_base)


def progress_callback(file_chunk, fraction_completed):
    print("\rAparat upload: %s" % ("%.1f%%" % (fraction_completed * 100)), end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Download a YouTube video and upload it to Aparat with the same title, description, and tags.",
    )
    parser.add_argument("youtube_url", help="YouTube video URL (e.g. https://www.youtube.com/watch?v=...)")
    parser.add_argument(
        "--playlist", "-p",
        default="",
        help="Aparat playlist ID (numeric) or playlist name (e.g. same as your YouTube playlist).",
    )
    parser.add_argument(
        "--visibility", "-v",
        choices=("public", "private"),
        default="public",
        help="Aparat visibility (default: public).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save the downloaded file (default: tmp/).",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the downloaded file after uploading to Aparat.",
    )
    parser.add_argument(
        "--cookies", "-c",
        default=None,
        help="Path to Aparat cookies.txt (default: www.aparat.com_cookies.txt or cookies.txt in repo root).",
    )
    parser.add_argument(
        "--yt-dlp",
        default="yt-dlp",
        help="Path to yt-dlp (default: yt-dlp from PATH).",
    )
    args = parser.parse_args()

    url = args.youtube_url.strip()
    if not url:
        parser.error("Provide a YouTube video URL.")

    out_dir = args.output_dir or os.path.join(REPO_ROOT, "tmp")
    os.makedirs(out_dir, exist_ok=True)

    print("Fetching YouTube metadata (title, description, tags)...")
    try:
        meta = get_yt_dlp_metadata(args.yt_dlp, url)
    except Exception as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)
    print("  Title: %s" % meta["title"][:80])
    print("  Tags: %s" % (", ".join(meta["tags"][:10]) if meta["tags"] else "(none)"))

    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in meta["title"])[:80]
    out_path_base = os.path.join(out_dir, "youtube_to_aparat_%s" % safe_title[:50])
    print("Downloading video...")
    try:
        out_path = download_with_yt_dlp(args.yt_dlp, url, out_path_base)
    except Exception as e:
        print("Error: %s" % e, file=sys.stderr)
        sys.exit(1)
    print("  Saved: %s" % out_path)

    cookies_path = args.cookies
    if not cookies_path:
        for name in ("www.aparat.com_cookies.txt", "cookies.txt"):
            candidate = os.path.join(REPO_ROOT, name)
            if os.path.isfile(candidate):
                cookies_path = candidate
                break
    if not cookies_path or not os.path.isfile(cookies_path):
        print("Missing Aparat cookies file. Export cookies from browser (see upload-aparat.py docstring).", file=sys.stderr)
        print("Default paths: www.aparat.com_cookies.txt or cookies.txt in project root.", file=sys.stderr)
        sys.exit(1)

    tags_str = "-".join(meta["tags"]) if meta["tags"] else "فیلم-آپارات-ویدیو"
    playlist_val = (args.playlist or "").strip()
    video_pass = "0" if args.visibility == "public" else "1"

    ap = AparatUploader(cookies_path)
    upload_kw = dict(
        videopath=out_path,
        title=meta["title"],
        description=meta["description"],
        progress_callback=progress_callback,
        tags=tags_str,
        video_pass=video_pass,
        category="",
    )
    if playlist_val.isdigit() and playlist_val:
        upload_kw["playlist"] = playlist_val
        upload_kw["playlistid"] = [playlist_val]
    elif playlist_val:
        upload_kw["new_playlist"] = playlist_val
        upload_kw["playlist_temp"] = playlist_val
        upload_kw["playlistid"] = ""

    print("Uploading to Aparat...")
    try:
        ap.upload(**upload_kw)
    except Exception as e:
        print("\nUpload failed: %s" % e, file=sys.stderr)
        if not args.keep:
            try:
                os.remove(out_path)
            except OSError:
                pass
        sys.exit(1)
    print("\nUpload finished.")

    if not args.keep:
        try:
            os.remove(out_path)
            print("Removed temporary file: %s" % out_path)
        except OSError:
            print("Could not remove temporary file: %s" % out_path, file=sys.stderr)


if __name__ == "__main__":
    main()
