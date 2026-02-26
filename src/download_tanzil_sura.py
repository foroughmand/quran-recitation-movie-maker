#!/usr/bin/env python3
"""
Download for one sura: recitation audio, translation audio, and Persian
translation text. Uses tanzil.ir/tanzil.net URLs; recitation and translation
audio URLs must contain a 6-digit placeholder (e.g. 013042 for sura 13 ayah 42)
which is replaced with the current sura/ayah. Translation text URL points to
a single file with the whole Quran (one verse per line, 6236 lines).

Usage:
  python3 src/download_tanzil_sura.py [options] <sura_index> <num_ayas> <output_dir>

Example:
  python3 src/download_tanzil_sura.py 59 24 data/persian-recitation/sura_59
  python3 src/download_tanzil_sura.py --recitation-url "https://..." 59 24 data/persian-recitation/sura_59

Output under <output_dir>:
  recitation_audio/1.mp3, 2.mp3, ...
  translation_audio/1.mp3, 2.mp3, ...
  translation_text/1.txt, 2.txt, ...   (one line per ayah, Persian)
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error

# Verse count per sura (1–114); used to compute line index in tanzil full-Quran text.
SURA_AYAH_COUNTS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
    111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
    54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
    49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52,
    44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19,
    26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3,
    6, 3, 5, 4, 5, 6,
]


def download_url(url, path, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return True
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {url}")
        return False
    except Exception as e:
        print(f"  Error: {e}: {url}")
        return False


def audio_url_for_ayah(template_url: str, sura: int, ayah: int) -> str:
    """Replace 6-digit sura/ayah placeholder in URL (e.g. 013042 -> 059001)."""
    return re.sub(r"\d{6}", f"{sura:03d}{ayah:03d}", template_url, count=1)


def download_recitation_ayah(sura: int, ayah: int, out_path: str, base_url: str) -> bool:
    url = audio_url_for_ayah(base_url, sura, ayah)
    return download_url(url, out_path)


def download_translation_audio_ayah(
    sura: int, ayah: int, out_path: str, base_url: str
) -> bool:
    if not (base_url or "").strip():
        return False
    url = audio_url_for_ayah(base_url, sura, ayah)
    return download_url(url, out_path)


def verse_to_line_index(sura: int, ayah: int) -> int:
    """1-based line number for (sura, ayah) in tanzil full-Quran text (6236 lines)."""
    if sura < 1 or sura > 114:
        return 0
    line = sum(SURA_AYAH_COUNTS[: sura - 1]) + ayah
    return line


def fetch_tanzil_translation_text(
    translation_text_url: str,
    sura_index: int,
    num_ayas: int,
    out_dir: str,
    trans_text_dir: str,
) -> None:
    """Download full Quran translation from tanzil.net and write per-ayah files."""
    cache_path = os.path.join(out_dir, "_tanzil_full_translation.txt")
    if not os.path.isfile(cache_path):
        print("  Downloading full translation text (one-time)...")
        if not download_url(translation_text_url, cache_path):
            print("  Failed to download translation text.")
            return
    with open(cache_path, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]
    for a in range(1, num_ayas + 1):
        path = os.path.join(trans_text_dir, f"{a}.txt")
        if os.path.isfile(path):
            print(f"  {a}: exists", end="\r")
            continue
        idx = verse_to_line_index(sura_index, a)
        if 1 <= idx <= len(lines):
            text = lines[idx - 1]
            # Optional sura:ayah prefix (e.g. "13:42\tTranslation")
            if "\t" in text:
                text = text.split("\t", 1)[-1]
            if "|" in text:
                text = text.split("|", 2)[-1]
            text = text.strip()
        else:
            text = ""
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  {a}: ok", end="\r")


def fetch_persian_translation_ayah_quran_api(sura: int, ayah: int) -> str:
    """Fallback: fetch one verse from Quran.com API (translation ID 135)."""
    try:
        url = (
            "https://api.quran.com/api/v4/verses/by_key/"
            f"{sura}:{ayah}?translations=135"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        for t in data.get("verse", {}).get("translations", []):
            return (t.get("text") or "").strip()
    except Exception as e:
        print(f"  Translation text error {sura}:{ayah}: {e}")
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Download recitation audio, translation audio, and Persian translation text for one sura."
    )
    parser.add_argument(
        "--recitation-url",
        default="https://tanzil.ir/res/audio/shateri/013042.mp3",
        help="URL template for recitation audio; a 6-digit number (e.g. 013042) is replaced by sura/ayah (default: tanzil.ir shateri)",
    )
    parser.add_argument(
        "--translation-audio-url",
        default="https://tanzil.ir/res/audio/fa.fooladvand/013042.mp3",
        help="URL template for translation audio (same 6-digit replacement). Use empty string to skip (default: tanzil.ir fa.fooladvand)",
    )
    parser.add_argument(
        "--translation-text-url",
        default="https://tanzil.net/trans/?transID=fa.fooladvand&type=txt-2",
        help="URL to full-Quran translation text (one verse per line, 6236 lines). Use empty string to use Quran.com API fallback (default: tanzil.net fa.fooladvand)",
    )
    parser.add_argument(
        "sura_index",
        type=int,
        help="Sura number (1–114)",
    )
    parser.add_argument(
        "num_ayas",
        type=int,
        help="Number of ayahs in this sura",
    )
    parser.add_argument(
        "output_dir",
        help="Output directory (e.g. data/persian-recitation/sura_59)",
    )
    args = parser.parse_args()

    sura_index = args.sura_index
    num_ayas = args.num_ayas
    out_dir = args.output_dir.rstrip("/")
    recitation_url = (args.recitation_url or "").strip()
    translation_audio_url = (args.translation_audio_url or "").strip()
    translation_text_url = (args.translation_text_url or "").strip()

    rec_dir = os.path.join(out_dir, "recitation_audio")
    trans_audio_dir = os.path.join(out_dir, "translation_audio")
    trans_text_dir = os.path.join(out_dir, "translation_text")
    for d in (rec_dir, trans_audio_dir, trans_text_dir):
        os.makedirs(d, exist_ok=True)

    if not recitation_url:
        print("Error: --recitation-url is required.")
        sys.exit(1)

    print("Downloading recitation audio...")
    # For suras that start with Bismillah (not 1 = Al-Hamd, not 9 = Tawba), also download 1:1 as "0.mp3"
    needs_bismillah = sura_index not in (1, 9)
    if needs_bismillah:
        bismillah_path = os.path.join(rec_dir, "0.mp3")
        if os.path.isfile(bismillah_path):
            print("  0 (Bismillah): exists", end="\r")
        else:
            ok = download_recitation_ayah(1, 1, bismillah_path, recitation_url)
            print(f"  0 (Bismillah): {'ok' if ok else 'failed'}", end="\r")
    for a in range(1, num_ayas + 1):
        path = os.path.join(rec_dir, f"{a}.mp3")
        if os.path.isfile(path):
            print(f"  {a}: exists", end="\r")
            continue
        ok = download_recitation_ayah(sura_index, a, path, recitation_url)
        print(f"  {a}: {'ok' if ok else 'failed'}", end="\r")

    if translation_audio_url:
        print("Downloading translation audio...")
        for a in range(1, num_ayas + 1):
            path = os.path.join(trans_audio_dir, f"{a}.mp3")
            if os.path.isfile(path):
                print(f"  {a}: exists", end="\r")
                continue
            ok = download_translation_audio_ayah(
                sura_index, a, path, translation_audio_url
            )
            print(f"  {a}: {'ok' if ok else 'failed'}", end="\r")
    else:
        print("Skipping translation audio (no --translation-audio-url).")

    print("Fetching Persian translation text...")
    if translation_text_url:
        fetch_tanzil_translation_text(
            translation_text_url, sura_index, num_ayas, out_dir, trans_text_dir
        )
    else:
        print("  (using Quran.com API fallback)")
        for a in range(1, num_ayas + 1):
            path = os.path.join(trans_text_dir, f"{a}.txt")
            if os.path.isfile(path):
                print(f"  {a}: exists", end="\r")
                continue
            text = fetch_persian_translation_ayah_quran_api(sura_index, a)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"  {a}: ok", end="\r")

    print("Done.", out_dir)


if __name__ == "__main__":
    main()
