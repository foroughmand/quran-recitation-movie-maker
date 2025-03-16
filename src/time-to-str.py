import sys
import re

def time_to_srt_format(seconds):
    milliseconds = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

with open(sys.argv[1], 'r', encoding='utf-8') as infile, open(sys.argv[2], 'w', encoding='utf-8') as outfile:
    for i, line in enumerate(infile, 1):
        match = re.match(r'(\d+\.\d+)-(\d+\.\d+):\s*(.+)', line)
        if match:
            start_time = time_to_srt_format(float(match.group(1)))
            end_time = time_to_srt_format(float(match.group(2)))
            text = match.group(3).strip()
            outfile.write(f"{i}\n{start_time} --> {end_time}\n{text}\n\n")

