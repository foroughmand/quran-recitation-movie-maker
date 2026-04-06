#!/usr/bin/env python3
"""
Build combined WAV and segment mapping for Persian recitation movie: for each
ayah, one segment for recitation then one for translation. So we have
2 * num_ayas segments; each segment line: start_sec end_sec ayah_index.

Usage:
  python3 src/build_persian_audio.py <sura_dir> <sura_index> <num_ayas>
  python3 src/build_persian_audio.py --skip-translation <sura_dir> <sura_index> <num_ayas>

Example:
  python3 src/build_persian_audio.py data/persian-recitation/sura_59 59 24

Reads:
  <sura_dir>/recitation_audio/0.mp3 (optional; Bismillah prepended to first ayah for suras 2-8, 10-114)
  <sura_dir>/recitation_audio/1.mp3, 2.mp3, ...
  <sura_dir>/translation_audio/1.mp3, 2.mp3, ... (optional; if missing, only recitation)
Writes:
  <sura_dir>/combined.wav
  <sura_dir>/segment_mapping.txt  (format: start end ayah_number, one per segment)
"""
import os
import sys

try:
    from pydub import AudioSegment
except ImportError:
    print("pydub required: pip install pydub")
    sys.exit(1)


def main():
    args = sys.argv[1:]
    skip_translation = False
    if args and args[0] == "--skip-translation":
        skip_translation = True
        args = args[1:]
    if len(args) < 3:
        print(__doc__.strip())
        sys.exit(1)
    sura_dir = args[0].rstrip("/")
    sura_index = int(args[1])
    num_ayas = int(args[2])

    rec_dir = os.path.join(sura_dir, "recitation_audio")
    trans_dir = os.path.join(sura_dir, "translation_audio")
    combined_path = os.path.join(sura_dir, "combined.wav")
    mapping_path = os.path.join(sura_dir, "segment_mapping.txt")

    segments = []  # (start_sec, end_sec, ayah_number)
    current = 0.0
    combined = AudioSegment.empty()
    bismillah_file = os.path.join(rec_dir, "0.mp3")
    prepend_bismillah = sura_index not in (1, 9) and os.path.isfile(bismillah_file)

    for a in range(1, num_ayas + 1):
        # Recitation segment (for first ayah and suras 2-8/10-114, prepend Bismillah audio)
        rec_file = os.path.join(rec_dir, f"{a}.mp3")
        if not os.path.isfile(rec_file):
            print(f"Missing: {rec_file}")
            sys.exit(1)
        rec = AudioSegment.from_file(rec_file)
        if a == 1 and prepend_bismillah:
            bism = AudioSegment.from_file(bismillah_file)
            rec = bism + rec
        start_rec = current
        current += len(rec) / 1000.0
        segments.append((start_rec, current, a))
        combined += rec

        # Translation segment (optional; skipped when --skip-translation)
        if not skip_translation:
            trans_file = os.path.join(trans_dir, f"{a}.mp3")
            if os.path.isfile(trans_file):
                trans = AudioSegment.from_file(trans_file)
                start_trans = current
                current += len(trans) / 1000.0
                segments.append((start_trans, current, a))
                combined += trans

    combined.export(combined_path, format="wav")
    with open(mapping_path, "w", encoding="utf-8") as f:
        for start, end, ayah in segments:
            f.write(f"{start:.3f} {end:.3f} {ayah}\n")
    print(f"Wrote {combined_path} and {mapping_path} ({len(segments)} segments)")


if __name__ == "__main__":
    main()
