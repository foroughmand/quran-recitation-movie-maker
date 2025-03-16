# Automatic Quran Recitation Movie Creation
You can create a recitation movie qutomatically with this repository. You need 
  1) Recitation audio (you can find free recitation audio on internet) 
  2) A background movie to be played at the background of the recitation text.

The main step in this process is the automatic synchronization of Quran text and recitation which is done with 
(ctc-forced-aligner)[https://github.com/MahmoudAshraf97/ctc-forced-aligner]. The rest is straight forward but implemented in this repository.

## 1. Install
Install (ctc-forced-aligner)[https://github.com/MahmoudAshraf97/ctc-forced-aligner]:
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

Example of creating recitation movie for Sure Taha.
```
# 20 Taha
PRJ=q-taha-abkar
SURE_INDEX=20
../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=hlWiI4xVXKY -k  -f 'bv*[height=720]+ba' -o tmp/${PRJ}-bg.mp4
../azan-tv/bin/yt-dlp -x 'https://youtu.be/2q9tphU_pB8\?list\=PLCSv-dj2OJ5nvu8wHvVCLzt-ih4Ly3BrL' -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
```

Example of creating recitation movie for Sure Asr.
```
# 103 Asr
PRJ=q-asr-abkar
SURE_INDEX=103
../azan-tv/bin/yt-dlp https://www.youtube.com/watch\?v\=hlWiI4xVXKY -f 'bv*[height=720]+ba' -o tmp/${PRJ}-bg.mp4
../azan-tv/bin/yt-dlp -x https://www.youtube.com/watch\?v\=4cl2a3qBGkA -o tmp/${PRJ}-sound
ffmpeg -i tmp/${PRJ}-sound.opus tmp/${PRJ}-sound.mp3
```

## 4. Run aligner
```
ctc-forced-aligner --audio_path "tmp/${PRJ}-sound.mp3" --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" --language "ara" --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
```

## 5. Create all aye movies
```
python src/create_movie.py "data/quran-simple-plain-${SURE_INDEX}.txt" tmp/${PRJ}-sound.txt tmp/${PRJ}-sound.mp3 tmp/${PRJ}_part_ tmp/${PRJ}-bg.mp4 ${SURE_INDEX} --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf --files tmp/${PRJ}_files.txt --title `printf "%03d\n" $SURE_INDEX`" surah" --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf --title_font_size 50
```

## 6. Merge movies
```
cat tmp/${PRJ}_files.txt | sed 's/^tmp\//file /g' > tmp/${PRJ}_files_ffmpeg.txt
ffmpeg -f concat -safe 0 -i tmp/${PRJ}_files_ffmpeg.txt -c copy out/${PRJ}.mp4
```

