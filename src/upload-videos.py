import argparse
import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


def to_hindi_numerals(number):
    """Convert Western digits (0-9) in a string or number to Eastern Arabic (Hindi) numerals."""
    hindi_digits = "٠١٢٣٤٥٦٧٨٩"
    return "".join(hindi_digits[int(d)] if d.isdigit() else d for d in str(number))

REPO_ROOT = os.path.abspath(os.path.dirname(__file__) + "/..")


def load_sura_names_fa():
    """Load Persian sura names from data/sura_names_fa.txt (index -> name)."""
    path = os.path.join(REPO_ROOT, "data", "sura_names_fa.txt")
    names = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    names[int(parts[0])] = parts[1]
    return names


def get_video_config(file_path: str, sura_index: int, reciter: str = "ادریس ابکر") -> dict:
    """Build video metadata based on surah index and reciter (Persian sura name)."""
    names_fa = load_sura_names_fa()
    sura_name_fa = names_fa.get(sura_index)
    if not sura_name_fa:
        sura_name_fa = str(sura_index)
    title = f"تلاوت سوره {sura_name_fa} - {reciter}"
    description = (
        f"تلاوت سوره {sura_name_fa} ({to_hindi_numerals(sura_index)}) - ترتیل\n"
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
        "tags": ["تلاوت قرآن", f"سوره {sura_name_fa}", reciter],
        "playlist": ["تلاوت قرآن"]
    }

# === CONFIG ===
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]

def get_authenticated_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Token revoked or invalid_grant (e.g. password changed, app permissions revoked)
                print("Token expired or revoked. Removing token.json and opening browser to sign in again.", file=sys.stderr)
                try:
                    os.remove("token.json")
                except OSError:
                    pass
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
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

def main():
    parser = argparse.ArgumentParser(
        description="Upload a video to YouTube (OAuth). Use either --file + metadata options, or sura_index + file for auto metadata.",
    )
    parser.add_argument("--file", "-f", help="Video file path to upload.")
    parser.add_argument("--title", "-t", help="Video title.")
    parser.add_argument("--description", "-d", default="", help="Video description.")
    parser.add_argument(
        "--visibility",
        "-v",
        choices=("public", "private", "unlisted"),
        default="private",
        help="Visibility: public, private, or unlisted (default: private).",
    )
    parser.add_argument(
        "--playlist",
        "-p",
        action="append",
        default=[],
        help="Playlist name(s) to add the video to (can be repeated). Creates playlist if missing.",
    )
    parser.add_argument("--tags", action="append", default=[], help="Tag (can be repeated).")
    parser.add_argument(
        "sura_index",
        nargs="?",
        type=int,
        default=None,
        help="Optional: sura number for auto title/description (use with file path only).",
    )
    parser.add_argument(
        "file_positional",
        nargs="?",
        default=None,
        help="Video file path (alternative to --file).",
    )
    args = parser.parse_args()

    file_path = args.file or args.file_positional
    if not file_path:
        parser.error("Provide video file via --file or as positional argument.")
    if not os.path.isfile(file_path):
        parser.error(f"File not found: {file_path}")

    if args.sura_index is not None and not args.title:
        video_config = get_video_config(file_path, args.sura_index)
    else:
        video_config = {
            "video_path": file_path,
            "title": args.title or os.path.splitext(os.path.basename(file_path))[0],
            "description": args.description or "",
            "made_for_kids": False,
            "category": "22",
            "visibility": args.visibility,
            "tags": args.tags if args.tags else [],
            "playlist": args.playlist if args.playlist else [],
        }

    try:
        youtube = get_authenticated_service()
        upload_video(youtube, video_config)
    except HttpError as e:
        print(f"❌ YouTube API error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


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
