# YouTube upload – credentials and setup

This project can upload videos to YouTube using the **YouTube Data API v3** and **OAuth 2.0**. You use your own Google/YouTube channel; the script only needs permission to upload and manage playlists.

**Python dependencies** (install once):
```bash
pip install google-auth google-auth-oauthlib google-api-python-client
```

## 1. Google Cloud project and YouTube API

1. Open **[Google Cloud Console](https://console.cloud.google.com/)** and sign in with the Google account that owns (or will own) your YouTube channel.

2. **Create a project** (or pick an existing one):
   - Top bar: click the project name → **New Project**.
   - Name it (e.g. “YouTube upload”) → **Create**.

3. **Enable the YouTube Data API v3**:
   - Left menu: **APIs & Services** → **Library**.
   - Search for **YouTube Data API v3** → open it → **Enable**.

## 2. OAuth consent screen

1. **APIs & Services** → **OAuth consent screen**.
2. Choose **External** (unless you use a Google Workspace org) → **Create**.
3. Fill:
   - **App name**: e.g. “My YouTube Uploader”
   - **User support email**: your email
   - **Developer contact**: your email
4. **Save and Continue**.
5. **Scopes**: **Add or Remove Scopes** → add:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube.force-ssl`
   → **Update** → **Save and Continue**.
6. **Test users** (if the app is in “Testing”): add the Gmail address of your YouTube channel.
7. **Save and Continue** through the summary.

## 3. Create OAuth client ID (desktop)

1. **APIs & Services** → **Credentials**.
2. **Create Credentials** → **OAuth client ID**.
3. **Application type**: **Desktop app**.
4. **Name**: e.g. “YouTube Upload Desktop”.
5. **Create**.
6. In the dialog, click **Download JSON** (or copy the client ID and secret if you prefer to paste them into a file yourself).

## 4. Save credentials in this project

1. Rename the downloaded file to **`client_secrets.json`** (or keep the name and ensure the script points to it).
2. Put **`client_secrets.json`** in the **repository root** (same folder as `src/`), e.g.:
   ```
   quran-recitation-movie-maker/
   ├── client_secrets.json   ← here
   ├── src/
   │   ├── upload-videos.py
   │   └── upload-youtube.sh
   └── ...
   ```
3. **Do not commit this file to git.** Add to `.gitignore`:
   ```
   client_secrets.json
   token.json
   ```

## 5. First run (browser login)

When you run the upload script for the first time:

1. A browser window opens.
2. Log in with the **Google account that owns the YouTube channel** you want to upload to.
3. If you see “Google hasn’t verified this app”: use **Advanced** → **Go to … (unsafe)** (it’s your own app).
4. Grant the requested permissions (upload to YouTube, manage your YouTube account).
5. The script saves a **`token.json`** in the repo root. Later runs will use this and only open the browser again when the token expires or is removed.

## 6. Upload from the command line

From the repo root:

```bash
# Minimal: file + title, private by default
bash src/upload-youtube.sh --file out/my-video.mp4 --title "سوره حمد - تلاوت"

# Full example: title, description, public, one playlist
bash src/upload-youtube.sh \
  --file out/my-video.mp4 \
  --title "سوره حمد - تلاوت" \
  --description "تلاوت سوره حمد با تصویر طبیعت" \
  --visibility public \
  --playlist "تلاوت قرآن"

# Short options
bash src/upload-youtube.sh -f out/video.mp4 -t "My title" -v public -p "My playlist"
```

Or call the Python script directly:

```bash
python3 src/upload-videos.py --file out/video.mp4 --title "Title" --description "Desc" --visibility public --playlist "Playlist name"
```

## 7. Using your channel

- Uploads go to the **YouTube channel of the Google account** you used when approving the OAuth consent (the one you logged in with in the browser).
- To use another channel, log out of that Google account, delete **`token.json`**, and run the script again; then log in with the other account when the browser opens.
- **Playlist**: if you pass `--playlist "Name"`, the script adds the video to a playlist with that title; if it doesn’t exist, it creates it (public by default).

## Troubleshooting

| Problem | What to do |
|--------|-------------|
| “Missing client_secrets.json” | Create and download OAuth client (Desktop) as above and put `client_secrets.json` in the repo root. |
| “Invalid grant” / token errors | Delete `token.json` and run again; log in again in the browser. |
| “Access blocked” / “App not verified” | In the consent screen, add your account as a test user; when opening the app, use “Advanced” → “Go to …”. |
| Upload fails with 403 | Ensure YouTube Data API v3 is enabled and the OAuth client has the upload and force-ssl scopes. |
