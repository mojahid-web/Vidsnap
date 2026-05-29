from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

QUALITY_MAP = {
    "low":    "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "medium": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "high":   "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
}

@app.get("/")
def root():
    return {"status": "VidSnap API running", "version": "1.0"}

@app.get("/info")
def get_info(url: str = Query(...)):
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "http_headers": HEADERS,
            "socket_timeout": 15,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title":     info.get("title", "Video"),
                "thumbnail": info.get("thumbnail", ""),
                "platform":  info.get("extractor_key", "Unknown"),
                "duration":  info.get("duration", 0),
            }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.get("/download")
def download(
    url:     str = Query(...),
    quality: str = "high",
    format:  str = "video"
):
    try:
        if format == "audio":
            opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "http_headers": HEADERS,
            }
            fname     = "audio.mp3"
            mediatype = "audio/mpeg"
        else:
            opts = {
                "format": QUALITY_MAP.get(quality, QUALITY_MAP["high"]),
                "quiet": True,
                "no_warnings": True,
                "http_headers": HEADERS,
            }
            fname     = f"video_{quality}.mp4"
            mediatype = "video/mp4"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if "url" in info:
                direct_url = info["url"]
            elif "requested_formats" in info:
                direct_url = info["requested_formats"][0]["url"]
            else:
                fmts = info.get("formats", [])
                direct_url = fmts[-1]["url"] if fmts else None

            if not direct_url:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Could not extract download URL"}
                )

        r = requests.get(
            direct_url,
            stream=True,
            timeout=30,
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "Referer": url,
            }
        )

        return StreamingResponse(
            r.iter_content(chunk_size=1024 * 1024),
            media_type=mediatype,
            headers={
                "Content-Disposition": f'attachment; filename="{fname}"',
                "Access-Control-Allow-Origin": "*",
            }
        )

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
