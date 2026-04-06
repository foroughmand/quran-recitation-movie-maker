#!/usr/bin/env zsh
#
# Juz-by-Juz Persian recitation movie maker using create_movie_persian_juz.py.
# - Uses Tanzil Parhizgar recitation by default (configurable via --recitation_template).
# - Keeps Persian translation TEXT on screen (from data/persian-recitation/sura_XX/translation_text).
# - Optional Persian translation VOICE per ayah (enable with --include_translation_audio in Python).
# - Full background management via src/bg_admin.py (same as persian-recitation.sh):
#   * data/persian-recitation/bg_urls.txt (URLs or local paths)
#   * State in tmp/bg_videos/state_juz.txt (name=juz)
#   * Skips 2 minutes at start and end of each background file
#   * Pre-downloads next background in a separate terminal when possible
#
# Usage:
#   export j=30   # or set juz number
#   zsh src/persian-recitation-juz.sh
#   # or
#   zsh src/persian-recitation-juz.sh 30
# Optional: RECITATION_TEMPLATE="https://tanzil.net/res/audio/shateri/{sura}{ayah}.mp3" for Shateri (default: Parhizgar).
# Optional: FULL_BISMILLAH_INTRO=1 — play full bismillah on intro page (e.g. for Shateri); else only first 3 s when juz starts at a sura.
# Optional: FIRST_PAGES_ONLY=1 — build only intro (first page) + first ayah → out/juz_N_parhizgar_limit1.mp4 (for debugging).
#
# Debug (first page + one ayah only): run the unified script directly, e.g. from repo root:
#   python3 src/create_movie_quran.py juz 1 out/juz1_debug.mp4 --view ayah --translation_root data/persian-recitation --fps 30 --first_page $'تلاوت قرآن کریم\nجزء {JOZ}\nسوره‌ها: {SURELIST}\nبا صدای آقای پرهیزگار' --debug

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
  echo "Usage: set juz number, e.g.:  export j=30   OR   zsh src/persian-recitation-juz.sh 30"
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

echo "=============================================="
echo "Juz: $JUZ_INDEX  |  Data dir: $DATA_DIR"
echo "=============================================="

# ----- Background: get next via bg_admin; if create_movie exits 2 (not enough remaining), exhaust current bg and try next -----
PRJ="p-juz-${JUZ_INDEX}-tanzil"
OUT_PATH="out/juz_${JUZ_INDEX}_shateri.mp4"
# First page + first ayah only (for debugging intro/bismillah): set FIRST_PAGES_ONLY=1 or DEBUG_LIMIT_AYAHS=1
[ -n "${FIRST_PAGES_ONLY:-}" ] && DEBUG_LIMIT_AYAHS="${DEBUG_LIMIT_AYAHS:-1}"
[ -n "${DEBUG_LIMIT_AYAHS:-}" ] && OUT_PATH="out/juz_${JUZ_INDEX}_parhizgar_limit${DEBUG_LIMIT_AYAHS}.mp4"
FIRST_PAGE=$'تلاوت قرآن کریم\nجزء {JOZ}\nسوره‌ها: {SURELIST}\nبا صدای آقای شاطری'
EXTRA_OPTS=()
[ -n "${DEBUG_LIMIT_AYAHS:-}" ] && { echo "Debug: limiting to first $DEBUG_LIMIT_AYAHS ayahs → $OUT_PATH"; EXTRA_OPTS+=(--debug_limit_ayahs "$DEBUG_LIMIT_AYAHS"); }

while true; do
  BG_ADMIN_OUT=$(python3 src/bg_admin.py juz "$BG_URLS_FILE" "$BG_VIDEOS_DIR" get_next \
    --required 60 --repo-root "$REPO_ROOT" --yt-dlp "$YT_DLP" \
    --skip-start "$BG_SKIP_START" --skip-end "$BG_SKIP_END")
  BG_EXIT=$?
  [ "$BG_EXIT" -eq 1 ] && { echo "Reached end of background list. No more videos."; exit 0; }
  [ "$BG_EXIT" -ne 0 ] && exit "$BG_EXIT"
  BG_VIDEO=$(echo "$BG_ADMIN_OUT" | head -1)
  BG_CLIP_START_SEC=$(echo "$BG_ADMIN_OUT" | tail -1)
  [ -z "$BG_VIDEO" ] || [ ! -f "$BG_VIDEO" ] && { echo "Error: bg_admin did not return a valid file"; exit 1; }
  echo "Background: $BG_VIDEO, clip_start=${BG_CLIP_START_SEC}s"

  RECIT_OPTS=()
  [ -n "${RECITATION_TEMPLATE:-https://tanzil.net/res/audio/shateri/{sura}{ayah}.mp3}" ] && RECIT_OPTS+=(--recitation_template "$RECITATION_TEMPLATE")
  [ -n "${FULL_BISMILLAH_INTRO:-}" ] && RECIT_OPTS+=(--full_bismillah_intro)
  CREAT_EXIT=0
  python3 src/create_movie_quran.py juz "$JUZ_INDEX" "$OUT_PATH" --view ayah \
    --translation_root "$DATA_DIR" \
    --fps 30 \
    --background_video "$BG_VIDEO" \
    --bg_clip_start "$BG_CLIP_START_SEC" \
    --first_page "$FIRST_PAGE" \
    --show_juz \
    "${RECIT_OPTS[@]}" \
    "${EXTRA_OPTS[@]}" || CREAT_EXIT=$?

  if [ "$CREAT_EXIT" -eq 0 ]; then
    break
  fi
  if [ "$CREAT_EXIT" -eq 2 ]; then
    echo "Not enough remaining time on this background; exhausting and trying next via bg_admin."
    python3 src/bg_admin.py juz "$BG_URLS_FILE" "$BG_VIDEOS_DIR" update_used --seconds 9999999 --repo-root "$REPO_ROOT"
    continue
  fi
  exit "$CREAT_EXIT"
done

# Advance used amount via bg_admin based on actual Juz video duration
JUZ_DURATION=$(LC_NUMERIC=C ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUT_PATH" 2>/dev/null || true)
JUZ_DURATION=${JUZ_DURATION:-0}
python3 src/bg_admin.py juz "$BG_URLS_FILE" "$BG_VIDEOS_DIR" update_used --seconds "$JUZ_DURATION" --repo-root "$REPO_ROOT"
echo "State saved via bg_admin."

echo "File saved to $OUT_PATH. For next juz: export j=\$((j+1)) and run again."

