from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp, requests, time, threading

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

INSTAGRAM_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Referer": "https://www.instagram.com/"
}

QUALITY = {
    "low": "best[height<=360]/best",
    "medium": "best[height<=720]/best",
    "high": "best[height<=1080]/best"
}

# Platforms backend handles reliably (no datacenter block)
ALLOWED = ["instagram.com", "facebook.com", "fb.watch", "twitter.com",
           "x.com", "vimeo.com", "twitch.tv", "dailymotion.com"]

# Platforms that must redirect (blocked on datacenter IP)
BLOCKED = ["youtube.com", "youtu.be", "reddit.com", "redd.it", "tiktok.com"]

# Cache
video_cache = {}
CACHE_DURATION = 3600

def get_cached(key):
    if key in video_cache:
        data, ts = video_cache[key]
        if time.time() - ts < CACHE_DURATION:
            return data
    return None

def set_cache(key, data):
    video_cache[key] = (data, time.time())

def is_allowed(url):
    return any(p in url for p in ALLOWED)

def is_blocked(url):
    return any(p in url for p in BLOCKED)

def get_headers(url):
    if "instagram.com" in url:
        return INSTAGRAM_HEADERS
    return HEADERS

def base_opts(url):
    return {
        "quiet": True,
        "no_warnings": True,
        "http_headers": get_headers(url),
        "socket_timeout": 10,
        "extractor_retries": 1,
        "file_access_retries": 1,
        "fragment_retries": 1,
        "noplaylist": True,
    }

# yt-dlp pre-warm on startup
@app.on_event("startup")
async def startup_event():
    def warm():
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                   "socket_timeout": 5, "extractor_retries": 0}) as y:
                y.extract_info("https://www.instagram.com/p/test/", download=False)
        except:
            pass
    threading.Thread(target=warm, daemon=True).start()

@app.get("/")
def root():
    return {"status": "GrabSnap API running"}

@app.get("/info")
def info(url: str = Query(...)):
    try:
        if is_blocked(url):
            return JSONResponse(status_code=400, content={
                "error": "redirect", "message": "This platform opens via a secure source"
            })
        if not is_allowed(url):
            return JSONResponse(status_code=400, content={
                "error": "Unsupported platform"
            })

        cached = get_cached(f"info:{url}")
        if cached:
            return cached

        o = base_opts(url)
        o["format"] = "best[ext=mp4]/best"

        with yt_dlp.YoutubeDL(o) as y:
            d = y.extract_info(url, download=False)

            du = None
            if "url" in d:
                du = d["url"]
            elif "requested_formats" in d:
                du = d["requested_formats"][0]["url"]
            elif d.get("formats"):
                du = d["formats"][-1]["url"]
            if du:
                set_cache(f"dl:{url}:high:video", du)

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
        if is_blocked(url):
            return JSONResponse(status_code=400, content={"error": "redirect"})
        if not is_allowed(url):
            return JSONResponse(status_code=400, content={"error": "Unsupported platform"})

        if format == "audio":
            f, n, m = "bestaudio/best", "audio.mp3", "audio/mpeg"
        else:
            f = QUALITY.get(quality, QUALITY["high"])
            n = f"video_{quality}.mp4"
            m = "video/mp4"

        cache_key = f"dl:{url}:{quality}:{format}"
        cached_url = get_cached(cache_key)

        if cached_url:
            du = cached_url
        else:
            o = base_opts(url)
            o["format"] = f
            with yt_dlp.YoutubeDL(o) as y:
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
                                   
