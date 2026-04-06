#!/usr/bin/env python3
"""
Background video admin: manage a list of background URLs/files, state (index + used seconds),
downloads into a storage folder (under tmp/), and optional pre-download of next in a new window.

Usage:
  get_next — return path to current bg file and start_sec; ensure required_remaining_sec available.
  update_used — add used seconds to state.

  python3 src/bg_admin.py NAME BG_FILE_LIST STORAGE_FOLDER get_next [--required SEC] [--repo-root PATH] [--yt-dlp PATH]
  python3 src/bg_admin.py NAME BG_FILE_LIST STORAGE_FOLDER update_used --seconds SEC

Output for get_next (stdout): two lines — absolute file path, then start_sec. Exit 0 = success, 1 = no more videos.
"""

import argparse
import glob
import os
import subprocess
import sys
import time


def ensure_storage_under_tmp(storage_folder: str, repo_root: str) -> str:
    """Resolve storage_folder; must be under tmp (repo_root/tmp/...). Creates it if missing."""
    if not os.path.isabs(storage_folder):
        storage_folder = os.path.join(repo_root, storage_folder)
    storage_folder = os.path.normpath(os.path.abspath(storage_folder))
    tmp_dir = os.path.normpath(os.path.abspath(os.path.join(repo_root, "tmp")))
    try:
        common = os.path.commonpath([storage_folder, tmp_dir])
    except ValueError:
        common = ""
    if common != tmp_dir and storage_folder != tmp_dir:
        sys.stderr.write(f"Error: storage folder must be under tmp (got {storage_folder})\n")
        sys.exit(2)
    os.makedirs(storage_folder, exist_ok=True)
    return storage_folder


def load_list(path: str) -> list[str]:
    """Load lines from file; strip, skip empty and # comments. 1-based index = line number."""
    with open(path, "r", encoding="utf-8") as f:
        lines = []
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lines.append(line)
        return lines


def load_state(state_path: str) -> tuple[int, float]:
    """Return (index, used_seconds). Default (1, 0.0)."""
    if not os.path.isfile(state_path):
        return 1, 0.0
    with open(state_path, "r", encoding="utf-8") as f:
        line = f.read().strip()
    parts = line.split()
    if len(parts) < 2:
        return 1, 0.0
    try:
        return int(parts[0]), float(parts[1])
    except ValueError:
        return 1, 0.0


def save_state(state_path: str, index: int, used_seconds: float) -> None:
    with open(state_path, "w", encoding="utf-8") as f:
        f.write(f"{index} {used_seconds}\n")


def is_url(entry: str) -> bool:
    return entry.startswith("http://") or entry.startswith("https://")


def resolve_bg_video(storage_folder: str, index: int) -> str | None:
    """Return path to bg_{index}.* file if present."""
    base = os.path.join(storage_folder, f"bg_{index}")
    if os.path.isfile(base + ".mp4"):
        return base + ".mp4"
    for p in glob.glob(base + ".*"):
        if os.path.isfile(p):
            return p
    return None


def get_duration_sec(path: str) -> float | None:
    """Return duration in seconds via ffprobe, or None."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return float(out.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def download_url(
    storage_folder: str,
    index: int,
    url: str,
    yt_dlp: str,
    repo_root: str,
) -> bool:
    """Download URL to storage_folder/bg_{index}.mp4 (or other format). Blocking. Returns True on success."""
    out_base = os.path.join(storage_folder, f"bg_{index}")
    cmd = [
        yt_dlp,
        "-f", "bv*[height=1080]+ba/bv*+ba/best",
        "-o", out_base + ".mp4",
        "--no-part",
        "--",
        url,
    ]
    for attempt in range(1, 4):
        sys.stderr.write(f"  [yt-dlp] attempt {attempt}/3: bg_{index}\n")
        try:
            r = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=3600)
            if r.returncode == 0 and resolve_bg_video(storage_folder, index):
                return True
        except subprocess.TimeoutExpired:
            pass
        if attempt < 3:
            time.sleep(60)
    return False


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_for_download(
    storage_folder: str,
    index: int,
    timeout_sec: int,
    yt_dlp: str,
    repo_root: str,
    url: str,
) -> bool:
    """Wait for bg_{index} to exist and have valid duration; if pid gone, start blocking download."""
    pid_path = os.path.join(storage_folder, f".downloading_{index}.pid")
    elapsed = 0
    while elapsed < timeout_sec:
        path = resolve_bg_video(storage_folder, index)
        if path and get_duration_sec(path) is not None:
            return True
        if os.path.isfile(pid_path):
            try:
                with open(pid_path, "r") as f:
                    pid = int(f.read().strip())
                if pid_alive(pid):
                    time.sleep(5)
                    elapsed += 5
                    continue
            except (ValueError, OSError):
                pass
            try:
                os.remove(pid_path)
            except OSError:
                pass
        # Start blocking download
        if download_url(storage_folder, index, url, yt_dlp, repo_root):
            return True
        return False
    return False


def start_background_download(
    storage_folder: str,
    index: int,
    url: str,
    yt_dlp: str,
    repo_root: str,
) -> None:
    """Start download in a new terminal window (non-blocking) or as subprocess; write pid to .downloading_{index}.pid."""
    pid_path = os.path.join(storage_folder, f".downloading_{index}.pid")
    if resolve_bg_video(storage_folder, index):
        return
    if os.path.isfile(pid_path):
        try:
            with open(pid_path, "r") as f:
                pid = int(f.read().strip())
            if pid_alive(pid):
                return
        except (ValueError, OSError):
            pass
        try:
            os.remove(pid_path)
        except OSError:
            pass

    out_base = os.path.join(storage_folder, f"bg_{index}.mp4")
    cmd_flat = f'cd "{repo_root}" && "{yt_dlp}" -f "bv*[height=1080]+ba/bv*+ba/best" -o "{out_base}" --no-part -- "{url}"'
    # Try new terminal (non-blocking for caller)
    for term in ["gnome-terminal", "konsole", "xterm", "x-terminal-emulator"]:
        try:
            if subprocess.run(["which", term], capture_output=True, check=False).returncode != 0:
                continue
        except Exception:
            continue
        if term == "gnome-terminal":
            run = ["gnome-terminal", "--", "bash", "-c", cmd_flat + "; echo ''; read -p 'Press Enter to close'"]
        elif term == "konsole":
            run = ["konsole", "-e", "bash", "-c", cmd_flat]
        elif term == "xterm":
            run = ["xterm", "-e", "bash", "-c", cmd_flat]
        else:
            run = [term, "-e", "bash", "-c", cmd_flat]
        try:
            p = subprocess.Popen(run, cwd=repo_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with open(pid_path, "w") as f:
                f.write(str(p.pid))
            return
        except Exception:
            continue
    # Fallback: background process in same shell
    try:
        p = subprocess.Popen(
            [yt_dlp, "-f", "bv*[height=1080]+ba/bv*+ba/best", "-o", out_base, "--no-part", "--", url],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(pid_path, "w") as f:
            f.write(str(p.pid))
    except Exception:
        pass


def resolve_local_path(entry: str, repo_root: str) -> str:
    """Absolute path for a local file entry (relative to repo or absolute)."""
    entry = entry.strip()
    if os.path.isabs(entry):
        return entry
    return os.path.normpath(os.path.join(repo_root, entry))


def action_get_next(
    name: str,
    bg_file_list: str,
    storage_folder: str,
    repo_root: str,
    yt_dlp: str,
    required_remaining: float,
    skip_start: float,
    skip_end: float,
) -> None:
    state_path = os.path.join(storage_folder, f"state_{name}.txt")
    entries = load_list(bg_file_list)
    if not entries:
        sys.stderr.write("Error: no entries in bg file list\n")
        sys.exit(1)

    index, used_seconds = load_state(state_path)
    if index < 1:
        index = 1
    num = len(entries)

    while index <= num:
        entry = entries[index - 1]
        if is_url(entry):
            path = resolve_bg_video(storage_folder, index)
            if not path or not os.path.isfile(path):
                sys.stderr.write(f"Background {index} not found; downloading (blocking)...\n")
                if not wait_for_download(storage_folder, index, 600, yt_dlp, repo_root, entry):
                    if not download_url(storage_folder, index, entry, yt_dlp, repo_root):
                        sys.stderr.write(f"Download failed for URL {index}; trying next.\n")
                        index += 1
                        used_seconds = 0.0
                        save_state(state_path, index, used_seconds)
                        continue
                path = resolve_bg_video(storage_folder, index)
        else:
            path = resolve_local_path(entry, repo_root)
            if not os.path.isfile(path):
                sys.stderr.write(f"Background file not found: {path}\n")
                index += 1
                used_seconds = 0.0
                save_state(state_path, index, used_seconds)
                continue

        duration = get_duration_sec(path)
        if duration is None or duration <= 0:
            sys.stderr.write(f"Invalid file bg_{index}; trying next.\n")
            if is_url(entry) and path.startswith(storage_folder):
                try:
                    os.remove(path)
                except OSError:
                    pass
            index += 1
            used_seconds = 0.0
            save_state(state_path, index, used_seconds)
            continue

        usable = max(0.0, duration - skip_start - skip_end)
        remaining = usable - used_seconds
        if remaining >= required_remaining:
            start_sec = skip_start + used_seconds
            # Pre-download next
            next_idx = index + 1
            if next_idx <= num and is_url(entries[next_idx - 1]):
                start_background_download(storage_folder, next_idx, entries[next_idx - 1], yt_dlp, repo_root)
            print(os.path.abspath(path))
            print(start_sec)
            return

        sys.stderr.write(f"bg_{index} has {remaining}s left (need {required_remaining}s); switching to next.\n")
        if is_url(entry) and path.startswith(storage_folder):
            try:
                os.remove(path)
            except OSError:
                pass
        index += 1
        used_seconds = 0.0
        save_state(state_path, index, used_seconds)

        if index <= num and is_url(entries[index - 1]):
            path_next = resolve_bg_video(storage_folder, index)
            if not path_next or not os.path.isfile(path_next):
                sys.stderr.write(f"Waiting for bg_{index} (up to 10 min)...\n")
                if not wait_for_download(storage_folder, index, 600, yt_dlp, repo_root, entries[index - 1]):
                    if not download_url(storage_folder, index, entries[index - 1], yt_dlp, repo_root):
                        sys.stderr.write("Download failed; will try next in loop.\n")

    sys.stderr.write("Reached end of background list. No more videos.\n")
    sys.exit(1)


def action_update_used(
    name: str,
    storage_folder: str,
    seconds: float,
) -> None:
    state_path = os.path.join(storage_folder, f"state_{name}.txt")
    index, used_seconds = load_state(state_path)
    used_seconds += seconds
    save_state(state_path, index, used_seconds)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Background video admin: get next bg file + start time, or update used time.",
    )
    ap.add_argument("name", help="State name (e.g. sura, juz); state stored as state_<name>.txt in storage folder.")
    ap.add_argument("bg_file_list", help="Path to file with one URL or file path per line (# = comment).")
    ap.add_argument("storage_folder", help="Folder under tmp/ for downloads and state.")
    ap.add_argument("action", choices=["get_next", "update_used"], help="Action to run.")
    ap.add_argument("--required", type=float, default=0.0, help="Required remaining seconds (get_next). Default 0 = any remaining.")
    ap.add_argument("--seconds", type=float, default=None, help="Seconds used (update_used).")
    ap.add_argument("--repo-root", default=".", help="Repo root to resolve storage and relative paths.")
    ap.add_argument("--yt-dlp", default="yt-dlp", help="Path to yt-dlp.")
    ap.add_argument("--skip-start", type=float, default=120.0, help="Seconds to skip at start of each file.")
    ap.add_argument("--skip-end", type=float, default=120.0, help="Seconds to skip at end of each file.")

    args = ap.parse_args()
    repo_root = os.path.abspath(args.repo_root)
    storage_folder = ensure_storage_under_tmp(args.storage_folder, repo_root)

    if args.action == "get_next":
        if not os.path.isfile(args.bg_file_list):
            sys.stderr.write(f"Error: bg file list not found: {args.bg_file_list}\n")
            sys.exit(2)
        yt_dlp = args.yt_dlp
        if not os.path.isabs(yt_dlp):
            yt_dlp = os.path.join(repo_root, yt_dlp)
        if os.path.isdir(yt_dlp):
            yt_dlp = os.path.join(yt_dlp, "yt-dlp")
        if not os.path.isfile(yt_dlp) and not os.path.isfile(yt_dlp + ".py"):
            # try PATH
            yt_dlp = "yt-dlp"
        action_get_next(
            args.name,
            os.path.abspath(args.bg_file_list),
            storage_folder,
            repo_root,
            yt_dlp,
            args.required,
            args.skip_start,
            args.skip_end,
        )
    else:
        if args.seconds is None:
            sys.stderr.write("Error: update_used requires --seconds\n")
            sys.exit(2)
        action_update_used(args.name, storage_folder, args.seconds)


if __name__ == "__main__":
    main()
