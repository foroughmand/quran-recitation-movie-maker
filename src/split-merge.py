import os
import re
import tempfile
import subprocess
from pydub import AudioSegment

def time_to_float(time_star: str):
    if time_star.find('*') != -1:
        x = time_star.split('*')
        return float(x[0]) * 60 + float(x[1])
    return float(time_star)

def parse_split_list(split_str):
    """Parse split list of format 'AYE:TIME,...' into list of (AYE, TIME)."""
    if split_str == "": return []
    pairs = split_str.strip().split(",")
    parsed = [(int(p.split(":")[0]), time_to_float(p.split(":")[1])) for p in pairs]
    return parsed

def split_audio(prj_prefix, audio_path, split_times, out_dir):
    audio = AudioSegment.from_mp3(audio_path)
    prev_time = 0
    audio_chunks = []

    for i, (_, time_point) in enumerate(split_times + [(-1, len(audio))]):
        chunk = audio[prev_time * 1000: time_point * 1000]
        # chunk_path = os.path.join(out_dir, f"{prj_prefix}_sound_{i}.wav")
        chunk_path = f"{prj_prefix}_sound_{i}.wav"
        chunk.export(chunk_path, format="wav")
        audio_chunks.append(chunk_path)
        prev_time = time_point

    return audio_chunks

def split_text(prj_prefix, text_path, split_tags, out_dir):
    with open(text_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    split_texts = []
    last_index = 0
    for i, (idx, _) in enumerate(split_tags + [(len(lines)+1, -1)]):
        # try:
        #     idx = lines.index(tag, last_index)
        # except ValueError:
        #     raise ValueError(f"Tag '{tag}' not found in text file.")

        chunk_lines = lines[last_index:(idx-1)]
        # chunk_path = os.path.join(out_dir, f"{prj_prefix}_text_{i}.txt")
        chunk_path = f"{prj_prefix}_text_{i}.txt"
        with open(chunk_path, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk_lines) + "\n")
        split_texts.append(chunk_path)
        last_index = idx-1

    return split_texts

def run_ctc_forced_aligner(audio_path, text_path, out_dir):
    # with open(os.path.splitext(audio_path)[0] + ".txt", 'w') as f:
    #     print("0.0-0.0: Text", file=f)
    # return

    cmd = [
        "ctc-forced-aligner",
        "--audio_path", audio_path,
        "--text_path", text_path,
        "--language", "ara",
        "--alignment_model", "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
    ]
    print('run_ctc_forced_aligner ', ' '.join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)

def shift_timestamps(input_txt, offset_sec):
    pattern = re.compile(r"^([-0-9.]*)-([-0-9.]*):\s*(.*)")
    adjusted_lines = []
    lines = []

    with open(input_txt, "r", encoding="utf-8") as f:
        for line in f:
            lines.append(line)
            match = pattern.match(line.strip())
            if match:
                start = float(match.group(1)) + offset_sec
                end = float(match.group(2)) + offset_sec
                text = match.group(3)
                adjusted_lines.append(f"{start:.2f}-{end:.2f}: {text}")
            else:
                adjusted_lines.append(line.strip())

    # print(f"lines: {lines} {offset_sec}", file=sys.stderr)
    # print(f"adjusted_lines: {adjusted_lines}", file=sys.stderr)
    return adjusted_lines

def process_alignment(prj_prefix, audio_path, text_path, split_str):
    split_tags_times = parse_split_list(split_str)
    print(f'split_tags_times={split_tags_times}', file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_chunks = split_audio(prj_prefix, audio_path, split_tags_times, tmpdir)
        print(f'audio_chunks={audio_chunks}', file=sys.stderr)
        text_chunks = split_text(prj_prefix, text_path, split_tags_times, tmpdir)
        print(f'text_chunks={text_chunks}', file=sys.stderr)

        all_lines = []

        for i, (audio_chunk, text_chunk) in enumerate(zip(audio_chunks, text_chunks)):
            # if i >= 4: break
            run_ctc_forced_aligner(audio_chunk, text_chunk, tmpdir)
            aligned_txt = os.path.splitext(audio_chunk)[0] + ".txt"
            # aligned_txt = os.path.join(tmpdir, os.path.basename(aligned_txt))

            adjusted = shift_timestamps(aligned_txt, split_tags_times[i-1][1] if i-1 >= 0 else 0)
            all_lines.extend(adjusted)

    return all_lines

import sys
def main():
    audio_path = sys.argv[1]
    text_path = sys.argv[2]
    # "5:12.33,9:15.12" -> Aye 5 starts from 12.33, Aye 9 starts from 15.12, [Aye 1 starts from 0.0]
    split_str = sys.argv[3]
    prj_prefix = sys.argv[4]

    result_lines = process_alignment(prj_prefix, audio_path, text_path, split_str)

    # with sys.stdout as f:
    f = sys.stdout
    f.write("\n".join(result_lines))

    print("Alignment complete. Output saved to 'stdout'.", file=sys.stderr)

if __name__ == "__main__":
    main()
