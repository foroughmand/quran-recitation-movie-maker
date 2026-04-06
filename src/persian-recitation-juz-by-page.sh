#!/usr/bin/env zsh
#
# Juz-by-Juz Persian recitation movie maker, PAGE-BY-PAGE layout.
# - Uses create_movie_persian_juz_by_page.py (full page shown, current ayah highlighted, only that ayah's translation).
# - Uses Tanzil Parhizgar recitation by default (configurable via --recitation_template).
# - Background videos fully managed via src/bg_admin.py (same logic as persian-recitation-juz.sh):
#   * data/persian-recitation/bg_urls.txt (URLs or local paths)
#   * State in tmp/bg_videos/state_juz_page.txt (name=juz_page)
#   * Skips 2 minutes at start and end of each background file
#   * Pre-downloads next background in a separate terminal when possible
#
# Usage:
#   export j=30   # or set juz number
#   zsh src/persian-recitation-juz-by-page.sh
#   # or
#   zsh src/persian-recitation-juz-by-page.sh 30

setopt KSH_ARRAYS
set -e

[ -n "$ZSH_VERSION" ] && setopt KSH_ARRAYS 2>/dev/null
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
REPO_ROOT="$SCRIPT_DIR"
cd "$REPO_ROOT"

# --- Juz number: 1–30 ---
if [ -n "$1" ]; then
  j="$1"
elif [ -z "${j:-}" ]; then
  echo "Usage: set juz number, e.g.:  export j=30   OR   zsh src/persian-recitation-juz-by-page.sh 30"
  j=30
fi
JUZ_INDEX="$j"
if ! [ "$JUZ_INDEX" -ge 1 ] 2>/dev/null || ! [ "$JUZ_INDEX" -le 30 ] 2>/dev/null; then
  echo "Error: juz number must be 1–30 (got: $JUZ_INDEX)"
  exit 1
fi

DATA_DIR="data/persian-recitation"
mkdir -p "$DATA_DIR" tmp out

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

echo "=========================================================="
echo "Juz (page-by-page): $JUZ_INDEX  |  Data dir: $DATA_DIR"
echo "=========================================================="

# ----- Background: get next file and clip start via bg_admin.py (name=juz_page, require remaining >= 1s) -----
BG_ADMIN_OUT=$(python3 src/bg_admin.py juz_page "$BG_URLS_FILE" "$BG_VIDEOS_DIR" get_next \
  --required 1 --repo-root "$REPO_ROOT" --yt-dlp "$YT_DLP" \
  --skip-start "$BG_SKIP_START" --skip-end "$BG_SKIP_END")
BG_EXIT=$?
[ "$BG_EXIT" -eq 1 ] && { echo "Reached end of background list. No more videos."; exit 0; }
[ "$BG_EXIT" -ne 0 ] && exit "$BG_EXIT"
BG_VIDEO=$(echo "$BG_ADMIN_OUT" | head -1)
BG_CLIP_START_SEC=$(echo "$BG_ADMIN_OUT" | tail -1)
[ -z "$BG_VIDEO" ] || [ ! -f "$BG_VIDEO" ] && { echo "Error: bg_admin did not return a valid file"; exit 1; }
echo "Background: $BG_VIDEO, clip_start=${BG_CLIP_START_SEC}s"

OUT_PATH="out/juz_${JUZ_INDEX}_parhizgar_by_page.mp4"

PAGE_OPTS=()
[ -n "${RECITATION_TEMPLATE:-}" ] && PAGE_OPTS+=(--recitation_template "$RECITATION_TEMPLATE")
[ -n "${FULL_BISMILLAH_INTRO:-}" ] && PAGE_OPTS+=(--full_bismillah_intro)

python3 src/create_movie_quran.py juz "$JUZ_INDEX" "$OUT_PATH" --view page \
  --translation_root "$DATA_DIR" \
  --fps 30 \
  --background_video "$BG_VIDEO" \
  --bg_clip_start "$BG_CLIP_START_SEC" \
  "${PAGE_OPTS[@]}"

# Advance used amount via bg_admin based on actual Juz video duration
JUZ_DURATION=$(LC_NUMERIC=C ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUT_PATH" 2>/dev/null || true)
JUZ_DURATION=${JUZ_DURATION:-0}
python3 src/bg_admin.py juz_page "$BG_URLS_FILE" "$BG_VIDEOS_DIR" update_used --seconds "$JUZ_DURATION" --repo-root "$REPO_ROOT"
echo "State saved via bg_admin (juz_page)."

echo "File saved to $OUT_PATH. For next juz: export j=\$((j+1)) and run again."

