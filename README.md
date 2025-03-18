# Automatic Quran Recitation Movie Creation
You can create a recitation movie qutomatically with this repository. You need 
  1) Recitation audio (you can find free recitation audio on internet) 
  2) A background movie to be played at the background of the recitation text.

The main step in this process is the automatic synchronization of Quran text and recitation which is done with 
[ctc-forced-aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner). The rest is straight forward but implemented in this repository.

## 1. Install
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
In this step, we need two variables ${PRJ} and ${SURE_INDEX} to be setted, 
the recitation sound file `tmp/${PRJ}-sound.mp3` be created.
Also, the file `tmp/${PRJ}-bg.mp4` will contain the background movie.

### Sure Taha
```
# 20 Taha
PRJ=q-taha-abkar
SURE_INDEX=20
../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=hlWiI4xVXKY -k  -f 'bv*[height=1080]+ba' -o tmp/${PRJ}-bg.mp4
mv tmp/q-taha-abkar-bg.mp4.f399.mp4 tmp/${PRJ}-bg.mp4
../azan-tv/bin/yt-dlp -x 'https://youtu.be/2q9tphU_pB8\?list\=PLCSv-dj2OJ5nvu8wHvVCLzt-ih4Ly3BrL' -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3

# run ctc-forced-aligner

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.mp3 tmp/${PRJ}_part_ tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --interline 20 --stroke_width 5
```

### Sure Anbia
```
PRJ=q-anbia-abkar
SURE_INDEX=21

../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=mdoZdXBpYzU -k  -f 'mp4' -o tmp/${PRJ}-bg.mp4
../azan-tv/bin/yt-dlp -x https://www.youtube.com/watch?v=wZrSMYj91ls -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
```

Then run ctc-forced-aligner.

Following will fix a problem in the alignment and creates the movie parts.
```
ffmpeg -i tmp/${PRJ}-sound.mp3 -vn -acodec copy -ss 00:27:34 -to 00:29:03 tmp/${PRJ}-sound-p2.mp3
# 1654
tail +105 data/quran-simple-plain-$SURE_INDEX.txt > tmp/quran-simple-plain-$SURE_INDEX-p2.txt
ctc-forced-aligner --audio_path "tmp/${PRJ}-sound-p2.mp3" --text_path "tmp/quran-simple-plain-${SURE_INDEX}-p2.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
python src/add-to-value.py tmp/${PRJ}-sound-p2.txt '^([0-9.]+)-' 1654.0 > tmp/${PRJ}-sound-p2-t1.txt
python src/add-to-value.py tmp/${PRJ}-sound-p2-t1.txt '-([0-9.]+):' 1654.0 > tmp/${PRJ}-sound-p2-t2.txt

(head -n -$(wc -l < tmp/${PRJ}-sound-p2-t2.txt) tmp/${PRJ}-sound.txt; cat tmp/${PRJ}-sound-p2-t2.txt) > tmp/${PRJ}-sound-t3.txt

python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound-t3.txt tmp/${PRJ}-sound.mp3 tmp/${PRJ}_part_ tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --interline 20 --stroke_width 5
```

### Sure Najm
```
PRJ=q-najm-abkar
SURE_INDEX=53

#../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=mdoZdXBpYzU -k  -f 'mp4' -o tmp/${PRJ}-bg.mp4
ln -s q-anbia-abkar-bg.mp4 tmp/${PRJ}-bg.mp4 
../azan-tv/bin/yt-dlp -x https://youtu.be/XvtclX6z0NY -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
```

Then run ctc-forced-aligner.

```
python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.mp3 tmp/${PRJ}_part_ tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 00:40:00 --bg_clip_end 01:00:00 --interline 20 --stroke_width 5
```


### Sure Ghamar
```
PRJ=q-ghamar-abkar
SURE_INDEX=54

#../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=mdoZdXBpYzU -k  -f 'mp4' -o tmp/${PRJ}-bg.mp4
ln -s q-anbia-abkar-bg.mp4 tmp/${PRJ}-bg.mp4 
../azan-tv/bin/yt-dlp -x https://youtu.be/Nue7gWUInJo -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
```

Then run ctc-forced-aligner.

```
python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.mp3 tmp/${PRJ}_part_ tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 01:00:00 --bg_clip_end 01:20:00 --interline 20 --stroke_width 5
```


### Sure Asr

Example of creating recitation movie for Sure Asr.
```
# 103 Asr
PRJ=q-asr-abkar
SURE_INDEX=103
#../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=hlWiI4xVXKY -f 'bv*[height=720]+ba' -o tmp/${PRJ}-bg.mp4
ln -s q-anbia-abkar-bg.mp4 tmp/${PRJ}-bg.mp4 
../azan-tv/bin/yt-dlp -x https://www.youtube.com/watch\?v\=4cl2a3qBGkA -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
```

Then run ctc-forced-aligner.

```
python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.mp3 tmp/${PRJ}_part_ tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --font_size 100 --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100 --size_x 1920 --size_y 1080 --bg_clip_start 01:00:00 --bg_clip_end 01:20:00 --interline 20 --stroke_width 5
```



## 4. Run aligner
This will create the file `tmp/${PRJ}-sound.txt`.
```
ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.mp3" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
```

## 5. Create all aye movies
This is replaced for some examples above.
```
python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.mp3 tmp/${PRJ}_part_ tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 100
```

## 6. Merge movies
This will create the output file `out/${PRJ}.mp4`.
```
cat tmp/${PRJ}_files.txt | sed 's/^tmp\//file /g' > tmp/${PRJ}_files_ffmpeg.txt
ffmpeg -f concat -safe 0 -i tmp/${PRJ}_files_ffmpeg.txt -c copy out/${PRJ}.mp4
```

