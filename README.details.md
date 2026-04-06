# Quran Recitation Movie Maker Details

This file contains the setup steps, data preparation, and detailed workflows that were moved out of the top-level README.

For a quick task-oriented entry point, use [README.md](README.md).

## Install

Make sure these tools are available:

- `ffmpeg`
- `yt-dlp`
- `python3`

Install the main Python dependencies used by the movie pipeline:

```bash
pip install git+https://github.com/MahmoudAshraf97/ctc-forced-aligner.git
pip install moviepy
```

Depending on which workflow you use, you may also need packages such as `requests`, `pydub`, `Pillow`, and the YouTube upload dependencies listed in [YOUTUBE_CREDENTIALS.md](YOUTUBE_CREDENTIALS.md).

## Data Preparation

Create the working folders and download the base Quran text data:

```bash
mkdir -p data/ tmp/ out/ font/
wget https://tanzil.net/res/text/metadata/quran-data.xml -O data/quran-data.xml
cat data/quran-data.xml | grep '<sura ' | sed 's/.*index="\([0-9]*\)" ayas="\([0-9]*\)".*/\1 \2/' > data/quran-sura-aye.txt
wget 'https://tanzil.net/pub/download/index.php?quranType=simple-plain&outType=txt&agree=true' -O data/quran-simple-plain.txt
python src/split_quran_text.py data/quran-simple-plain.txt data/quran-sura-aye.txt data/quran-simple-plain-
```

Download the Persian fonts used by the Persian workflows:

```bash
wget https://bitbucket.org/dma8hm1334/persian-hm-xs2-3.8/raw/master/persian-hm-xs2-3.8/fonts/Ttf/HM_XNiloofarBd.ttf -O font/HM_XNiloofarBd.ttf
wget https://bitbucket.org/dma8hm1334/persian-hm-xs2-3.8/raw/master/persian-hm-xs2-3.8/fonts/Ttf/HM_XNiloofar.ttf -O font/HM_XNiloofar.ttf
```

Clone the Quran.com frontend repository for the Arabic glyph fonts used by rendering:

```bash
git clone https://github.com/quran/quran.com-frontend-next
```

## Arabic Surah Workflow

Use this workflow when you already have:

- one recitation audio file
- one background video
- one surah number

### 1. Prepare audio and background

Set:

- `PRJ` as the project name
- `SURE_INDEX` as the surah number
- `tmp/${PRJ}-sound.wav` as the recitation WAV
- `tmp/${PRJ}-bg.mp4` as the background video

### 2. Run forced alignment

This generates `tmp/${PRJ}-sound.txt`:

```bash
ctc-forced-aligner \
  --audio_path "tmp/${PRJ}-sound.wav" \
  --text_path "data/quran-simple-plain-${SURE_INDEX}.txt" \
  --language "ara" \
  --alignment_model "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
```

### 3. Render the final movie

```bash
python src/create_movie.py \
  "data/quran-simple-plain-${SURE_INDEX}.txt" \
  "tmp/${PRJ}-sound.txt" \
  "tmp/${PRJ}-sound.wav" \
  "out/${PRJ}.mp4" \
  "tmp/${PRJ}-bg.mp4" \
  "${SURE_INDEX}" \
  --font quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf \
  --font_size 100 \
  --files "tmp/${PRJ}_files.txt" \
  --title "$(printf "%03d\n" "$SURE_INDEX") surah" \
  --title_font quran.com-frontend-next/public/fonts/quran/surah-names/v1/sura_names.ttf \
  --title_font_size 100 \
  --size_x 1920 \
  --size_y 1080 \
  --interline 30 \
  --stroke_width 5
```

## Persian Surah Workflow

Use this when you want one surah at a time with Arabic text and Persian translation on screen.

Run:

```bash
s=59 zsh src/persian-recitation.sh
```

Optional variants:

```bash
RECITATION_ONLY=1 s=59 zsh src/persian-recitation.sh
RECITATION_ONLY=1 RECITATION_TEMPLATE="https://tanzil.net/res/audio/shateri/{sura}{ayah}.mp3" s=100 zsh src/persian-recitation.sh
```

This workflow depends on the Tanzil-based data layout under `data/persian-recitation/`.

## Juz Workflows

### Ayah-by-ayah juz video

```bash
j=30 bash src/persian-recitation-juz.sh
```

With a different reciter:

```bash
RECITATION_TEMPLATE="https://tanzil.net/res/audio/shateri/{sura}{ayah}.mp3" j=30 bash src/persian-recitation-juz.sh
```

### Page-based juz video

```bash
j=1 bash src/persian-recitation-juz-by-page.sh
```

Both workflows can use `data/persian-recitation/bg_urls.txt` for background selection when present.

## Unified Script Reference

The repository has a unified movie entry point:

```bash
python3 src/create_movie_quran.py ...
```

It supports two modes:

| Mode | Purpose |
|------|---------|
| `sura` | One surah with prepared segment mapping and combined audio |
| `juz` | One juz in `ayah` view or `page` view |

### Example: Juz ayah view

```bash
python3 src/create_movie_quran.py juz 30 out/juz_30_parhizgar.mp4 --view ayah \
  --translation_root data/persian-recitation \
  --fps 30 \
  --speed 2.0 \
  --include_translation_audio
```

### Example: Juz page view

```bash
python3 src/create_movie_quran.py juz 1 out/juz_1_pages.mp4 --view page \
  --translation_root data/persian-recitation \
  --fps 30
```

Useful options include:

- `--background_video`
- `--bg_clip_start`
- `--recitation_template`
- `--translation_audio_template`
- `--include_translation_audio`
- `--debug`
- `--debug_no_background`
- `--debug_pages`
- `--debug_limit_ayahs`

## Alignment Workflow

The newer alignment CLI can align one recitation and produce browser-reviewable output:

```bash
python3 -m quran_aligner.cli align path/to/audio.mp3 59 --output-dir alignment_out
python3 -m quran_aligner.cli serve --directory alignment_out
```

Main alignment outputs include:

- `index.html`
- `run.log`
- alignment text/json files in the chosen output directory

There is also an older standalone alignment app documented in [alignment-old/README.md](alignment-old/README.md).

## Uploading

### YouTube

Upload with:

```bash
python3 src/upload-videos.py --file out/video.mp4 --title "Title"
```

Credential setup is documented in [YOUTUBE_CREDENTIALS.md](YOUTUBE_CREDENTIALS.md).

### Aparat

Upload with:

```bash
python3 src/upload-aparat.py --file out/video.mp4 --title "عنوان"
```

This uses exported Aparat browser cookies. The script docstring explains the cookie export flow.

### Mirror YouTube to Aparat

```bash
python3 src/youtube_to_aparat.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Common options:

| Option | Description |
|--------|-------------|
| `--playlist` | Aparat playlist ID or playlist name |
| `--visibility` | `public` or `private` |
| `--output-dir` | Download directory for the temporary file |
| `--keep` | Keep the downloaded file after upload |
| `--cookies` | Path to Aparat cookies file |
| `--yt-dlp` | Path to the `yt-dlp` executable |

## Notes

- Background darkening and other visual refinements are still useful future improvements.
- Some older one-off per-surah and per-project command notes were intentionally kept out of the top-level README to keep navigation cleaner.
- If you need the historical ad hoc command history, it still exists in git history.
