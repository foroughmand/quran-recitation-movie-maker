#!/usr/bin/env zsh
#
# Full-surah recitation movie maker from quran_aligner output.
# - Input: one folder with audio.mp3 and alignment.debug.json
# - Uses the existing page-by-page Quran movie layout via create_movie_quran.py aligned_sura
# - Background videos are managed by src/bg_admin.py exactly like the other scripts
#
# Usage:
#   zsh src/aligned-recitation.sh 54
#   zsh src/aligned-recitation.sh 54 quran_aligner/out/54-abkar-full
#
# Optional environment variables:
#   ALIGN_DIR=quran_aligner/out/54-abkar-full
#   PRJ=54-abkar-full
#   HIGHLIGHT_COLOR="#FFFF00"
#   DEBUG_LIMIT_SEC=30

setopt KSH_ARRAYS
set -e
set -x

[ -n "$ZSH_VERSION" ] && setopt KSH_ARRAYS 2>/dev/null
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
REPO_ROOT="$SCRIPT_DIR"
cd "$REPO_ROOT"

if [ -n "$1" ]; then
  s="$1"
elif [ -z "${s:-}" ]; then
  echo "Usage: set sura number, e.g.: export s=54 OR zsh src/aligned-recitation.sh 54 [alignment_dir]"
  exit 1
fi
SURE_INDEX="$s"
if ! [ "$SURE_INDEX" -ge 1 ] 2>/dev/null || ! [ "$SURE_INDEX" -le 114 ] 2>/dev/null; then
  echo "Error: sura number must be 1-114 (got: $SURE_INDEX)"
  exit 1
fi

ALIGN_DIR="${2:-${ALIGN_DIR:-quran_aligner/out/${SURE_INDEX}-full}}"
ALIGN_DIR="${ALIGN_DIR%/}"
if [ ! -d "$ALIGN_DIR" ]; then
  echo "Error: alignment dir not found: $ALIGN_DIR"
  exit 1
fi
ALIGN_AUDIO="${ALIGN_AUDIO:-$ALIGN_DIR/audio.mp3}"
ALIGN_DEBUG_JSON="${ALIGN_DEBUG_JSON:-$ALIGN_DIR/alignment.debug.json}"
if [ ! -f "$ALIGN_AUDIO" ]; then
  RUNLOG="$ALIGN_DIR/run.log"
  if [ -f "$RUNLOG" ]; then
    RECOVERED=$(grep 'Starting alignment: audio=' "$RUNLOG" 2>/dev/null | tail -1 \
      | sed -n 's/^.*Starting alignment: audio=\([^ ]*\).*/\1/p')
    if [ -n "$RECOVERED" ] && [ -f "$RECOVERED" ]; then
      echo "audio.mp3 missing; linking source from run.log: $RECOVERED"
      ln -sf "$RECOVERED" "$ALIGN_DIR/audio.mp3"
      ALIGN_AUDIO="$ALIGN_DIR/audio.mp3"
    fi
  fi
fi
if [ ! -f "$ALIGN_AUDIO" ]; then
  echo "Error: aligned audio not found: $ALIGN_AUDIO"
  echo "  - Let quran_aligner align run to completion (audio is copied after alignment.txt)."
  echo "  - Chain commands with && not ; so this script runs only if align succeeded."
  echo "  - Or set ALIGN_AUDIO to your source MP3 (e.g. export ALIGN_AUDIO=\"../quran-recitation-playlist/raw/013-....mp3\")."
  exit 1
fi
if [ ! -f "$ALIGN_DEBUG_JSON" ]; then
  echo "Error: word-level alignment debug json not found: $ALIGN_DEBUG_JSON"
  echo "This script needs quran_aligner's alignment.debug.json to highlight words."
  exit 1
fi

DATA_DIR="data/persian-recitation"
SURE_DIR="${DATA_DIR}/sura_${SURE_INDEX}"
TRANSLATION_DIR="${TRANSLATION_DIR:-$SURE_DIR/translation_text}"
[ -d "$TRANSLATION_DIR" ] || { echo "Error: translation dir not found: $TRANSLATION_DIR"; exit 1; }
mkdir -p tmp out

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
echo "Aligned sura: $SURE_INDEX"
echo "Alignment dir: $ALIGN_DIR"
echo "Translation dir: $TRANSLATION_DIR"
echo "=========================================================="

AUDIO_DURATION=$(LC_NUMERIC=C ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$ALIGN_AUDIO" 2>/dev/null || true)
[ -z "$AUDIO_DURATION" ] && { echo "Could not get duration of $ALIGN_AUDIO"; exit 1; }

BG_ADMIN_OUT=$(python3 src/bg_admin.py aligned_sura "$BG_URLS_FILE" "$BG_VIDEOS_DIR" get_next \
  --required "$AUDIO_DURATION" --repo-root "$REPO_ROOT" --yt-dlp "$YT_DLP" \
  --skip-start "$BG_SKIP_START" --skip-end "$BG_SKIP_END")
BG_EXIT=$?
[ "$BG_EXIT" -eq 1 ] && { echo "Reached end of background list. No more videos."; exit 0; }
[ "$BG_EXIT" -ne 0 ] && exit "$BG_EXIT"
BG_VIDEO=$(echo "$BG_ADMIN_OUT" | head -1)
BG_CLIP_START_SEC=$(echo "$BG_ADMIN_OUT" | tail -1)
[ -z "$BG_VIDEO" ] || [ ! -f "$BG_VIDEO" ] && { echo "Error: bg_admin did not return a valid file"; exit 1; }
echo "Background: $BG_VIDEO, clip_start=${BG_CLIP_START_SEC}s"

PRJ="${PRJ:-$(basename "$ALIGN_DIR")}"
OUT_PATH="out/${PRJ}.mp4"
MOVIE_OPTS=()
[ -n "${HIGHLIGHT_COLOR:-}" ] && MOVIE_OPTS+=(--highlight_color "$HIGHLIGHT_COLOR")
[ -n "${DEBUG_LIMIT_SEC:-}" ] && MOVIE_OPTS+=(--debug_limit_sec "$DEBUG_LIMIT_SEC")

python3 src/create_movie_quran.py aligned_sura \
  "$ALIGN_DIR" \
  "$OUT_PATH" \
  "$BG_VIDEO" \
  "$SURE_INDEX" \
  --audio_file "$ALIGN_AUDIO" \
  --alignment_debug_json "$ALIGN_DEBUG_JSON" \
  --translation_dir "$TRANSLATION_DIR" \
  --font "quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf" \
  --font_size 100 \
  --title_font "quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf" \
  --title_font_size 100 \
  --size_x 1920 \
  --size_y 1080 \
  --interline 30 \
  --stroke_width 5 \
  --translation_font "font/HM_XNiloofar.ttf" \
  --translation_font_size 48 \
  --bg_clip_start "$BG_CLIP_START_SEC" \
  "${MOVIE_OPTS[@]}"

USED_DURATION="${DEBUG_LIMIT_SEC:-$AUDIO_DURATION}"
python3 src/bg_admin.py aligned_sura "$BG_URLS_FILE" "$BG_VIDEOS_DIR" update_used --seconds "$USED_DURATION" --repo-root "$REPO_ROOT"
echo "State saved via bg_admin."
echo "File saved to $OUT_PATH"
