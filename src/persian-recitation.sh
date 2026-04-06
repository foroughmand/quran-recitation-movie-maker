#!/usr/bin/env zsh
#
# Persian recitation movie maker (step-by-step, run each section manually).
# Uses: sura number, then downloads recitation + translation audio and Persian
# translation text (from tanzil.ir / tanzil.net), then builds a movie with
# background, Arabic ayah text, and Persian translation on screen.
#
# Usage:
#   export s=59   # or set sura number
#   bash src/persian-recitation.sh
# Optional: RECITATION_TEMPLATE="https://tanzil.net/res/audio/shateri/{sura}{ayah}.mp3" (used in Step 1 for download).
# Then run each "STEP" block below one by one (copy-paste or uncomment).
#
# Prerequisites: ffmpeg, python3, requests; data/ and font/ as in README.

setopt KSH_ARRAYS
# set -e
set -x
# Support zsh (e.g. when run as zsh persian-recitation.sh): 0-based arrays and script path
[ -n "$ZSH_VERSION" ] && setopt KSH_ARRAYS 2>/dev/null
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
REPO_ROOT="$SCRIPT_DIR"
cd "$REPO_ROOT"

# --- Sura number: set once at the start ---
# Get from first argument or use default for testing.
if [ -n "$1" ]; then
  s="$1"
elif [ -z "$s" ]; then
  echo "Usage: set sura number, e.g.:  export s=59   OR   bash src/persian-recitation.sh 59"
  echo "Then run the steps below one by one."
  s=59
fi
SURE_INDEX="$s"
# Validate 1–114
if ! [ "$SURE_INDEX" -ge 1 ] 2>/dev/null || ! [ "$SURE_INDEX" -le 114 ] 2>/dev/null; then
  echo "Error: sura number must be 1-114 (got: $SURE_INDEX)"
  exit 1
fi

# Number of ayas for this sura (from data/quran-sura-aye.txt)
AYAS=$(sed -n "${SURE_INDEX}p" data/quran-sura-aye.txt | awk '{print $2}')
DATA_DIR="data/persian-recitation"
SURE_DIR="${DATA_DIR}/sura_${SURE_INDEX}"
mkdir -p "$SURE_DIR"/{recitation_audio,translation_audio,translation_text}

# Recitation URL for download (Step 1). If RECITATION_TEMPLATE is set (e.g. https://tanzil.net/res/audio/shateri/{sura}{ayah}.mp3),
# convert to form expected by download_tanzil_sura.py (one 6-digit placeholder: 001001 -> sura+ayah).
if [ -n "${RECITATION_TEMPLATE:-}" ]; then
  RECITATION_URL="${RECITATION_TEMPLATE//\{sura\}/001}"
  RECITATION_URL="${RECITATION_URL//\{ayah\}/001}"
fi

# --- Background: one list (URLs or local file paths) in bg_urls.txt; managed by bg_admin.py ---
BG_SKIP_START=120
BG_SKIP_END=120
BG_URLS_FILE="${DATA_DIR}/bg_urls.txt"
BG_VIDEOS_DIR="tmp/bg_videos"
YT_DLP="${REPO_ROOT}/../yt-dlp"
[ -d "$YT_DLP" ] && YT_DLP="${YT_DLP}/yt-dlp"
if [ ! -f "$BG_URLS_FILE" ]; then
  echo "Error: create $BG_URLS_FILE (one YouTube URL or file path per line)"
  exit 1
fi
[ -x "$YT_DLP" ] || [ -f "$YT_DLP" ] || { echo "Error: yt-dlp not found at $YT_DLP (set YT_DLP or use ../yt-dlp)"; exit 1; }

echo "=============================================="
echo "Sura: $SURE_INDEX  |  Ayas: $AYAS  |  Data dir: $SURE_DIR"
echo "=============================================="

# =============================================================================
# STEP 1 — Download recitation and translation audio + Persian translation text
# =============================================================================
# Run this once. Audio/text will be under $SURE_DIR.
# Optional: override URLs with --recitation-url, --translation-audio-url, --translation-text-url
#
# Uncomment and run:
#
# python3 src/download_tanzil_sura.py "$SURE_INDEX" "$AYAS" "$SURE_DIR"
# Optional: RECITATION_TEMPLATE="https://tanzil.net/res/audio/shateri/{sura}{ayah}.mp3" (passed as --recitation-url with 001001 placeholder)
if [ -n "${RECITATION_URL:-}" ]; then
  python3 src/download_tanzil_sura.py --recitation-url "$RECITATION_URL" "$SURE_INDEX" "$AYAS" "$SURE_DIR"
else
  python3 src/download_tanzil_sura.py "$SURE_INDEX" "$AYAS" "$SURE_DIR"
fi

# =============================================================================
# STEP 2 — Build combined audio (recitation then translation per ayah)
# =============================================================================
# Concatenates: rec_1, trans_1, rec_2, trans_2, ... into one WAV and writes
# segment timings to a mapping file for the movie script.
# In RECITATION_ONLY=1 mode, we skip translation audio entirely so combined.wav
# has only recitation (no silent gaps from translation segments).
#
# Uncomment and run:
#
if [ -n "${RECITATION_ONLY:-}" ]; then
  echo "RECITATION_ONLY=1 → building combined.wav with recitation only (skip translation audio)"
  python3 src/build_persian_audio.py --skip-translation "$SURE_DIR" "$SURE_INDEX" "$AYAS"
else
  python3 src/build_persian_audio.py "$SURE_DIR" "$SURE_INDEX" "$AYAS"
fi

# =============================================================================
# STEP 3 — Prepare background videos
# =============================================================================
# Option A — URLs (YouTube): create data/persian-recitation/bg_urls.txt with one
#   YouTube URL per line. Step 4 will download to bg_videos/bg_1.mp4, bg_2.mp4, ...
#   (index = line number). When current file is exhausted, next is used; previous
#   file is removed. Next URL is pre-downloaded in background. yt-dlp at ../yt-dlp.
#   Or a local file path (relative to repo or absolute); it is used as-is and not removed.
# 2 min are skipped from start and end of each file.
#
# Example bg_urls.txt:
#   https://www.youtube.com/watch?v=...
#   https://www.youtube.com/watch?v=...

# =============================================================================
# STEP 4 — Create the movie (Arabic + translation text on screen)
# =============================================================================
# Audio: default = Persian translation voice only (--audio translation).
#        Set RECITATION_ONLY=1 for Arabic recitation only (no translation voice): --audio recitation
# Background: bg_urls.txt (URLs or file paths, one per line). State in tmp/bg_videos/state_sura.txt (via bg_admin.py).
# Debug: add --debug = first 3 ayahs, black background, 5 s per ayah (background not used).
#
PRJ="p-${SURE_INDEX}-tanzil"
AUDIO_MODE="${RECITATION_ONLY:+recitation}"
AUDIO_MODE="${AUDIO_MODE:-translation}"
test -f "$SURE_DIR/combined.wav" || { echo "Run Step 2 first (build combined.wav)."; exit 1; }
SURA_DURATION=$(LC_NUMERIC=C ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$SURE_DIR/combined.wav" 2>/dev/null || true)
[ -z "$SURA_DURATION" ] && { echo "Could not get duration of combined.wav"; exit 1; }

# ----- Background: get next file and clip start via bg_admin.py -----
BG_ADMIN_OUT=$(python3 src/bg_admin.py sura "$BG_URLS_FILE" "$BG_VIDEOS_DIR" get_next \
  --required "$SURA_DURATION" --repo-root "$REPO_ROOT" --yt-dlp "$YT_DLP" \
  --skip-start "$BG_SKIP_START" --skip-end "$BG_SKIP_END")
BG_EXIT=$?
[ "$BG_EXIT" -eq 1 ] && { echo "Reached end of background list. No more videos."; exit 0; }
[ "$BG_EXIT" -ne 0 ] && exit "$BG_EXIT"
BG_VIDEO=$(echo "$BG_ADMIN_OUT" | head -1)
BG_CLIP_START_SEC=$(echo "$BG_ADMIN_OUT" | tail -1)
[ -z "$BG_VIDEO" ] || [ ! -f "$BG_VIDEO" ] && { echo "Error: bg_admin did not return a valid file"; exit 1; }
echo "Background: $BG_VIDEO, clip_start=${BG_CLIP_START_SEC}s"
echo "Audio: $AUDIO_MODE (set RECITATION_ONLY=1 for Arabic recitation only)"

python3 src/create_movie_quran.py sura \
  "data/quran-simple-plain-${SURE_INDEX}.txt" \
  "$SURE_DIR/segment_mapping.txt" \
  "$SURE_DIR/combined.wav" \
  "out/${PRJ}.mp4" \
  "$BG_VIDEO" \
  "$SURE_INDEX" \
  --translation_dir "$SURE_DIR/translation_text" \
  --font "quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf" \
  --font_size 100 \
  --title "$(printf '%03d' "$SURE_INDEX") surah" \
  --title_font "quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf" \
  --title_font_size 100 \
  --size_x 1920 \
  --size_y 1080 \
  --interline 30 \
  --stroke_width 5 \
  --translation_font "font/HM_XNiloofar.ttf" \
  --translation_font_size 48 \
  --show_page \
  --bg_clip_start "$BG_CLIP_START_SEC" \
  --audio_skip 0.0 --audio "$AUDIO_MODE"

# Advance used amount via bg_admin; next run will switch to next file if this one has no time left
python3 src/bg_admin.py sura "$BG_URLS_FILE" "$BG_VIDEOS_DIR" update_used --seconds "$SURA_DURATION" --repo-root "$REPO_ROOT"
echo "State saved via bg_admin."

echo "File saved to out/${PRJ}.mp4. For next sura: export s=\$((s+1)) and run again."
