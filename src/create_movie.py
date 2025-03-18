import re, sys
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ImageClip, AudioFileClip


# Function to parse the mapping file
def parse_mapping_file(mapping_file):
    ayat_data = []
    with open(mapping_file, 'r', encoding='utf-8') as file:
        for line in file:
            match = re.match(r'(\d+\.\d+)-(\d+\.\d+):\s*(.+)', line.strip())
            if match:
                start_time = float(match.group(1))
                end_time = float(match.group(2))
                text = match.group(3).strip()
                ayat_data.append((start_time, end_time, text))
    return ayat_data

def parse_text_File(text_file):
    # print('parse_text_File', text_file)
    text_data = []
    with open(text_file, 'r', encoding='utf-8') as file:
        for line in file:
            text_data.append(line.strip())
    return text_data

# # Paths to your files
# text_file = 'q-taha.txt'
# mapping_file = 'q-taha-sound.txt'
# audio_file = 'q-taha-sound.mp3'
# background_image = 'q-taha.jpg'
# output_video = 'q-taha-video.mp4'

import argparse
parser = argparse.ArgumentParser(description='Create a video from text, audio, and background image.')
parser.add_argument('text_file', help='Path to the text file containing the script.')
parser.add_argument('mapping_file', help='Path to the mapping file (currently unused).')
parser.add_argument('audio_file', help='Path to the audio file.')
# parser.add_argument('background_image', help='Path to the background image file.')
parser.add_argument('output_prefix', help='Prefix for output files for each aye.')
parser.add_argument('background_video', help='Path to the video file.')
parser.add_argument('surah_number', type=int, help='Sure number.')

parser.add_argument('--title', help='File title.')
parser.add_argument('--title_font', default='HM_XNiloofarBd.ttf', help='Font.')
parser.add_argument('--title_font_size', type=int, default=50, help='Font size.')
parser.add_argument('--title_color', default='white', help='Text color.')
parser.add_argument('--title_margin_h', type=int, default=100, help='Horizontal margin.')
parser.add_argument('--title_margin_v', type=int, default=50, help='Vertical margin.')
parser.add_argument('--title_stroke_color', default='#0a0a0a', help='Color of the text stroke (outline). Default is black.')
parser.add_argument('--title_stroke_width', type=int, default=3, help='Width of the text stroke in pixels. Default is 1.')

parser.add_argument('--add_aye_number', action=argparse.BooleanOptionalAction, default=True, help='Add aye number to the end of line.')

parser.add_argument('--fps', type=int, default=27, help='Frames per second.')
parser.add_argument('--font', default='HM_XNiloofarBd.ttf', help='Font.')
parser.add_argument('--font_size', type=int, default=50, help='Font size.')
parser.add_argument('--color', default='white', help='Text color.')
parser.add_argument('--margin_h', type=int, default=200, help='Horizontal margin.')
parser.add_argument('--margin_v', type=int, default=20, help='Vertical margin.')

parser.add_argument('--stroke_color', default='black', help='Color of the text stroke (outline). Default is black.')
parser.add_argument('--stroke_width', type=int, default=1, help='Width of the text stroke in pixels. Default is 1.')
parser.add_argument('--interline', type=int, default=50, help='Spacing between lines of text. Default is 50.')

# parser.add_argument('--fill_silent', type-float, default=1.0, help='Fill silence shorter than this with keeping text for the next word.')
parser.add_argument('--files', help='List of created files.')

parser.add_argument('--text_render_method', default='quran.com', help='How to render ayes. Options: quran.com, file.')
parser.add_argument('--bg_clip_start', help='If present, bg file will be clipped.')
parser.add_argument('--bg_clip_end', help='If present, bg file will be clipped.')
parser.add_argument('--size_x', type=int, default=1280, help='X-resolution.')
parser.add_argument('--size_y', type=int, default=780, help='X-resolution.')



args = parser.parse_args()

# Parse the mapping file
ayat_data = parse_mapping_file(args.mapping_file)
text_data = parse_text_File(args.text_file)
# print(text_data)


# Load the audio file
audio_clip = AudioFileClip(args.audio_file)

# Resize the background image if necessary
# bg_image_clip = ImageClip("q-taha.jpg")
bg_image_clip = VideoFileClip(args.background_video).without_audio()
if args.bg_clip_start is not None and args.bg_clip_end is not None:
    bg_image_clip = bg_image_clip.subclipped(start_time=args.bg_clip_start, end_time=args.bg_clip_end)
    print(f'Clipping the bg video to {args.bg_clip_start}-{args.bg_clip_end}')

from moviepy.video.fx import Loop
bg_image_clip = bg_image_clip.with_effects([Loop(audio_clip.duration)])
# .loop(duration = audio_clip.duration)
bg_image_clip = bg_image_clip.resized((args.size_x, args.size_y))  # DEBUG (1280, 720)

x = VideoFileClip(args.background_video)

## Set the duration of the background image to match the audio
#bg_image_clip = bg_image_clip.with_duration(audio_clip.duration)

# Set the audio to the background image
# bg_image_clip = bg_image_clip.with_audio(audio_clip)

# Create text clips for each Ayah

def number_persian(n):
    n = str(n)
    anl = '۰۱۲۳۴۵۶۷۸۹'
    for i, ai in enumerate(anl):
        n = n.replace(str(i), ai)
    return n

def finalize(chunk_start_time, chunk_end_time, bg_image_clip, text_clips, chunk_index, extra_clips):
    bg_image_clip_chunk = bg_image_clip.subclipped(chunk_start_time, chunk_end_time)
    # bg_image_clip_chunk = bg_image_clip.with_duration(chunk_end_time - chunk_start_time)
    audio_subclip = audio_clip.subclipped(chunk_start_time, chunk_end_time)
    bg_image_clip_chunk = bg_image_clip_chunk.with_audio(audio_subclip)
    
    video = CompositeVideoClip([bg_image_clip_chunk] + text_clips + extra_clips)
    fn = args.output_prefix + f"{chunk_index}.mp4"
    # if args.output_prefix + f"{chunk_index}" in ["tmp/q-anbia-abkar_part_104", "tmp/q-anbia-abkar_part_103", "tmp/q-anbia-abkar_part_97", "tmp/q-anbia-abkar_part_87", "tmp/q-anbia-abkar_part_84", "tmp/q-anbia-abkar_part_82", "tmp/q-anbia-abkar_part_79", "tmp/q-anbia-abkar_part_78", "tmp/q-anbia-abkar_part_74", "tmp/q-anbia-abkar_part_73", "tmp/q-taha-abkar_part_134", "tmp/q-anbia-abkar_part_47", "tmp/q-najm-abkar_part_32", "tmp/q-taha-abkar_part_131", "tmp/q-najm-abkar_part_31", "tmp/q-taha-abkar_part_130", "tmp/q-anbia-abkar_part_44", "tmp/q-anbia-abkar_part_43", "tmp/q-najm-abkar_part_26", "tmp/q-anbia-abkar_part_39", "tmp/q-taha-abkar_part_123", "tmp/q-najm-abkar_part_23", "tmp/q-anbia-abkar_part_36", "tmp/q-taha-abkar_part_121", "tmp/q-anbia-abkar_part_30", "tmp/q-taha-abkar_part_114", "tmp/q-anbia-abkar_part_24", "tmp/q-taha-abkar_part_97", "tmp/q-taha-abkar_part_96", "tmp/q-taha-abkar_part_94", "tmp/q-taha-abkar_part_87", "tmp/q-anbia-abkar_part_3", "tmp/q-taha-abkar_part_86", "tmp/q-taha-abkar_part_81", "tmp/q-taha-abkar_part_77", "tmp/q-taha-abkar_part_72", "tmp/q-taha-abkar_part_71", "tmp/q-taha-abkar_part_53", "tmp/q-taha-abkar_part_47", "tmp/q-taha-abkar_part_40", "tmp/q-taha-abkar_part_39"]: #DEBUG  or chunk_index == 1
    # if chunk_index == 1: #DEBUG  or 
    if True:
        video.write_videofile(fn, codec='libx264', fps=args.fps, audio_codec='aac') #DEBUG fps

    # audio_subclip.close()
    # bg_image_clip_chunk.close()
    print(f'Finalizing chunk={chunk_index} text_clips={len(text_clips)} time={chunk_start_time}-{chunk_end_time} fn={fn}')
    # for t in text_clips:
    #     print(f'  {t.start}-{t.end}={t.duration}')
    if files_f is not None:
        print(fn, file=files_f)

label_clip = TextClip(
        text=args.title if args.title is not None else '',
        # text='طه',
        font_size=args.title_font_size, 
        font=args.title_font, 
        color=args.title_color, 
        stroke_color=args.title_stroke_color, 
        stroke_width=args.title_stroke_width,
        # interline=args.interline,
        size=(bg_image_clip.size[0] - args.title_margin_h, bg_image_clip.size[1] - args.title_margin_v), 
        method='label',
        text_align="center", horizontal_align="right", vertical_align="top").with_position((0, args.title_margin_v/2))


files_f = open(args.files, 'w') if args.files is not None else None

def method_1():
    current_aye, current_word = 0, 0
    text_clips = []
    chunk_start_time = 0
    for i, (start_time, end_time, text) in enumerate(ayat_data):
        # print(i, start_time, end_time, text)
        aye_s = text_data[current_aye].split(' ')
        if current_word+1 < len(aye_s):
            # not the last word,
            #   then fill the space to the next word and keep the text here
            end_time = ayat_data[i+1][0]

        # if current_aye > 6: break
        # if text_data[current_aye].find(text) == -1:
        #     if current_aye+1 < len(text_data) and text_data[current_aye+1].find(text) != -1:
        #         finalize(chunk_start_time, start_time, bg_image_clip, text_clips, current_aye+1)
        #         chunk_start_time = start_time
        #         # for c in text_clips:
        #         #     c.close()
        #         if len(text_data[current_aye].split(' ')) != len(text_clips):
        #             print(text_data[current_aye].split(' '), [t.text for t in text_clips])
        #         text_clips = []
        #         current_aye += 1
        #     else:
        #         print(f'W text={text} is not aye={current_aye}={text_data[current_aye]} nor in next aye={text_data[current_aye+1] if current_aye+1 < len(text_data) else ''} ')
        
        # if text_data[current_aye].split(' ')[current_word] != text:
        #     print(f'W {current_aye}:{current_word} {text_data[current_aye].split(' ')[current_word]}!={text} aye={text_data[current_aye].split(' ')}')

        h_text = ' '.join(aye_s[0:current_word] + [f'{aye_s[current_word]}'] + aye_s[current_word+1:])
        if args.add_aye_number:
            h_text += f'﴿{number_persian(current_aye+1)}﴾'
        # txt_clip = (TextClipEx(
        #         text_pre=' '.join(aye_s[0:current_word]) +' ', 
        #         text_highlight=aye_s[current_word], 
        #         text_post=(' ' if current_word+1<len(aye_s) else '') + ' '.join(aye_s[current_word+1:])+f'({current_aye+1})', 
        w, h = bg_image_clip.size
        txt_clip = (TextClip(
                text=h_text,
                font_size=args.font_size, 
                font=args.font, 
                color=args.color, 
                stroke_color=args.stroke_color, 
                stroke_width=args.stroke_width,
                interline=args.interline,
                size=(w - args.margin_h, h - args.margin_v), 
                method='caption',
                text_align="center")
                    .with_start(start_time - chunk_start_time)
                    .with_duration(end_time - start_time)
                    .with_position('center'))
        text_clips.append(txt_clip)

        # t = TextClip()
        # t

        current_word += 1
        if current_word >= len(aye_s):
            # if current_aye+1 == 10:  # DEBUG

            next_start_time = ayat_data[i+1][0] if i+1 < len(ayat_data) else end_time
            
            finalize(chunk_start_time, next_start_time, bg_image_clip, text_clips, current_aye+1, [label_clip.with_duration(next_start_time - chunk_start_time)])
                # break
            current_aye += 1
            current_word = 0
            text_clips = []
            chunk_start_time = next_start_time

        # if i+1 == len(ayat_data):
        #     finalize(chunk_start_time, end_time, bg_image_clip, text_clips, current_aye+1)

# method_1()


def method_2():
    current_aye, current_word = 0, 0
    text_clips = []
    chunk_start_time = 0
    for i, (start_time, end_time, text) in enumerate(ayat_data):
        # print(i, start_time, end_time, text)
        aye_s = text_data[current_aye].split(' ')
        if current_word+1 < len(aye_s):
            # not the last word,
            #   then fill the space to the next word and keep the text here
            end_time = ayat_data[i+1][0]

        current_word += 1
        if current_word >= len(aye_s):
            next_start_time = ayat_data[i+1][0] if i+1 < len(ayat_data) else audio_clip.duration
            add_besmellah = False

            if args.text_render_method == 'quran.com':

                import requests

                # Fetch the ayah data from the Quran.com API
                api_url = f"https://api.quran.com/api/v4/verses/by_key/{args.surah_number}:{current_aye+1}?words=true"
                response = requests.get(api_url)

                if current_aye == 0:
                    response_besmellah = requests.get(f"https://api.quran.com/api/v4/verses/by_key/1:1?words=true")
                    add_besmellah = True

                if response.status_code == 200:
                    ayah_data = response.json()
                    words = ayah_data["verse"]["words"]
                    h_page = ayah_data["verse"]["page_number"]
                    
                    # Extract the Unicode characters for the words in the ayah
                    h_text = " ".join(word["code_v1"] for word in words)
                    h_text = h_text[:(len(h_text)-2)] + h_text[len(h_text)-1]

                    # h_font = "quran.com-frontend-next/public/fonts/quran/hafs/v1/ttf/p{h_page}.ttf"
                    h_font = args.font.format(h_page=h_page)
                    # h_font = h_font.format(h_page=h_page)
                    
                    # Display the result
                    print(f"Unicode representation of Surah {args.surah_number}, Ayah {current_aye} ({h_page}, font={h_font}): ")
                    print(h_text)
                else:
                    raise RuntimeError(f"Error fetching ayah data {response}. \n{api_url}")
            elif args.text_render_method == 'file':
                h_text = text_data[current_aye]
                if args.add_aye_number:
                    h_text += f'﴿{number_persian(current_aye+1)}﴾'
            else:
                raise RuntimeError(f"Invalid text_render_method {args.text_render_method}.")


            w, h = bg_image_clip.size
            txt_clip = (TextClip(
                    text=h_text,
                    font_size=args.font_size, 
                    font=h_font, 
                    color=args.color, 
                    stroke_color=args.stroke_color, 
                    stroke_width=args.stroke_width,
                    interline=args.interline,
                    # size=(w - args.margin_h, h - args.margin_v), 
                    size=(w - args.margin_h, None), 
                    method='caption',
                    text_align="center")
                        .with_start(chunk_start_time - chunk_start_time)
                        .with_duration(next_start_time - chunk_start_time)
                        .with_position('center'))
            text_clips.append(txt_clip)
            print(txt_clip.size)

            if add_besmellah:
                ayah_data = response_besmellah.json()
                words = ayah_data["verse"]["words"]
                h_page = ayah_data["verse"]["page_number"]
                
                h_text = " ".join(word["code_v1"] for word in words[:-1])
                h_font = args.font.format(h_page=h_page)

                besmellah_clip = (TextClip(
                        text=h_text,
                        font_size=args.font_size * 1.3, 
                        font=h_font, 
                        color=args.color, 
                        stroke_color=args.stroke_color, 
                        stroke_width=args.stroke_width,
                        interline=args.interline,
                        # size=(w - args.margin_h, h - args.margin_v), 
                        size=(w - args.margin_h, None), 
                        method='caption',
                        text_align="center")
                            .with_start(chunk_start_time - chunk_start_time)
                            .with_duration(next_start_time - chunk_start_time)
                            .with_position('center'))
                main_w, main_h = txt_clip.size
                sec_w, sec_h = besmellah_clip.size

                total_height = main_h + sec_h + args.interline

                final_clip = CompositeVideoClip([
                    txt_clip.with_position(('center', sec_h + args.interline)),
                    besmellah_clip.with_position(('center', 0))
                ], size=(w - args.margin_h, total_height)).with_position(('center', (h - total_height) / 2))

                del text_clips[-1]
                text_clips.append(final_clip)

            
            finalize(chunk_start_time, next_start_time, bg_image_clip, text_clips, current_aye+1, [label_clip.with_duration(next_start_time - chunk_start_time)])
            current_aye += 1
            current_word = 0
            text_clips = []
            chunk_start_time = next_start_time

        # if i+1 == len(ayat_data):
        #     finalize(chunk_start_time, end_time, bg_image_clip, text_clips, current_aye+1)

method_2()

# print('Loop finished')
audio_clip.close()
bg_image_clip.close()
if files_f is not None:
    files_f.close()
# # Combine the background and text clips
# video = CompositeVideoClip([bg_image_clip] + text_clips)

# # Write the final video file
# video.write_videofile(output_video, codec='libx264', fps=24, audio_codec='aac')

