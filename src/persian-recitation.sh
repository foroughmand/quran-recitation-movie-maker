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

# --- Background: one list (URLs or local file paths) in bg_urls.txt ---
BG_SKIP_START=120
BG_SKIP_END=120
BG_URLS_FILE="${DATA_DIR}/bg_urls.txt"
BG_VIDEOS_DIR="tmp/bg_videos"
BG_STATE_FILE="tmp/bg_state.txt"
YT_DLP="${REPO_ROOT}/../yt-dlp"
[ -d "$YT_DLP" ] && YT_DLP="${YT_DLP}/yt-dlp"
BG_URLS=()
if [ ! -f "$BG_URLS_FILE" ]; then
  echo "Error: create $BG_URLS_FILE (one YouTube URL or file path per line)"
  exit 1
fi
[ -x "$YT_DLP" ] || [ -f "$YT_DLP" ] || { echo "Error: yt-dlp not found at $YT_DLP (set YT_DLP or use ../yt-dlp)"; exit 1; }
mkdir -p "$BG_VIDEOS_DIR"
while IFS= read -r line; do
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  [[ -z "$line" || "$line" == \#* ]] && continue
  BG_URLS+=("$line")
done < "$BG_URLS_FILE"
[ ${#BG_URLS[@]} -eq 0 ] && { echo "Error: no entries in $BG_URLS_FILE"; exit 1; }

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
python3 src/download_tanzil_sura.py "$SURE_INDEX" "$AYAS" "$SURE_DIR"

# =============================================================================
# STEP 2 — Build combined audio (recitation then translation per ayah)
# =============================================================================
# Concatenates: rec_1, trans_1, rec_2, trans_2, ... into one WAV and writes
# segment timings to a mapping file for the movie script.
#
# Uncomment and run:
#
python3 src/build_persian_audio.py "$SURE_DIR" "$SURE_INDEX" "$AYAS"

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
# STEP 4 — Create the movie (Arabic ayah + Persian translation on screen)
# =============================================================================
# Background: bg_urls.txt (URLs or file paths, one per line). State in bg_state.txt. Reset: rm bg_state.txt
#
PRJ="p-${SURE_INDEX}-tanzil"
test -f "$SURE_DIR/combined.wav" || { echo "Run Step 2 first (build combined.wav)."; exit 1; }
SURA_DURATION=$(LC_NUMERIC=C ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$SURE_DIR/combined.wav" 2>/dev/null || true)
[ -z "$SURA_DURATION" ] && { echo "Could not get duration of combined.wav"; exit 1; }

# ----- Background: URLs (download, remove when done) or file paths (use as-is, do not remove) -----
is_bg_url() { [[ "$1" == http://* || "$1" == https://* ]]; }
resolve_bg_path() { case "$1" in /*) echo "$1";; *) echo "$REPO_ROOT/$1";; esac; }
# Resolve actual file for bg index when entry is a URL (yt-dlp may write .mp4 or .mp4.webm etc.)
resolve_bg_video() {
  setopt local_options null_glob 2>/dev/null || true
  local idx="$1"
  local base="${BG_VIDEOS_DIR}/bg_${idx}"

  [ -f "${base}.mp4" ] && echo "${base}.mp4" && return 0

  local f
  for f in "${base}".*; do
    [ -f "$f" ] && echo "$f" && return 0
  done

  return 1
}
download_bg_url() {
  local idx="$1"
  local url="$2"
  local out="${BG_VIDEOS_DIR}/bg_${idx}.mp4"
  local max_retries=3
  local retry_delay=60
  local r=1
  while [ "$r" -le "$max_retries" ]; do
    echo "  [yt-dlp] attempt $r/$max_retries: bg_${idx} (any format)"
    if "$YT_DLP" -f 'bv*[height=1080]+ba/bv*+ba/best' -o "$out" --no-part -- "$url" 2>/dev/null; then
      resolve_bg_video "$idx" >/dev/null && return 0
    fi
    [ "$r" -lt "$max_retries" ] && echo "  Retry in ${retry_delay}s..." && sleep "$retry_delay"
    r=$((r+1))
  done
  return 1
}

# True if we can open a new terminal window (for background downloads).
have_terminal_window() {
  command -v gnome-terminal >/dev/null 2>&1 || \
  command -v konsole >/dev/null 2>&1 || \
  command -v xterm >/dev/null 2>&1 || \
  command -v x-terminal-emulator >/dev/null 2>&1
}

# Run a command in a new terminal window; blocks until the user closes the window (or command ends).
# Used for bg downloads so the user can cancel by closing the window; waiters see the PID die.
run_in_new_terminal() {
  local cmd="$1"
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal --wait -- bash -c "$cmd"
    return 0
  fi
  if command -v konsole >/dev/null 2>&1; then
    konsole -e bash -c "$cmd"
    return 0
  fi
  if command -v xterm >/dev/null 2>&1; then
    xterm -e bash -c "$cmd"
    return 0
  fi
  if command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e bash -c "$cmd"
    return 0
  fi
  return 1
}

# Start a background (pre-)download: in a new window if possible (user can cancel there); else in-process.
start_background_download_bg() {
  local idx="$1"
  local pidfile="${BG_VIDEOS_DIR}/.downloading_${idx}.pid"
  [ "$idx" -gt ${#BG_URLS[@]} ] && return
  resolve_bg_video "$idx" >/dev/null && return
  if [ -f "$pidfile" ]; then
    local pid
    read -r pid < "$pidfile" 2>/dev/null || true
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return
    fi
    rm -f "$pidfile" "${BG_VIDEOS_DIR}/.downloading_${idx}"
  fi
  local url="${BG_URLS[$((idx-1))]}"
  local out="${BG_VIDEOS_DIR}/bg_${idx}.mp4"
  if have_terminal_window; then
    local run_cmd
    run_cmd="cd \"$(printf '%s' "$REPO_ROOT" | sed 's/"/\\"/g')\" && \"$(printf '%s' "$YT_DLP" | sed 's/"/\\"/g')\" -f 'bv*[height=1080]+ba/bv*+ba/best' -o \"$(printf '%s' "$out" | sed 's/"/\\"/g')\" --no-part -- \"$(printf '%s' "$url" | sed 's/"/\\"/g')\"; echo ''; read -p 'Press Enter to close (download finished or cancelled)'"
    ( run_in_new_terminal "$run_cmd" ) &
    echo $! > "$pidfile"
  else
    ( download_bg_url "$idx" "$url" ; rm -f "${BG_VIDEOS_DIR}/.downloading_${idx}" ) &
    echo $! > "$pidfile"
  fi
}
wait_for_bg_file() {
  local idx="$1"
  local timeout="${2:-600}"
  local elapsed=0
  local pidfile="${BG_VIDEOS_DIR}/.downloading_${idx}.pid"
  local res pid
  while [ "$elapsed" -lt "$timeout" ]; do
    res=$(resolve_bg_video "$idx" || true)
    if [ -n "$res" ]; then
      if LC_NUMERIC=C ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$res" 2>/dev/null | grep -q .; then
        return 0
      fi
    fi
    if [ -f "$pidfile" ]; then
      read -r pid < "$pidfile" 2>/dev/null || true
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        sleep 5
        elapsed=$((elapsed+5))
        continue
      fi
      rm -f "$pidfile" "${BG_VIDEOS_DIR}/.downloading_${idx}"
    fi
    start_background_download_bg "$idx"
    sleep 5
    elapsed=$((elapsed+5))
  done
  return 1
}

# Load state: 1-based item index, seconds used on current background
BG_INDEX=0
USED_SECONDS=0
if [ -f "$BG_STATE_FILE" ]; then
  read -r BG_INDEX USED_SECONDS < "$BG_STATE_FILE" 2>/dev/null || true
  BG_INDEX=${BG_INDEX:-0}
  USED_SECONDS=${USED_SECONDS:-0}
fi

NUM_ITEMS=${#BG_URLS[@]}
[ "$BG_INDEX" -lt 1 ] && BG_INDEX=1
while true; do
  [ "$BG_INDEX" -gt "$NUM_ITEMS" ] && { echo "Reached end of background list ($NUM_ITEMS items). No more videos."; exit 0; }
  ENTRY="${BG_URLS[$((BG_INDEX-1))]}"
  if is_bg_url "$ENTRY"; then
    BG_VIDEO=$(resolve_bg_video "$BG_INDEX" || true)
    if [ -z "$BG_VIDEO" ] || [ ! -f "$BG_VIDEO" ]; then
      echo "Background $BG_INDEX not found; downloading (blocking)..."
      if download_bg_url "$BG_INDEX" "$ENTRY"; then
        BG_VIDEO=$(resolve_bg_video "$BG_INDEX" || true)
      else
        echo "Download failed for URL $BG_INDEX; trying next."
        BG_INDEX=$((BG_INDEX+1))
        USED_SECONDS=0
        continue
      fi
    fi
  else
    BG_VIDEO=$(resolve_bg_path "$ENTRY")
    if [ ! -f "$BG_VIDEO" ]; then
      echo "Background file not found: $BG_VIDEO"
      BG_INDEX=$((BG_INDEX+1))
      USED_SECONDS=0
      continue
    fi
  fi
  [ -z "$BG_VIDEO" ] && { BG_INDEX=$((BG_INDEX+1)); USED_SECONDS=0; continue; }
  FILE_DURATION=$(LC_NUMERIC=C ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$BG_VIDEO" 2>/dev/null) || FILE_DURATION=""
  if [ -z "$FILE_DURATION" ] || [ "$FILE_DURATION" = "N/A" ]; then
    echo "Invalid file bg_${BG_INDEX}; trying next."
    [[ "$BG_VIDEO" == "${BG_VIDEOS_DIR}"* ]] && rm -f "$BG_VIDEO"
    BG_INDEX=$((BG_INDEX+1))
    USED_SECONDS=0
    continue
  fi
  USABLE=$(LC_NUMERIC=C awk -v d="$FILE_DURATION" -v s="$BG_SKIP_START" -v e="$BG_SKIP_END" 'BEGIN{print d-s-e}' 2>/dev/null) || USABLE=0
  REMAINING=$(LC_NUMERIC=C awk -v u="$USABLE" -v used="$USED_SECONDS" 'BEGIN{print u-used}' 2>/dev/null) || REMAINING=0
  if LC_NUMERIC=C awk -v r="$REMAINING" -v need="$SURA_DURATION" 'BEGIN{exit !(r>=need)}' 2>/dev/null; then
    break
  fi
  echo "bg_${BG_INDEX} has ${REMAINING}s left (need ${SURA_DURATION}s); switching to next."
  [[ "$BG_VIDEO" == "${BG_VIDEOS_DIR}"* ]] && rm -f "$BG_VIDEO"
  BG_INDEX=$((BG_INDEX+1))
  [ "$BG_INDEX" -gt "$NUM_ITEMS" ] && { echo "Reached end of background list ($NUM_ITEMS items). No more videos."; exit 0; }
  USED_SECONDS=0
  ENTRY="${BG_URLS[$((BG_INDEX-1))]}"
  if is_bg_url "$ENTRY"; then
    if ! resolve_bg_video "$BG_INDEX" >/dev/null; then
      echo "Waiting for bg_${BG_INDEX} (up to 10 min)..."
      if wait_for_bg_file "$BG_INDEX" 600; then
        :
      else
        echo "Still not ready; downloading now (blocking)..."
        if ! download_bg_url "$BG_INDEX" "$ENTRY"; then
          echo "Download failed; will try next in loop."
        fi
      fi
    fi
  fi
done
ENTRY="${BG_URLS[$((BG_INDEX-1))]}"
if is_bg_url "$ENTRY"; then
  BG_VIDEO=$(resolve_bg_video "$BG_INDEX" || true)
else
  BG_VIDEO=$(resolve_bg_path "$ENTRY")
fi
[ -z "$BG_VIDEO" ] || [ ! -f "$BG_VIDEO" ] && { echo "Error: resolved bg_${BG_INDEX} not found"; exit 1; }
NEXT_INDEX=$((BG_INDEX+1))
if [ "$NEXT_INDEX" -le "$NUM_ITEMS" ] && is_bg_url "${BG_URLS[$((NEXT_INDEX-1))]}"; then
  start_background_download_bg "$NEXT_INDEX"
fi
BG_CLIP_START_SEC=$(LC_NUMERIC=C awk "BEGIN { print $BG_SKIP_START + $USED_SECONDS }" 2>/dev/null || echo "$BG_SKIP_START")
echo "Background: $BG_VIDEO (item $BG_INDEX/$NUM_ITEMS), clip_start=${BG_CLIP_START_SEC}s, used_so_far=${USED_SECONDS}s"

python3 src/create_movie_persian.py \
  "data/quran-simple-plain-${SURE_INDEX}.txt" \
  "$SURE_DIR/segment_mapping.txt" \
  "$SURE_DIR/combined.wav" \
  "out/${PRJ}.mp4" \
  "$BG_VIDEO" \
  "$SURE_INDEX" \
  --translation_dir "$SURE_DIR/translation_text" \
  --font "quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf" \
  --font_size 100 \
  --title "سوره $(sed -n "${SURE_INDEX}p" "$REPO_ROOT/data/sura_names_fa.txt" 2>/dev/null | sed 's/^[0-9]*[[:space:]]*//' || echo "$SURE_INDEX")" \
  --title_font "quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf" \
  --title_font_size 100 \
  --size_x 1920 \
  --size_y 1080 \
  --interline 30 \
  --stroke_width 5 \
  --translation_font "font/HM_XNiloofar.ttf" \
  --translation_font_size 48 \
  --bg_clip_start "$BG_CLIP_START_SEC" \
  --audio_skip 0.0 --audio translation

# Advance used amount; next run will switch to next file if this one has no time left
USED_SECONDS=$(LC_NUMERIC=C awk "BEGIN { print $USED_SECONDS + $SURA_DURATION }" 2>/dev/null || echo "$USED_SECONDS")
echo "$BG_INDEX $USED_SECONDS" > "$BG_STATE_FILE"
echo "State saved: file_index=$BG_INDEX, used_seconds=$USED_SECONDS"

echo "File saved to out/${PRJ}.mp4. For next sura: export s=\$((s+1)) and run again."
