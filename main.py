from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp, requests, re, time

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

TIKTOK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://www.tiktok.com/"
}

QUALITY = {
    "low": "best[height<=360]/best",
    "medium": "best[height<=720]/best",
    "high": "best[height<=1080]/best"
}

# Cache system
video_cache = {}
CACHE_DURATION = 3600  # 1 hour

def get_cached(key):
    if key in video_cache:
        data, timestamp = video_cache[key]
        if time.time() - timestamp < CACHE_DURATION:
            return data
    return None

def set_cache(key, data):
    video_cache[key] = (data, time.time())

def is_instagram(u):
    return "instagram.com" in u

def is_facebook(u):
    return "facebook.com" in u or "fb.watch" in u

def get_headers(url):
    return TIKTOK_HEADERS if "tiktok.com" in url else HEADERS

def opts(url, f):
    return {
        "quiet": True,
        "no_warnings": True,
        "http_headers": get_headers(url),
        "socket_timeout": 10,
        "format": f,
        "extractor_retries": 1,
        "file_access_retries": 1,
        "fragment_retries": 1,
    }

@app.get("/")
def root():
    return {"status": "GrabSnap API running"}

@app.get("/info")
def info(url: str = Query(...)):
    try:
        cached = get_cached(f"info:{url}")
        if cached:
            return cached

        o = {
            "quiet": True,
            "no_warnings": True,
            "http_headers": get_headers(url),
            "socket_timeout": 10,
            "extractor_retries": 1,
            "file_access_retries": 1,
            "fragment_retries": 1,
        }

        with yt_dlp.YoutubeDL(o) as y:
            d = y.extract_info(url, download=False)
            result = {
                "title": d.get("title", "Video"),
                "thumbnail": d.get("thumbnail", ""),
                "platform": d.get("extractor_key", "Unknown"),
                "duration": d.get("duration", 0)
            }
            set_cache(f"info:{url}", result)
            return result

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.get("/download")
def download(url: str = Query(...), quality: str = "high", format: str = "video"):
    try:
        if format == "audio":
            f, n, m = "bestaudio/best", "audio.mp3", "audio/mpeg"
        else:
            f = QUALITY.get(quality, QUALITY["high"])
            n = f"video_{quality}.mp4"
            m = "video/mp4"

        # Cache check for download URL
        cache_key = f"dl:{url}:{quality}:{format}"
        cached_url = get_cached(cache_key)

        if cached_url:
            du = cached_url
        else:
            with yt_dlp.YoutubeDL(opts(url, f)) as y:
                d = y.extract_info(url, download=False)
                if "url" in d:
                    du = d["url"]
                elif "requested_formats" in d:
                    du = d["requested_formats"][0]["url"]
                else:
                    fl = d.get("formats", [])
                    du = fl[-1]["url"] if fl else None

                if not du:
                    return JSONResponse(status_code=400, content={"error": "No URL found"})

                set_cache(cache_key, du)

        h = {"User-Agent": get_headers(url)["User-Agent"], "Referer": url}
        r = requests.get(du, stream=True, timeout=30, headers=h)

        return StreamingResponse(
            r.iter_content(chunk_size=1024 * 1024),
            media_type=m,
            headers={
                "Content-Disposition": f'attachment; filename="{n}"',
                "Access-Control-Allow-Origin": "*"
            }
        )

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
