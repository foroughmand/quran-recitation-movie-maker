#!/usr/bin/env bash
#
# Upload the generated Persian recitation video (sura N) to YouTube and/or Aparat.
#
# Usage:
#   bash src/upload-persian-recitation.sh Y 59    # YouTube only, sura 59
#   bash src/upload-persian-recitation.sh A 59    # Aparat only
#   bash src/upload-persian-recitation.sh YA 59   # Both YouTube and Aparat
#
# Video file: out/p-<sura>-tanzil.mp4 (override with VIDEO_FILE=...)
# Title: ترجمه گویای سوره SURENAME (فولادوند)
# Description: سوره SURENUMBER - SURENAME - ترجمه گویا
# Visibility: public
# YouTube playlist: ترجمه گویای قرآن (فولادوند)
# Aparat: playlist ترجمه گویای قرآن (or set APARAT_PLAYLIST_ID to numeric ID), category مذهبی (6)
#
set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 Y|A|YA <sura_number>"
  echo "  Y  = YouTube only"
  echo "  A  = Aparat only"
  echo "  YA = YouTube and Aparat"
  echo "  sura_number = 1-114"
  exit 1
fi

DEST="$1"
SURE="$2"

if [[ ! "$DEST" =~ ^(Y|A|YA)$ ]]; then
  echo "First argument must be Y, A, or YA"
  exit 1
fi

if (( SURE < 1 || SURE > 114 )); then
  echo "Sura number must be 1-114"
  exit 1
fi

VIDEO_FILE="${VIDEO_FILE:-out/p-${SURE}-tanzil.mp4}"
if [[ ! -f "$VIDEO_FILE" ]]; then
  echo "Video file not found: $VIDEO_FILE"
  exit 1
fi

# Persian sura name from data/sura_names_fa.txt (same as movie and upload scripts)
SURA_NAMES_FA="${REPO_ROOT}/data/sura_names_fa.txt"
SURENAME=$(sed -n "${SURE}p" "$SURA_NAMES_FA" 2>/dev/null | sed 's/^[0-9]*[[:space:]]*//')
if [[ -z "$SURENAME" ]]; then
  echo "Could not get Persian sura name for $SURE; using number."
  SURENAME="$SURE"
fi

TITLE="ترجمه گویای سوره ${SURENAME} (فولادوند)"
DESCRIPTION="سوره ${SURE} - ${SURENAME} - ترجمه گویا"
# Aparat tags: ترجمه قرآن, قرآن, سوره SURENAME (third tag must be "سوره نام")
APARAT_TAGS="ترجمه قرآن-قرآن-سوره ${SURENAME}"

if [[ "$DEST" == "Y" || "$DEST" == "YA" ]]; then
  echo "Uploading to YouTube: $VIDEO_FILE"
  python3 src/upload-videos.py \
    --file "$VIDEO_FILE" \
    --title "$TITLE" \
    --description "$DESCRIPTION" \
    --visibility public \
    --playlist "ترجمه گویای قرآن (فولادوند)"
fi

if [[ "$DEST" == "A" || "$DEST" == "YA" ]]; then
  echo "Uploading to Aparat: $VIDEO_FILE"
  # Aparat category 6 = مذهبی (religious). Playlist: set APARAT_PLAYLIST_ID to numeric ID to add to existing, or use name (default matches YouTube).
  APARAT_PL="${APARAT_PLAYLIST_ID:-ترجمه گویای قرآن (فولادوند)}"
  python3 src/upload-aparat.py \
    --file "$VIDEO_FILE" \
    --title "$TITLE" \
    --description "$DESCRIPTION" \
    --visibility public \
    --playlist "$APARAT_PL" \
    --category "6" \
    --tags "$APARAT_TAGS"
fi

echo "Done."
