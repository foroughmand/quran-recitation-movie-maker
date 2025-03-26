PRJ=$1
SURE_INDEX=$2
SPLIT_STRING=$3
bg_seek_start=$4
BG_VIDEO=$5

set -e

python src/split-merge.py "tmp/${PRJ}-sound.wav" "data/quran-simple-plain-${SURE_INDEX}.txt" "${SPLIT_STRING}" "tmp/${PRJ}_" > "tmp/${PRJ}-sound.txt"

bg_seek_start_hhmmss=`python3 -c "import datetime; print(str(datetime.timedelta(seconds=$bg_seek_start)))"`

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 ${BG_VIDEO} ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start "$bg_seek_start_hhmmss" --bg_clip_end 00:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0
