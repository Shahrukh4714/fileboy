# Fileboy — Deployment Guide

This is a real, working file-conversion web app: a Flask backend (image/PDF/document/audio/video conversion) and a static HTML/JS frontend.

## What's included
- `backend/app.py` — Flask API with real conversion logic (Pillow, FFmpeg, LibreOffice, pypdf/pikepdf/img2pdf)
- `backend/requirements.txt` — Python dependencies
- `backend/Dockerfile` — containerizes the backend with FFmpeg + LibreOffice pre-installed
- `frontend/index.html` — the Fileboy UI, calls the backend via `fetch()`

## Why you need to deploy this yourself
I can run and test this backend live inside my own sandbox, but I can't keep a server running permanently for you after our conversation ends — that requires real hosting. The good news: this is a 10–15 minute task with a free tier on most platforms.

## Recommended hosting: Railway (easiest for Docker + FFmpeg + LibreOffice)

1. Create a free account at railway.app
2. Click **New Project → Deploy from GitHub repo** (push this `backend/` folder to a GitHub repo first), or use **Empty Project → Deploy from local directory** via the Railway CLI:
   ```
   npm i -g @railway/cli
   railway login
   cd backend
   railway init
   railway up
   ```
3. Railway will detect the `Dockerfile` and build it automatically (this installs FFmpeg + LibreOffice, which takes a few minutes on first deploy)
4. Once deployed, Railway gives you a public URL like `https://fileboy-backend-production.up.railway.app`
5. Set that as your backend's public address in Railway's settings (Generate Domain)

## Alternative hosts
- **Render.com** — similar process, has a free tier, supports Dockerfile deploys directly from a connected GitHub repo
- **Fly.io** — `fly launch` in the `backend/` folder, also Dockerfile-based
- Any VPS (DigitalOcean, Linode) — install Docker, `docker build` and `docker run` the image, put it behind Nginx + a domain

## Connecting the frontend to your deployed backend

Open `frontend/index.html` and change this one line near the top of the `<script>` block:

```javascript
const BACKEND_URL = 'http://localhost:5050'; // change to your deployed backend URL
```

to your real deployed URL, e.g.:

```javascript
const BACKEND_URL = 'https://fileboy-backend-production.up.railway.app';
```

Then host `frontend/index.html` anywhere static files are served: GitHub Pages, Netlify, Vercel, Cloudflare Pages — all have free tiers and take about 2 minutes (drag-and-drop the file on Netlify's dashboard is the fastest option).

## Testing locally before you deploy

If you have Python installed on your own machine:

```bash
cd backend
pip install -r requirements.txt
# You'll also need ffmpeg and libreoffice installed locally:
#   Mac: brew install ffmpeg libreoffice
#   Ubuntu: sudo apt install ffmpeg libreoffice poppler-utils
python3 app.py
```

Then open `frontend/index.html` directly in your browser (or serve it with `python3 -m http.server 8000` from the `frontend/` folder) — it will talk to your local backend at `localhost:5050`.

## What actually works right now (tested)
- Image ↔ image (JPEG, PNG, WEBP, GIF, BMP)
- Image → PDF
- Document (DOCX, PPTX, XLSX) → PDF, and PDF → those formats, via LibreOffice headless
- Audio format conversion (MP3, WAV, AAC, FLAC, OGG) via FFmpeg
- Video format conversion (MP4, MOV, WEBM) + video→GIF + video→MP3 (audio extraction) via FFmpeg

## Known limitations to plan for
- No auth / user accounts — anyone with the URL can use it
- No file size limits set yet — add one before going public, or large video files could crash the free-tier server (add `MAX_CONTENT_LENGTH` to Flask config)
- No rate limiting — vulnerable to abuse if the URL becomes public; consider adding basic rate limiting (Flask-Limiter) before a real launch
- Files are stored in `/tmp` and not automatically cleaned up on a schedule — for long-running deployments, add a cron job or startup cleanup to clear old files
- The frontend batch UI processes files sequentially (one at a time), not in parallel — fine for a few files, slow for dozens
