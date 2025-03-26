import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


def to_hindi_numerals(number):
    """Convert Western digits (0-9) in a string or number to Eastern Arabic (Hindi) numerals."""
    hindi_digits = "٠١٢٣٤٥٦٧٨٩"
    return "".join(hindi_digits[int(d)] if d.isdigit() else d for d in str(number))

import requests

def fetch_surah_data():
    """Fetch Surah metadata from Quran.com API (v4)."""
    url = "https://api.quran.com/api/v4/chapters"
    headers = {
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    chapters = response.json().get("chapters", [])
    return {
        chapter["id"]: {
            "name": chapter["name_arabic"],
            "latin": chapter["name_simple"],
            "english": chapter["translated_name"]["name"]
        }
        for chapter in chapters
    }

sura_data = fetch_surah_data()

def get_video_config(file_path: str, sura_index: int, reciter: str = "ادریس ابکر") -> dict:
    """Build video metadata based on surah index and reciter."""
    sura = sura_data.get(sura_index)
    if not sura:
        raise ValueError(f"Surah index {sura_index} not found in Quran.com API.")

    sura_name = sura["name"]
    title = f"تلاوت سوره {sura_name} - {reciter}"
    description = (
        f"تلاوت سوره {sura_name} ({to_hindi_numerals(sura_index)}) - ترتیل\n"
        f"قاری: {reciter}\n"
        f"با تصویر پس‌زمینه طبیعت"
    )

    return {
        "video_path": file_path,
        "title": title,
        "description": description,
        "made_for_kids": False,
        "category": "10",  # Music
        "visibility": "public",
        "tags": ["تلاوت قرآن", f"سوره {sura_name}", reciter],
        "playlist": ["تلاوت قرآن"]
    }

# === CONFIG ===
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]

def get_authenticated_service():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, prompt the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

# === Upload Function ===
def upload_video(youtube, config):
    request_body = {
        "snippet": {
            "title": config["title"],
            "description": config["description"],
            "tags": config.get("tags", []),
            "categoryId": config.get("category", "22"),
        },
        "status": {
            "privacyStatus": config.get("visibility", "private"),
            "madeForKids": config.get("made_for_kids", False)
        }
    }

    media = MediaFileUpload(config["video_path"], chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"✅ Upload complete: https://www.youtube.com/watch?v={video_id}")

    for playlist_title in config.get("playlist", []):
        add_video_to_playlist(youtube, video_id, playlist_title)

# === Playlist Support ===
def add_video_to_playlist(youtube, video_id, playlist_title):
    playlists = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
    target = next((pl for pl in playlists["items"] if pl["snippet"]["title"] == playlist_title), None)

    if not target:
        print(f"🎵 Creating playlist: {playlist_title}")
        pl = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": playlist_title, "description": ""},
                "status": {"privacyStatus": "public"}
            }
        ).execute()
        playlist_id = pl["id"]
    else:
        playlist_id = target["id"]

    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id}
            }
        }
    ).execute()
    print(f"✅ Added to playlist: {playlist_title}")

import sys
if __name__ == "__main__":
    try:
        
        sura_index = int(sys.argv[1])
        file_path = sys.argv[2]

        video_config = get_video_config(file_path, sura_index)

        youtube = get_authenticated_service()
        upload_video(youtube, video_config)

    except HttpError as e:
        print(f"❌ YouTube API error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


# # exmaples/upload_video.py
# import asyncio
# import yt_upload as yt
# import datetime as dt


# async def main():
#     # examples/upload_videos.py
#     channel = yt.Channel(
#         user_data_dir="/home/hforoughmand/.config/google-chrome",
#         google_profile="Default",
#         cookies_path="cookies.json",
#     )
#     video1 = yt.Video(
#         video_path="../out/q-1-abkar.mp4",
#         title="تلاوت سوره حمد - ادریس ابکر",
#         description="تلاوت سوره انبیا (۲۱) - ترتیل\nقاری: ادریس ابکر\nبا تصویر پس‌زمینه طبیعت",
#         made_for_kids=False,
#         category=yt.category.MUSIC,
#         visibility=yt.visibility.PUBLIC,
#         playlist=["تلاوت قرآن", ],
#         tags=["تلاوت قرآن", "سوره حمد", "ادریس ابکر"],
#     )


#     async with channel(youtube_channel="UCitXjg_tU3A6XkVaBi6vEWg", change_language_to_eng = True) as upload:
#         await upload.upload_videos([video1])

# asyncio.run(main())
