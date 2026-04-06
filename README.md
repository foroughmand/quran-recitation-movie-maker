# Quran Recitation Movie Maker

This repository is mainly for creating Quran recitation videos, preparing alignment outputs, and uploading finished videos.

All installation steps, data preparation, prerequisites, and detailed workflow notes are in [README.details.md](README.details.md).

## What do you want to do?

| Goal | How to do it | Details |
|------|---------------|---------|
| Create a classic surah video from one recitation audio file and one background video | Run the Arabic alignment pipeline, then render with `src/create_movie.py` | [Arabic surah workflow](README.details.md#arabic-surah-workflow) |
| Create a Persian surah video with Arabic text and Persian translation | Run `s=59 zsh src/persian-recitation.sh` | [Persian surah workflow](README.details.md#persian-surah-workflow) |
| Create a juz video, ayah by ayah | Run `j=30 bash src/persian-recitation-juz.sh` | [Juz workflows](README.details.md#juz-workflows) |
| Create a juz video, page by page with highlighted ayah | Run `j=1 bash src/persian-recitation-juz-by-page.sh` | [Juz workflows](README.details.md#juz-workflows) |
| Use the unified movie generator directly | Run `python3 src/create_movie_quran.py ...` in `sura` or `juz` mode | [Unified script reference](README.details.md#unified-script-reference) |
| Align a recitation audio file and review timings in the browser | Run `python3 -m quran_aligner.cli align ...` and then `python3 -m quran_aligner.cli serve ...` | [Alignment workflow](README.details.md#alignment-workflow) |
| Upload a finished video to YouTube | Run `python3 src/upload-videos.py ...` | [YouTube credentials](YOUTUBE_CREDENTIALS.md) |
| Upload a finished video to Aparat | Run `python3 src/upload-aparat.py ...` | [Aparat upload notes](README.details.md#uploading) |
| Mirror a YouTube video to Aparat | Run `python3 src/youtube_to_aparat.py "https://www.youtube.com/watch?v=..."` | [Mirror upload](README.details.md#uploading) |

## Where the details went

- Setup, dependencies, fonts, and data preparation: [README.details.md](README.details.md)
- YouTube OAuth setup: [YOUTUBE_CREDENTIALS.md](YOUTUBE_CREDENTIALS.md)
- Older alignment app notes: [alignment-old/README.md](alignment-old/README.md)
