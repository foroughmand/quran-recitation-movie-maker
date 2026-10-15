#!/usr/bin/env python3
"""
Download a video from Telewebion and upload it to YouTube with matching metadata.

By default this script:
  1. Uses yt-dlp metadata from the Telewebion page.
  2. Downloads the source video with ~/Downloads/yt-dlp-src/yt-dlp.sh.
  3. Runs yt-dlp under `conda run -n dev2`.
  4. Uploads to YouTube with the existing OAuth flow used by upload-videos.py.

You can override the title, description, tags, playlist, visibility, and more.
If you do not pass overrides, the script uses the best available metadata from
Telewebion.

Usage:
  python3 src/telewebion_to_youtube.py "https://telewebion.com/episode/0x..."
  python3 src/telewebion_to_youtube.py "https://telewebion.com/episode/0x..." --title "New title"
  python3 src/telewebion_to_youtube.py "https://telewebion.com/episode/0x..." --playlist "My playlist" --visibility public
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

from tqdm import tqdm


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_YT_DLP = os.path.expanduser("~/Downloads/yt-dlp-src/yt-dlp.sh")
DEFAULT_CONDA_ENV = "dev2"
OUT_TIME_RE = re.compile(r"out_time_ms=(\d+)")


def load_upload_module():
    module_path = os.path.join(REPO_ROOT, "src", "upload-videos.py")
    spec = importlib.util.spec_from_file_location("upload_videos_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load src/upload-videos.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_yt_dlp_cmd(yt_dlp_path: str, conda_env: str) -> list[str]:
    cmd = []
    if conda_env:
        cmd.extend(["conda", "run", "--no-capture-output", "-n", conda_env])
    cmd.append(yt_dlp_path)
    return cmd


def run_yt_dlp(yt_dlp_cmd: list[str], extra_args: list[str], timeout: int, capture_output: bool) -> subprocess.CompletedProcess:
    return subprocess.run(
        yt_dlp_cmd + extra_args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=capture_output,
        timeout=timeout,
    )


def build_conda_media_cmd(conda_env: str, executable: str) -> list[str]:
    cmd = []
    if conda_env:
        cmd.extend(["conda", "run", "--no-capture-output", "-n", conda_env])
    cmd.append(executable)
    return cmd


def create_tqdm_progress(label: str) -> tqdm:
    return tqdm(
        total=100.0,
        desc=label,
        unit="%",
        leave=False,
        dynamic_ncols=True,
        bar_format="{l_bar}{bar}| {n:6.2f}/{total:.0f}%",
    )


def pick_playlist_name(data: dict) -> str:
    candidates = [
        data.get("playlist_title"),
        data.get("playlist"),
        data.get("series"),
        data.get("album"),
        data.get("channel"),
        data.get("uploader"),
        data.get("creator"),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def build_tags(data: dict) -> list[str]:
    values = []
    for key in ("tags", "categories"):
        raw = data.get(key) or []
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
    for key in ("channel", "uploader", "creator", "series"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())

    seen = set()
    deduped = []
    for value in values:
        lowered = value.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(value)
    return deduped[:50]


def get_source_metadata(yt_dlp_cmd: list[str], url: str) -> dict:
    out = run_yt_dlp(
        yt_dlp_cmd,
        ["--dump-json", "--no-download", "--", url],
        timeout=120,
        capture_output=True,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr or out.stdout or "yt-dlp metadata failed")

    data = json.loads(out.stdout)
    title = (data.get("title") or "").strip() or "Untitled"
    description = (data.get("description") or "").strip()
    tags = build_tags(data)
    playlist = pick_playlist_name(data)
    return {
        "raw": data,
        "title": title,
        "description": description,
        "tags": tags,
        "playlist": playlist,
    }


def sanitize_basename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in value).strip()
    return safe[:80] or "telewebion_video"


def download_video(yt_dlp_cmd: list[str], url: str, out_path_base: str) -> str:
    cmd = [
        "-f", "bv*[ext=mp4]+ba/bv*+ba/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", out_path_base + ".%(ext)s",
        "--",
        url,
    ]
    result = run_yt_dlp(yt_dlp_cmd, cmd, timeout=7200, capture_output=False)
    if result.returncode != 0:
        raise RuntimeError("yt-dlp download failed (exit %d)" % result.returncode)

    for ext in (".mp4", ".mkv", ".webm"):
        candidate = out_path_base + ext
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError("Downloaded file not found under %s" % out_path_base)


def normalize_for_youtube(input_path: str, output_path: str, duration_seconds: float, conda_env: str) -> str:
    ffmpeg_cmd = build_conda_media_cmd(conda_env, "ffmpeg")
    cmd = ffmpeg_cmd + [
        "-y",
        "-i", input_path,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-af", "aresample=async=1:first_pts=0",
        "-movflags", "+faststart",
        "-fflags", "+genpts",
        "-avoid_negative_ts", "make_zero",
        "-max_interleave_delta", "0",
        "-progress", "pipe:1",
        "-nostats",
        output_path,
    ]
    process = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    output_lines = []
    progress_bar = create_tqdm_progress("Normalize") if duration_seconds > 0 else None
    last_progress = 0.0
    assert process.stdout is not None
    try:
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            output_lines.append(line)
            match = OUT_TIME_RE.search(line)
            if match and duration_seconds > 0:
                try:
                    out_time_ms = int(match.group(1))
                    target = min(out_time_ms / 1_000_000.0 / duration_seconds, 1.0) * 100.0
                    increment = max(0.0, target - last_progress)
                    if progress_bar is not None and increment:
                        progress_bar.update(increment)
                        last_progress = target
                    continue
                except ValueError:
                    pass
            if line == "progress=end":
                if progress_bar is not None and last_progress < 100.0:
                    progress_bar.update(100.0 - last_progress)
                    last_progress = 100.0
                continue
            if line and not line.startswith(("frame=", "fps=", "stream_", "bitrate=", "total_size=", "out_time_us=", "out_time_ms=", "out_time=", "dup_frames=", "drop_frames=", "speed=", "progress=")):
                if progress_bar is not None:
                    progress_bar.clear()
                print(line)
                if progress_bar is not None:
                    progress_bar.refresh()
    finally:
        process.stdout.close()
        if progress_bar is not None:
            if last_progress < 100.0:
                progress_bar.update(100.0 - last_progress)
            progress_bar.close()

    returncode = process.wait(timeout=7200)
    if returncode != 0:
        tail = "\n".join(output_lines[-20:])
        raise RuntimeError("ffmpeg normalization failed (exit %d)\n%s" % (returncode, tail))
    if not os.path.isfile(output_path):
        raise FileNotFoundError("Normalized file not created: %s" % output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Download a Telewebion video and upload it to YouTube using Telewebion metadata by default.",
    )
    parser.add_argument("telewebion_url", help="Telewebion video URL.")
    parser.add_argument("--title", "-t", default="", help="Override video title.")
    parser.add_argument("--description", "-d", default="", help="Override video description.")
    parser.add_argument(
        "--playlist",
        "-p",
        action="append",
        default=[],
        help="YouTube playlist name to add the video to. Repeat to add multiple playlists.",
    )
    parser.add_argument("--tag", dest="tags", action="append", default=[], help="Override/add a tag. Repeat as needed.")
    parser.add_argument(
        "--visibility",
        "-v",
        choices=("public", "private", "unlisted"),
        default="private",
        help="YouTube visibility (default: private).",
    )
    parser.add_argument(
        "--category",
        default="22",
        help="YouTube category ID (default: 22).",
    )
    parser.add_argument(
        "--made-for-kids",
        action="store_true",
        help="Mark the upload as made for kids.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save the downloaded file (default: tmp/).",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the downloaded file after uploading to YouTube.",
    )
    parser.add_argument(
        "--fix-only",
        action="store_true",
        help="Download and normalize the video for YouTube, but do not upload it.",
    )
    parser.add_argument(
        "--yt-dlp",
        default=DEFAULT_YT_DLP,
        help="Path to yt-dlp wrapper (default: ~/Downloads/yt-dlp-src/yt-dlp.sh).",
    )
    parser.add_argument(
        "--conda-env",
        default=DEFAULT_CONDA_ENV,
        help="Conda environment to run yt-dlp under (default: dev2). Use empty string to disable conda run.",
    )
    args = parser.parse_args()

    url = args.telewebion_url.strip()
    if not url:
        parser.error("Provide a Telewebion video URL.")

    yt_dlp_path = os.path.expanduser(args.yt_dlp)
    if not os.path.isfile(yt_dlp_path):
        parser.error("yt-dlp wrapper not found: %s" % yt_dlp_path)

    out_dir = args.output_dir or os.path.join(REPO_ROOT, "tmp")
    os.makedirs(out_dir, exist_ok=True)

    yt_dlp_cmd = build_yt_dlp_cmd(yt_dlp_path, args.conda_env.strip())

    print("Fetching Telewebion metadata...")
    try:
        meta = get_source_metadata(yt_dlp_cmd, url)
    except Exception as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    final_title = args.title.strip() or meta["title"]
    final_description = args.description if args.description else meta["description"]
    final_playlists = args.playlist[:] if args.playlist else ([meta["playlist"]] if meta["playlist"] else [])
    final_tags = args.tags[:] if args.tags else meta["tags"]

    print("  Title: %s" % final_title[:100])
    print("  Playlist: %s" % (", ".join(final_playlists) if final_playlists else "(none)"))
    print("  Tags: %s" % (", ".join(final_tags[:10]) if final_tags else "(none)"))

    out_path_base = os.path.join(out_dir, "telewebion_to_youtube_%s" % sanitize_basename(final_title)[:50])
    print("Downloading video from Telewebion...")
    try:
        out_path = download_video(yt_dlp_cmd, url, out_path_base)
    except Exception as exc:
        print("Error: %s" % exc, file=sys.stderr)
        sys.exit(1)

    print("  Saved: %s" % out_path)
    normalized_path = os.path.join(out_dir, os.path.splitext(os.path.basename(out_path))[0] + "_youtube.mp4")
    print("Normalizing audio/container for YouTube...")
    try:
        upload_path = normalize_for_youtube(
            out_path,
            normalized_path,
            float(meta["raw"].get("duration") or 0.0),
            args.conda_env.strip(),
        )
    except Exception as exc:
        print("Error: %s" % exc, file=sys.stderr)
        if not args.keep:
            try:
                os.remove(out_path)
            except OSError:
                pass
        sys.exit(1)
    print("  Ready: %s" % upload_path)

    if args.fix_only:
        if not args.keep:
            try:
                os.remove(out_path)
                print("Removed temporary file: %s" % out_path)
            except OSError:
                print("Could not remove temporary file: %s" % out_path, file=sys.stderr)
        print("Fix-only complete. Normalized file: %s" % upload_path)
        return

    upload_config = {
        "video_path": upload_path,
        "title": final_title,
        "description": final_description,
        "made_for_kids": args.made_for_kids,
        "category": args.category,
        "visibility": args.visibility,
        "tags": final_tags,
        "playlist": final_playlists,
    }

    try:
        os.chdir(REPO_ROOT)
        upload_module = load_upload_module()
        youtube = upload_module.get_authenticated_service()
        upload_module.upload_video(youtube, upload_config)
    except Exception as exc:
        print("Upload failed: %s" % exc, file=sys.stderr)
        if not args.keep:
            try:
                os.remove(out_path)
            except OSError:
                pass
            try:
                if upload_path != out_path:
                    os.remove(upload_path)
            except OSError:
                pass
        sys.exit(1)

    if not args.keep:
        try:
            os.remove(out_path)
            print("Removed temporary file: %s" % out_path)
        except OSError:
            print("Could not remove temporary file: %s" % out_path, file=sys.stderr)
        try:
            if upload_path != out_path:
                os.remove(upload_path)
                print("Removed temporary file: %s" % upload_path)
        except OSError:
            print("Could not remove temporary file: %s" % upload_path, file=sys.stderr)


if __name__ == "__main__":
    main()
