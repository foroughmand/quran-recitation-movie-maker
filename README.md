# Automatic Quran Recitation Movie Creation
You can create a recitation movie automatically with this repository. You need 
  1) Recitation audio (you can find free recitation audio files on the internet) 
  2) A background video to accompany the recitation text.

The main step in this process is the automatic synchronization of Quran text and recitation which is done with 
[ctc-forced-aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner). The rest is straightforward and has been implemented in this repository.

## 1. Install
Make sure `ffmpeg` and `yt-dlp` are installed

Install [ctc-forced-aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner):
```
pip install git+https://github.com/MahmoudAshraf97/ctc-forced-aligner.git
```

Install moviepy
```
pip install moviepy
```

## 2. Downloading data
```
mkdir -p data/ tmp/ out/ font/
wget https://tanzil.net/res/text/metadata/quran-data.xml -O data/quran-data.xml
cat data/quran-data.xml | grep '<sura ' | sed 's/.*index="\([0-9]*\)" ayas="\([0-9]*\)".*/\1 \2/' > data/quran-sura-aye.txt
wget https://tanzil.net/pub/download/index.php\?quranType\=simple-plain\&outType\=txt\&agree\=true -O data/quran-simple-plain.txt
python src/split_quran_text.py data/quran-simple-plain.txt data/quran-sura-aye.txt data/quran-simple-plain-
wget https://bitbucket.org/dma8hm1334/persian-hm-xs2-3.8/raw/master/persian-hm-xs2-3.8/fonts/Ttf/HM_XNiloofarBd.ttf -O font/HM_XNiloofarBd.ttf
wget https://bitbucket.org/dma8hm1334/persian-hm-xs2-3.8/raw/master/persian-hm-xs2-3.8/fonts/Ttf/HM_XNiloofar.ttf -O font/HM_XNiloofar.ttf

# Font: HM_XNiloofarBD.ttf
git clone https://github.com/quran/quran.com-frontend-next
```

## 3. Preparing background video and audio file
In this step, the two variables `${PRJ}` and `${SURE_INDEX}` must be set, and the recitation audio file `tmp/${PRJ}-sound.wav` must be created.
Also, the file `tmp/${PRJ}-bg.mp4` will contain the background video.

## 4. Run aligner
This will create the file `tmp/${PRJ}-sound.txt`.
```
ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
```

## 5. Create the final movie
This is used in the examples above.
```
python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --interline 30 --stroke_width 5 

```


# Customized Instructions for Individual Surahs

### Backgrounds

```
#../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=hlWiI4xVXKY -k  -f 'bv*[height=1080]+ba' -o tmp/${PRJ}-bg.mp4

../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=m17G-1clTaM -k -o tmp/bg1
rm tmp/bg1.mp4
mv tmp/bg1.f401.mp4 tmp/bg1.mp4

../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=5QXeJwQ0Sy4 -k -o tmp/bg2
rm tmp/bg2.mp4
mv tmp/bg2.f401.mp4 tmp/bg2.mp4

# 10:23h
../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=fhO4kiSmbV4 -k -o tmp/bg3

# 7:53h
../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=_tpjXSSV1rc -k -o tmp/bg4

# 3h
../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=bqy4X3FF1rE -k -o tmp/bg5

# 1:07h
../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=cHlioeh1WKA -k -o tmp/bg6

# 10:25h
https://www.youtube.com/watch?v=BUJro8RTUOY
# 8h
https://www.youtube.com/watch?v=3E5LKDJykeQ
# 6:40h
https://www.youtube.com/watch?v=lTWDwIxuhYo
# 8:10h
https://www.youtube.com/watch?v=dGaNaEpU6uY
# 8:30h
https://www.youtube.com/watch?v=FUuJZuwa9Po
# 8:20h
https://www.youtube.com/watch?v=e4ajwAFKmz0
# 3h
https://www.youtube.com/watch?v=dBRmL3yQ9GQ
# 2h
https://www.youtube.com/watch?v=vHE-NvgHrt0
# 3.5h
https://www.youtube.com/watch?v=tMYQR8c29G4
# 3h
https://www.youtube.com/watch?v=yeOSCLtaYqo
```


### Sure Ebrahim
```
PRJ=q-ebrahim-abkar
SURE_INDEX=14
# ln -s tmp/q-anbia-abkar-bg.mp4 tmp/${PRJ}-bg.mp4 
#../azan-tv/bin/yt-dlp -x https://youtu.be/TdZ-R485j3s -o tmp/${PRJ}-sound
wget https://server6.mp3quran.net/abkr/014.mp3 -O tmp/${PRJ}-sound-0.mp3
ffmpeg -i tmp/${PRJ}-sound-0.mp3 tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/bg2.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 02:20:00 --bg_clip_end 02:41:00 --interline 30 --stroke_width 5 --audio_skip 0.0

```


### Sure Maryam
```
PRJ=q-maryam-abkar
SURE_INDEX=19
#../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=hlWiI4xVXKY -k  -f 'bv*[height=1080]+ba' -o tmp/${PRJ}-bg.mp4
ln -s q-anbia-abkar-bg.mp4 tmp/${PRJ}-bg.mp4 
../azan-tv/bin/yt-dlp -x https://youtu.be/jpZH0t5zoo0 -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.wav

# run ctc-forced-aligner

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 02:20:00 --bg_clip_end 02:XXXX:00 --interline 30 --stroke_width 5 --audio_skip 0.0
```




### Sure Taha
```
# 20 Taha
PRJ=q-taha-abkar
SURE_INDEX=20
../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=hlWiI4xVXKY -k  -f 'bv*[height=1080]+ba' -o tmp/${PRJ}-bg.mp4
mv tmp/q-taha-abkar-bg.mp4.f399.mp4 tmp/${PRJ}-bg.mp4
../azan-tv/bin/yt-dlp -x 'https://youtu.be/2q9tphU_pB8' -o tmp/${PRJ}-sound
#ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 01:50:00 --bg_clip_end 02:20:00 --interline 30 --stroke_width 5 --audio_skip 0.0
```

### Sure Anbia
```
PRJ=q-anbia-abkar
SURE_INDEX=21

# ../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=mdoZdXBpYzU -k  -o tmp/${PRJ}-bg.mp4
# ../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=ewXluXsb-mM -k  -o tmp/${PRJ}-bg.mp4
#rm tmp/${PRJ}-bg.mp4.webm
#mv tmp/${PRJ}-bg.mp4.f313.webm tmp/${PRJ}-bg.webm 
# ../azan-tv/bin/yt-dlp -x https://www.youtube.com/watch?v=wZrSMYj91ls -o tmp/${PRJ}-sound
# ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
wget https://server6.mp3quran.net/abkr/021.mp3 -O tmp/${PRJ}-sound-0.mp3
ffmpeg -i tmp/${PRJ}-sound-0.mp3 tmp/${PRJ}-sound.wav
```

```
ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
```

The following steps will fix an alignment issue and create the movie parts.
```
ffmpeg -i tmp/${PRJ}-sound.wav -ss 00:27:33.36 -to 00:29:05.95 tmp/${PRJ}-sound-p2.wav
# 1654
tail +105 data/quran-simple-plain-$SURE_INDEX.txt > tmp/quran-simple-plain-$SURE_INDEX-p2.txt
ctc-forced-aligner --audio_path "tmp/${PRJ}-sound-p2.wav" --text_path "tmp/quran-simple-plain-${SURE_INDEX}-p2.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
python src/add-to-value.py tmp/${PRJ}-sound-p2.txt '^([0-9.]+)-' 1654.0 > tmp/${PRJ}-sound-p2-t1.txt
python src/add-to-value.py tmp/${PRJ}-sound-p2-t1.txt '-([0-9.]+):' 1654.0 > tmp/${PRJ}-sound-p2-t2.txt

(head -n -$(wc -l < tmp/${PRJ}-sound-p2-t2.txt) tmp/${PRJ}-sound.txt; cat tmp/${PRJ}-sound-p2-t2.txt) > tmp/${PRJ}-sound-t3.txt

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound-t3.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 01:20:00 --bg_clip_end 01:50:00 --interline 30 --stroke_width 5 --audio_skip 0.0

```

### Sure Najm
```
PRJ=q-najm-abkar
SURE_INDEX=53

#../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=mdoZdXBpYzU -k  -f 'mp4' -o tmp/${PRJ}-bg.mp4
ln -s q-anbia-abkar-bg.mp4 tmp/${PRJ}-bg.mp4 
../azan-tv/bin/yt-dlp -x https://youtu.be/XvtclX6z0NY -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 00:40:00 --bg_clip_end 01:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0

```


### Sure Ghamar
```
PRJ=q-ghamar-abkar
SURE_INDEX=54

#../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=mdoZdXBpYzU -k  -f 'mp4' -o tmp/${PRJ}-bg.mp4
ln -s q-anbia-abkar-bg.mp4 tmp/${PRJ}-bg.mp4 
# ../azan-tv/bin/yt-dlp -x https://youtu.be/Nue7gWUInJo -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 01:00:00 --bg_clip_end 01:20:00 --interline 30 --stroke_width 5 --audio_skip 0.0

```




### Sure Asr

Example: Creating a recitation movie for Sure Asr.
```
# 103 Asr
PRJ=q-asr-abkar
SURE_INDEX=103
#../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=hlWiI4xVXKY -f 'bv*[height=720]+ba' -o tmp/${PRJ}-bg.mp4
ln -s q-anbia-abkar-bg.mp4 tmp/${PRJ}-bg.mp4 
../azan-tv/bin/yt-dlp -x https://www.youtube.com/watch\?v\=4cl2a3qBGkA -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 00:59:00 --bg_clip_end 01:00:00 --interline 30 --stroke_width 5 

```


### All Sure
```
# 1..6
bg_seek_start=70

for SURE_INDEX in {1..6}; do
PRJ=q-$SURE_INDEX-abkar

echo "PROJECT ****************** $PRJ ***************** $SURE_INDEX ****************"

wget https://server6.mp3quran.net/abkr/`printf "%03d\n" $SURE_INDEX`.mp3 -O tmp/${PRJ}-sound-0.mp3
ffmpeg -y -hide_banner -loglevel error -i tmp/${PRJ}-sound-0.mp3 tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

bg_seek_start_hhmmss=`python3 -c "import datetime; print(str(datetime.timedelta(seconds=$bg_seek_start)))"`

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/bg4.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start "$bg_seek_start_hhmmss" --bg_clip_end 00:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0

duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "tmp/${PRJ}-sound.wav")
bg_seek_start=$(echo "$bg_seek_start + $duration" | bc)
rm -f tmp/${PRJ}-sound-0.wav tmp/${PRJ}-sound.wav

done

SURE_INDEX=2
PRJ=q-$SURE_INDEX-abkar
bg_seek_start=40.691567

```

```
# 7 .. 23
bg_seek_start=70
for SURE_INDEX in {7..23}; do
PRJ=q-$SURE_INDEX-abkar

echo "PROJECT ****************** $PRJ ***************** $SURE_INDEX ****************"

wget https://server6.mp3quran.net/abkr/`printf "%03d\n" $SURE_INDEX`.mp3 -O tmp/${PRJ}-sound-0.mp3
ffmpeg -y -hide_banner -loglevel error -i tmp/${PRJ}-sound-0.mp3 tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

bg_seek_start_hhmmss=`python3 -c "import datetime; print(str(datetime.timedelta(seconds=$bg_seek_start)))"`

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/bg3.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start "$bg_seek_start_hhmmss" --bg_clip_end 00:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0

duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "tmp/${PRJ}-sound.wav")
bg_seek_start=$(echo "$bg_seek_start + $duration" | bc)
rm -f tmp/${PRJ}-sound-0.wav tmp/${PRJ}-sound.wav

done

SURE_INDEX=9
bg_seek_start=6470.8325

SURE_INDEX=17
PRJ=q-$SURE_INDEX-abkar
bg_seek_start=23059.70454
../azan-tv/bin/yt-dlp https://youtu.be/5BAs4cGEATA -k -o tmp/${PRJ}-sound_v2 
ffmpeg -y -i tmp/${PRJ}-sound_v2.f234.mp4 tmp/${PRJ}-sound.wav


SURE_INDEX=18
PRJ=q-$SURE_INDEX-abkar
bg_seek_start=25232.59529
rm tmp/${PRJ}-sound_v2*
#../azan-tv/bin/yt-dlp https://youtu.be/MfNSRW0OaIk -k -o tmp/${PRJ}-sound_v2 
../azan-tv/bin/yt-dlp https://www.aparat.com/v/g04p9rq -k -o tmp/${PRJ}-sound_v2 
ffmpeg -y -ss 4 -i tmp/${PRJ}-sound_v2 tmp/${PRJ}-sound.wav
python src/split-merge.py tmp/${PRJ}-sound.wav "data/quran-simple-plain-${SURE_INDEX}.txt" "54:18*35.33,102:31*28.59,103:32*01.55,104:32*16.210,105:33*6.13,106:34*09.94,107:34*26.20,108:34*51.98,109:35*28.49,110:35*57.49" tmp/${PRJ}_split_ > tmp/${PRJ}-sound.txt

SURE_INDEX=19
PRJ=q-$SURE_INDEX-abkar
bg_seek_start=27439.4976

SURE_INDEX=23
PRJ=q-$SURE_INDEX-abkar
bg_seek_start=34029.74549
../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=BOMP01R41cY -k -o tmp/${PRJ}-sound_v2 
ffmpeg -y -i tmp/${PRJ}-sound_v2.f234.mp4 tmp/${PRJ}-sound.wav



```

```
# 24 .. 28
bg_seek_start=70
for SURE_INDEX in {24..28}; do
PRJ=q-$SURE_INDEX-abkar

echo "PROJECT ****************** $PRJ ***************** $SURE_INDEX ****************"

wget https://server6.mp3quran.net/abkr/`printf "%03d\n" $SURE_INDEX`.mp3 -O tmp/${PRJ}-sound-0.mp3
ffmpeg -y -hide_banner -loglevel error -i tmp/${PRJ}-sound-0.mp3 tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

bg_seek_start_hhmmss=`python3 -c "import datetime; print(str(datetime.timedelta(seconds=$bg_seek_start)))"`

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/bg5.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start "$bg_seek_start_hhmmss" --bg_clip_end 00:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0

duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "tmp/${PRJ}-sound.wav")
bg_seek_start=$(echo "$bg_seek_start + $duration" | bc)
rm -f tmp/${PRJ}-sound-0.wav tmp/${PRJ}-sound.wav

done



SURE_INDEX=25
PRJ=q-$SURE_INDEX-abkar
../azan-tv/bin/yt-dlp https://youtu.be/K2pL1cT2a0M -k -o tmp/${PRJ}-sound_v2 --cookies-from-browser chrome
ffmpeg -y -ss 57 -i tmp/${PRJ}-sound_v2.mp4 tmp/${PRJ}-sound.wav
bg_seek_start=1821.203378

SURE_INDEX=26
PRJ=q-$SURE_INDEX-abkar
bg_seek_start=3347.822316
../azan-tv/bin/yt-dlp https://youtu.be/ZC2IqExI5s8 -k -o tmp/${PRJ}-sound_v2 
ffmpeg -y -ss 55 -i tmp/${PRJ}-sound_v2.f234.mp4 -to 38:00 tmp/${PRJ}-sound.wav



```

```
# 29 .. 31
bg_seek_start=40
for SURE_INDEX in {29..31}; do
PRJ=q-$SURE_INDEX-abkar

echo "PROJECT ****************** $PRJ ***************** $SURE_INDEX ****************"

wget https://server6.mp3quran.net/abkr/`printf "%03d\n" $SURE_INDEX`.mp3 -O tmp/${PRJ}-sound-0.mp3
ffmpeg -y -hide_banner -loglevel error -i tmp/${PRJ}-sound-0.mp3 tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

bg_seek_start_hhmmss=`python3 -c "import datetime; print(str(datetime.timedelta(seconds=$bg_seek_start)))"`

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/bg6.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start "$bg_seek_start_hhmmss" --bg_clip_end 00:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0

duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "tmp/${PRJ}-sound.wav")
bg_seek_start=$(echo "$bg_seek_start + $duration" | bc)
rm -f tmp/${PRJ}-sound-0.wav tmp/${PRJ}-sound.wav

done
```


```
# 32 .. 114
bg_seek_start=21

for SURE_INDEX in {47..114}; do
PRJ=q-$SURE_INDEX-abkar
echo "PROJECT ****************** $PRJ ***************** $SURE_INDEX ****************"

if [[ $SURE_INDEX == "45" ]]; then
  wget https://player.iranseda.ir/downloadnewfile/?VALID=TRUE&attid=450564&q=10&g=443942&t=1&w=46 -O tmp/q-45-abkar-sound-0.mp4
  ffmpeg -y -i tmp/q-45-abkar-sound-0.mp4 tmp/q-45-abkar-sound-0.mp3
elif [[ $SURE_INDEX == "46" ]]; then
  wget https://player.iranseda.ir/downloadnewfile/?VALID=TRUE&attid=450989&q=10&g=443943&t=1&w=46 -O tmp/q-46-abkar-sound-0.mp4
  ffmpeg -y -i tmp/q-46-abkar-sound-0.mp4 tmp/q-46-abkar-sound-0.mp3
elif [[ $SURE_INDEX == "49" ]]; then
  wget https://player.iranseda.ir/downloadnewfile/?VALID=TRUE&attid=450998&q=10&g=443946&t=1&w=46 -O tmp/q-49-abkar-sound-0.mp4
  ffmpeg -y -i tmp/q-49-abkar-sound-0.mp4 tmp/q-49-abkar-sound-0.mp3
else
  wget https://server6.mp3quran.net/abkr/`printf "%03d\n" $SURE_INDEX`.mp3 -O tmp/${PRJ}-sound-0.mp3
fi
ffmpeg -y -hide_banner -loglevel error -i tmp/${PRJ}-sound-0.mp3 tmp/${PRJ}-sound.wav

ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"

bg_seek_start_hhmmss=`python3 -c "import datetime; print(str(datetime.timedelta(seconds=$bg_seek_start)))"`

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/bg1.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start "$bg_seek_start_hhmmss" --bg_clip_end 00:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0

duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "tmp/${PRJ}-sound.wav")
bg_seek_start=$(echo "$bg_seek_start + $duration" | bc)
rm -f tmp/${PRJ}-sound-0.wav tmp/${PRJ}-sound.wav

done

SURE_INDEX=36
PRJ=q-$SURE_INDEX-abkar
../azan-tv/bin/yt-dlp https://www.youtube.com/watch?v=8FDGEjLr9NU -k -o tmp/${PRJ}-sound_v2
ffmpeg -i tmp/q-36-abkar-sound_v2.f251.webm tmp/${PRJ}-sound.wav

bg_seek_start_hhmmss=4844
python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/bg1.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start "$bg_seek_start_hhmmss" --bg_clip_end 00:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0

SURE_INDEX=42
PRJ=q-$SURE_INDEX-abkar
../azan-tv/bin/yt-dlp https://youtu.be/v-Bd3MShIUc -k -o tmp/${PRJ}-sound_v2 --cookies-from-browser chrome
ffmpeg -y -i tmp/${PRJ}-sound_v2.f251.webm tmp/${PRJ}-sound.wav
bg_seek_start=13280.03116

SURE_INDEX=43
PRJ=q-$SURE_INDEX-abkar
rm tmp/${PRJ}-sound.*
../azan-tv/bin/yt-dlp https://youtu.be/1LsTxoxhHLc -k -o tmp/${PRJ}-sound_v2 --cookies-from-browser chrome
ffmpeg -y -i tmp/${PRJ}-sound_v2.f251.webm tmp/${PRJ}-sound.wav

bg_seek_start=14682.13547

SURE_INDEX=44
PRJ=q-$SURE_INDEX-abkar
../azan-tv/bin/yt-dlp https://youtu.be/JQqR9Ffd7gQ -o tmp/${PRJ}-sound_v2 --cookies-from-browser chrome
ffmpeg -ss 44.00 -i tmp/q-44-abkar-sound_v2.mp4 tmp/${PRJ}-sound.wav
bg_seek_start_hhmmss=16096.90916

SURE_INDEX=45
PRJ=q-$SURE_INDEX-abkar
mv out/${PRJ}.mp4 tmp/${PRJ}_.mp4
ffmpeg -ss 7.40 -i tmp/${PRJ}_.mp4 -to 10:49 out/${PRJ}.mp4

SURE_INDEX=46
PRJ=q-$SURE_INDEX-abkar
mv out/${PRJ}.mp4 tmp/${PRJ}_.mp4
ffmpeg -i tmp/${PRJ}_.mp4 -to 15:57 out/${PRJ}.mp4
bg_seek_start=17437.93915


SURE_INDEX=47
bg_seek_start=18424.55793

SURE_INDEX=49
PRJ=q-$SURE_INDEX-abkar
mv out/${PRJ}.mp4 tmp/${PRJ}_.mp4
ffmpeg -i tmp/${PRJ}_.mp4 -to 8:21.30 out/${PRJ}.mp4


SURE_INDEX=114
PRJ=q-$SURE_INDEX-abkar
mv out/${PRJ}.mp4 tmp/${PRJ}_.mp4
ffmpeg -i tmp/${PRJ}_.mp4 -to 30.00 out/${PRJ}.mp4
```

```
for sure in {1..114}; do wget https://server6.mp3quran.net/abkr/`printf "%03d\n" $sure`.mp3 -O tmp/q-${sure}-abkar-sound-0.mp3; done
wget https://player.iranseda.ir/downloadnewfile/?VALID=TRUE&attid=450564&q=10&g=443942&t=1&w=46 -O tmp/q-45-abkar-sound-0.mp4
ffmpeg -y -i tmp/q-45-abkar-sound-0.mp4 tmp/q-45-abkar-sound-0.mp3
wget https://player.iranseda.ir/downloadnewfile/?VALID=TRUE&attid=450989&q=10&g=443943&t=1&w=46 -O tmp/q-46-abkar-sound-0.mp4
ffmpeg -y -i tmp/q-46-abkar-sound-0.mp4 tmp/q-46-abkar-sound-0.mp3
wget https://player.iranseda.ir/downloadnewfile/?VALID=TRUE&attid=450998&q=10&g=443946&t=1&w=46 -O tmp/q-49-abkar-sound-0.mp4
ffmpeg -y -i tmp/q-49-abkar-sound-0.mp4 tmp/q-49-abkar-sound-0.mp3
```

### Doa
```
PRJ=abuhamze-samavati
../azan-tv/bin/yt-dlp -x https://youtu.be/aJgD-438KVY -o tmp/${PRJ}-sound
# wget https://server6.mp3quran.net/abkr/014.mp3 -O tmp/${PRJ}-sound-0.mp3
ffmpeg -i tmp/${PRJ}-sound.mp4 tmp/${PRJ}-sound.wav


ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.wav" --text_path "data/abuhamze.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-persian"
python src/create_movie.py "data/abuhamze.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.wav out/${PRJ}.mp4 tmp/bg3.mp4 0 --font HM_XNiloofar.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title "دعای ابوحمزه ثمالی" --title_font HM_XNiloofar.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start "$bg_seek_start_hhmmss" --bg_clip_end 00:00:00 --interline 30 --stroke_width 5 --audio_skip 0.0 --text_render_method file --no-add_aye_number 

# TEST:
ffmpeg -i tmp/${PRJ}-sound.wav -to 01:00 tmp/${PRJ}-sound-test.wav
ctc-forced-aligner --audio_path "tmp/${PRJ}-sound-test.wav" --text_path tmp/abuhamze-test.txt --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-persian"

```

# Next steps
* Darkening the background may produce more visually appealing movies.
* A version which changes the background for each verse might produce better focus.
* Some recitations return to previous verses; the displayed verse could also revert accordingly.
* Current word in the verse could be highlighted. The problem was that the alignment between recitation and words is not so accurate.

# Done
* There is a very tiny silence between verses, which should be fixed.
* For long verses, the font size could be automatically decreased.
* Some videos are not playing the whole sound. 
