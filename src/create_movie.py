import re
import argparse
import numpy as np
import ffmpeg
from pydub import AudioSegment
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from dataclasses import dataclass


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

parser.add_argument('--fps', type=int, default=30, help='Frames per second.')
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
parser.add_argument('--bg_clip_start', default="0", help='If present, bg file will be clipped.')
parser.add_argument('--bg_clip_end', help='If present, bg file will be clipped.')
parser.add_argument('--size_x', type=int, default=1280, help='X-resolution.')
parser.add_argument('--size_y', type=int, default=780, help='X-resolution.')
parser.add_argument('--video_range', help='If present, only videos with Aye-id in this range will be created. Note that the "--files" will be regenerated for all Ayes.')
parser.add_argument('--audio_skip', type=float, default=(-0.4), help='Skip this amount from audio file to sink the mp3 output with the actual wave file.')


import re

def time_to_seconds(time_str):
    match = re.match(r'(?:(\d+):)?(?:(\d+):)?(\d+)(?:\.(\d+))?', time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")

    hh = int(match.group(1)) if match.group(1) else 0
    mm = int(match.group(2)) if match.group(2) else 0
    ss = int(match.group(3)) if match.group(3) else 0
    ms = match.group(4) if match.group(4) else "0"

    # Normalize milliseconds to always be 3 digits (convert 5 -> 500, 67 -> 670)
    ms = int(ms.ljust(3, '0'))  # Pad right with zeros to make it 3 digits

    return hh * 3600 + mm * 60 + ss + ms / 1000

args = parser.parse_args()
video_range = [int(x) for x in args.video_range.split('-')] if args.video_range is not None else None

bg_clip_start_seconds = time_to_seconds(args.bg_clip_start)
# print(bg_clip_start_seconds)
# Parse the mapping file
ayat_data = parse_mapping_file(args.mapping_file)
text_data = parse_text_File(args.text_file)
# print(text_data)

# Load the background video
audio = AudioSegment.from_file(args.audio_file)

def number_persian(n):
    n = str(n)
    anl = '۰۱۲۳۴۵۶۷۸۹'
    for i, ai in enumerate(anl):
        n = n.replace(str(i), ai)
    return n


# Define a structure for text properties
@dataclass
class TextInfo:
    text: str
    font: str
    font_size: int
    font_color: str
    stroke_width: int
    stroke_color: str

# Function to create text overlay image and save to file
# def create_text_image(text, size, font_path, font_size, filename):
#     img = Image.new('RGBA', size, (0, 0, 0, 0))  # Black background
#     draw = ImageDraw.Draw(img)
#     font = ImageFont.truetype(font_path, font_size)
    
#     # Calculate text width and height correctly
#     text_bbox = draw.textbbox((0, 0), text, font=font)
#     text_width = text_bbox[2] - text_bbox[0]
#     text_height = text_bbox[3] - text_bbox[1]

#     # Position text in the center
#     position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
#     draw.text(position, text, font=font, fill=(255, 255, 255), stroke_fill=args.stroke_color, stroke_width=args.stroke_width)  # White text

#     img.save(filename, format='PNG')  # Save as PNG file
#     return filename


# Function to create full text overlay with multiple texts
def create_full_text_image(main_text_info, additional_text_info, short_text_info, size, margin, interline, filename):
    img = Image.new('RGBA', size, (0, 0, 0, 0))  # Solid black background
    draw = ImageDraw.Draw(img)
    
    short_font = ImageFont.truetype(short_text_info.font, short_text_info.font_size) if short_text_info else None

    min_top = margin[1]
    # Draw short text (if provided)
    if short_text_info is not None:
        draw.text((size[0] - margin[0], margin[1]), short_text_info.text, font=short_font, fill=(255, 255, 255), stroke_fill=short_text_info.stroke_color, stroke_width=short_text_info.stroke_width, anchor="ra")
        min_top += draw.textbbox((0, 0), short_text_info.text, font=short_font)[3]

    while True:
        main_font = ImageFont.truetype(main_text_info.font, main_text_info.font_size)
        
        # Wrap the main text
        max_width = size[0] - margin[0]  # Leave some margin
        words = main_text_info.text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            if draw.textbbox((0, 0), test_line, font=main_font)[2] < max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Positioning calculations
        total_text_height = sum(draw.textbbox((0, 0), line, font=main_font)[3] for line in lines)
        y_main_text = (size[1] - total_text_height + draw.textbbox((0, 0), lines[0], font=main_font)[3] - (len(lines)-1) * interline) // 2

        y_min = y_main_text - draw.textbbox((0, 0), lines[0], font=main_font)[3] // 2
        if additional_text_info is not None:
            additional_font = ImageFont.truetype(additional_text_info.font, additional_text_info.font_size)
            y_min -= draw.textbbox((0, 0), additional_text_info.text, font=additional_font)[3] + interline
        
        if y_min > min_top or main_text_info.font_size < 1: break

        # if main_text_info.font_size < 66: break
        print('Shrinking ', main_text_info.font_size)
        main_text_info.font_size *= 0.9
        interline *= 0.9
        if additional_text_info is not None:
            additional_text_info.font_size *= 0.9
    
    # Draw additional text (if provided)
    if additional_text_info is not None:
        additional_font = ImageFont.truetype(additional_text_info.font, additional_text_info.font_size)
        y_additional_text = y_main_text - draw.textbbox((0, 0), additional_text_info.text, font=additional_font)[3] // 2 - draw.textbbox((0, 0), lines[0], font=main_font)[3] // 2 - interline
        print(additional_text_info, draw.textbbox((0, 0), additional_text_info.text, font=additional_font), y_main_text, y_additional_text)
        draw.text((size[0] // 2, y_additional_text), additional_text_info.text, font=additional_font, fill=(255, 255, 255), stroke_fill=additional_text_info.stroke_color, stroke_width=additional_text_info.stroke_width, anchor="mm")
    
    # Draw main text with stroke
    y_text = y_main_text
    for line in lines:
        x_text = size[0] // 2
        draw.text((x_text, y_text), line, font=main_font, fill=(255, 255, 255),
                  stroke_width=main_text_info.stroke_width, stroke_fill=main_text_info.stroke_color, anchor="mm")
        y_text += draw.textbbox((0, 0), line, font=main_font)[3] + interline
    
    
    img.save(filename, format='PNG')
    return filename

import os


# Function to finalize and save video chunk
def finalize(chunk_start_time, next_start_time, aye_number, aye_text_info, besmellah_text_info, sure_name_text_info):
    actual_end_time = next_start_time
    if args.video_range is None or (args.video_range[0] <= aye_number and aye_number <- args.video_range[1]):
        output_video = f"{args.output_prefix}_{aye_number}.mp4"
        # temp_audio_filename = f"tmp/temp_audio_{aye_number}.wav"
        temp_image_filename = f"tmp/temp_text_{aye_number}.png"
        
        # Process and save audio chunk
        # chunk_audio = audio[chunk_start_time * 1000:next_start_time * 1000]  # Convert seconds to milliseconds
        # chunk_audio.export(temp_audio_filename, format='wav')
        
        # Process and save text image
        # create_text_image(h_text, (args.size_x, args.size_y), h_font, args.font_size, temp_image_filename)
        create_full_text_image(aye_text_info, besmellah_text_info, sure_name_text_info, (args.size_x, args.size_y), (args.margin_h, args.margin_v), args.interline, temp_image_filename)
        
        # FFmpeg processing
        frame_duration = 1 / args.fps
        rounded_frame_count = int((next_start_time - chunk_start_time) / frame_duration)
        rounded_duration = rounded_frame_count * frame_duration
        actual_end_time = chunk_start_time + rounded_duration

        print(f'Rendering aye={aye_number} time={chunk_start_time}-{next_start_time}({actual_end_time})={rounded_duration}')

        input_video = ffmpeg.input(args.background_video, ss=chunk_start_time + bg_clip_start_seconds
                                   #, to=chunk_start_time + bg_clip_start_seconds + rounded_duration
                                   ).video
        resized_video = input_video.filter('scale', args.size_x, args.size_y)
        # input_audio = ffmpeg.input(temp_audio_filename)
        input_image = ffmpeg.input(temp_image_filename)
        # , eof_action='repeat'
        video_with_overlay = resized_video.overlay(input_image, x='(main_w-overlay_w)/2', y='(main_h-overlay_h)/2')
        final_video = ffmpeg.output(video_with_overlay, 
                                    # input_audio, 
                                    output_video, 
                                    vframes = rounded_frame_count,
                                    # vcodec='libvpx-vp9', acodec='libopus', crf=30, b='0', r=args.fps, pix_fmt='yuv420p'
                                    vcodec='libx264', acodec='aac', r=args.fps, pix_fmt='yuv420p'
                                    )
        # print(' '.join(final_video.compile()))
        final_video.run(overwrite_output=True, quiet=True)
        # os.remove(temp_audio_filename)
        # os.remove(temp_image_filename)
        
        print(f"Generated {output_video}")
    if files_f is not None:
        print(output_video, file=files_f)
    return actual_end_time

import random

def finalize2(chunk_start_time, next_start_time, aye_number, aye_text_info, besmellah_text_info, sure_name_text_info):
    # actual_end_time = next_start_time
    # if args.video_range is None or (args.video_range[0] <= aye_number and aye_number <- args.video_range[1]):
    r = random.randint(1e5, 1e6-1)
    temp_image_filename = f"tmp/temp_text_{aye_number}_{r}.png"
    
    create_full_text_image(aye_text_info, besmellah_text_info, sure_name_text_info, (args.size_x, args.size_y), (args.margin_h, args.margin_v), args.interline, temp_image_filename)
    
    # input_audio = ffmpeg.input(temp_audio_filename)
    # input_image = ffmpeg.input(temp_image_filename)
    return (temp_image_filename, chunk_start_time, next_start_time)
        

def write_(img_overlays):
    input_video = ffmpeg.input(args.background_video, ss=bg_clip_start_seconds).video
    resized_video = input_video.filter('scale', args.size_x, args.size_y)
    # input_audio = ffmpeg.input(args.audio_file, ss=args.audio_skip)
    input_audio = ffmpeg.input(args.audio_file)
    # output_video = f"{args.output_prefix}_all.mp4"
    output_video = args.output_prefix

    print(img_overlays)
    overlays = resized_video
    for img_fn, start_time, end_time in img_overlays:
        # print(f'between(t,{start_time},{end_time})')
        img = ffmpeg.input(img_fn)
        overlays = ffmpeg.overlay(overlays, img, enable=f'between(t,{start_time+args.audio_skip},{end_time+args.audio_skip})', x='(main_w-overlay_w)/2', y='(main_h-overlay_h)/2')
        # overlays = ffmpeg.overlay(overlays, img)


    # print(' '.join(final_video.compile()))
    # os.remove(temp_audio_filename)
    # os.remove(temp_image_filename)
    # video_with_overlay = resized_video.overlay(input_image, x='(main_w-overlay_w)/2', y='(main_h-overlay_h)/2', eof_action='repeat')
    final_video = ffmpeg.output(overlays, 
                                input_audio, 
                                output_video, 
                                t=img_overlays[-1][2]+args.audio_skip,
                                shortest=None,  # Pass None to include flag without value
                                vcodec='libx264', acodec='aac', r=args.fps, pix_fmt='yuv420p'
                                )
    print(' '.join(final_video.compile()))

    final_video.run(overwrite_output=True)
    # , quiet=True
    print(f"Generated {output_video}")
        


files_f = open(args.files, 'w') if args.files is not None else None

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
        next_start_time = ayat_data[i+1][0] if i+1 < len(ayat_data) else len(audio) / 1000.0
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
                # print(f"Unicode representation of Surah {args.surah_number}, Ayah {current_aye} ({h_page}, font={h_font}): ")
                # print(h_text)
            else:
                raise RuntimeError(f"Error fetching ayah data {response}. \n{api_url}")
        elif args.text_render_method == 'file':
            h_text = text_data[current_aye]
            if args.add_aye_number:
                h_text += f'﴿{number_persian(current_aye+1)}﴾'
        else:
            raise RuntimeError(f"Invalid text_render_method {args.text_render_method}.")


        # w, h = bg_image_clip.size
        # txt_clip = (TextClip(
        #         text=h_text,
        #         font_size=args.font_size, 
        #         font=h_font, 
        #         color=args.color, 
        #         stroke_color=args.stroke_color, 
        #         stroke_width=args.stroke_width,
        #         interline=args.interline,
        #         # size=(w - args.margin_h, h - args.margin_v), 
        #         size=(w - args.margin_h, None), 
        #         method='caption',
        #         text_align="center")
        #             .with_start(chunk_start_time - chunk_start_time)
        #             .with_duration(next_start_time - chunk_start_time)
        #             .with_position('center'))
        # text_clips.append(txt_clip)
        # print(txt_clip.size)
        aye_text_info = TextInfo(h_text, h_font, args.font_size, args.color, args.stroke_width, args.stroke_color)

        besmellah_text_info = None
        if add_besmellah:
            ayah_data = response_besmellah.json()
            words = ayah_data["verse"]["words"]
            h_page = ayah_data["verse"]["page_number"]
            
            h_text = " ".join(word["code_v1"] for word in words[:-1])
            h_font = args.font.format(h_page=h_page)
            besmellah_text_info = TextInfo(h_text, h_font, args.font_size * 1.3, args.color, args.stroke_width, args.stroke_color)

        sure_name_text_info = TextInfo(args.title if args.title is not None else '', args.title_font, args.title_font_size, args.title_color, args.title_stroke_width, args.title_stroke_color)
        
        
        # actual_end_time = finalize(chunk_start_time, next_start_time, current_aye+1, 
        #             aye_text_info=aye_text_info,
        #             besmellah_text_info=besmellah_text_info,
        #             sure_name_text_info=sure_name_text_info
        #         )
        img_info = finalize2(chunk_start_time, next_start_time, current_aye+1, 
                    aye_text_info=aye_text_info,
                    besmellah_text_info=besmellah_text_info,
                    sure_name_text_info=sure_name_text_info
                )
        # print("img_info:", img_info)
        text_clips.append(img_info)
        current_aye += 1
        current_word = 0
        # text_clips = []
        chunk_start_time = next_start_time
        # chunk_start_time = actual_end_time


# print("text_clips:", text_clips)
write_(text_clips)
for img_fn, _, _ in text_clips:
    os.remove(img_fn)
