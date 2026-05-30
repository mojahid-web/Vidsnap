from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp, requests, re

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
QUALITY = {"low": "best[height<=360]/best", "medium": "best[height<=720]/best", "high": "best[height<=1080]/best"}

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.slipfox.xyz",
    "https://yt.artemislena.eu",
    "https://invidious.privacyredirect.com"
]

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.in.projectsegfau.lt",
]

def extract_video_id(url: str):
    patterns = [
        r"youtube\.com\/watch\?v=([^&\n?#]+)",
        r"youtube\.com\/shorts\/([^&\n?#]+)",
        r"youtu\.be\/([^&\n?#]+)",
        r"youtube\.com\/embed\/([^&\n?#]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_youtube(url: str):
    return "youtube.com" in url or "youtu.be" in url

def opts(u, f):
    return {"quiet": True, "no_warnings": True, "http_headers": HEADERS, "socket_timeout": 20, "format": f}

@app.get("/")
def root():
    return {"status": "GrabSnap API running"}

@app.get("/test-invidious")
def test_invidious():
    results = []
    for instance in INVIDIOUS_INSTANCES:
        try:
            res = requests.get(
                f"{instance}/api/v1/videos/dQw4w9WgXcQ",
                timeout=8,
                headers=HEADERS
            )
            results.append({
                "instance": instance,
                "status": res.status_code,
                "working": res.status_code == 200
            })
        except Exception as e:
            results.append({
                "instance": instance,
                "status": "failed",
                "error": str(e)
            })
    return results

@app.get("/test-piped")
def test_piped():
    results = []
    for instance in PIPED_INSTANCES:
        try:
            res = requests.get(
                f"{instance}/streams/dQw4w9WgXcQ",
                timeout=8,
                headers=HEADERS
            )
            results.append({
                "instance": instance,
                "status": res.status_code,
                "working": res.status_code == 200
            })
        except Exception as e:
            results.append({
                "instance": instance,
                "status": "failed",
                "error": str(e)
            })
    return results

@app.get("/info")
def info(url: str = Query(...)):
    try:
        if is_youtube(url):
            video_id = extract_video_id(url)
            if not video_id:
                return JSONResponse(status_code=400, content={"error": "Invalid YouTube URL"})
            for instance in INVIDIOUS_INSTANCES:
                try:
                    res = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=8, headers=HEADERS)
                    if res.status_code == 200:
                        data = res.json()
                        return {
                            "title": data.get("title", "Video"),
                            "thumbnail": data.get("videoThumbnails", [{}])[0].get("url", ""),
                            "platform": "YouTube",
                            "duration": data.get("lengthSeconds", 0)
                        }
                except:
                    continue
            return JSONResponse(status_code=500, content={"error": "All instances failed"})

        o = {"quiet": True, "no_warnings": True, "http_headers": HEADERS, "socket_timeout": 20}
        with yt_dlp.YoutubeDL(o) as y:
            d = y.extract_info(url, download=False)
            return {
                "title": d.get("title", "Video"),
                "thumbnail": d.get("thumbnail", ""),
                "platform": d.get("extractor_key", "Unknown"),
                "duration": d.get("duration", 0)
            }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.get("/youtube/formats")
def youtube_formats(url: str = Query(...)):
    video_id = extract_video_id(url)
    if not video_id:
        return JSONResponse(status_code=400, content={"error": "Invalid YouTube URL"})

    for instance in INVIDIOUS_INSTANCES:
        try:
            res = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=8, headers=HEADERS)
            if res.status_code == 200:
                data = res.json()
                formats = []
                for f in data.get("formatStreams", []):
                    formats.append({
                        "quality": f.get("qualityLabel", ""),
                        "url": f.get("url", ""),
                        "type": "video"
                    })
                return {
                    "title": data.get("title", "Video"),
                    "thumbnail": data.get("videoThumbnails", [{}])[0].get("url", ""),
                    "formats": formats
                }
        except:
            continue

    return JSONResponse(status_code=500, content={"error": "All instances failed"})

@app.get("/download")
def download(url: str = Query(...), quality: str = "high", format: str = "video"):
    try:
        if is_youtube(url):
            video_id = extract_video_id(url)
            for instance in INVIDIOUS_INSTANCES:
                try:
                    res = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=8, headers=HEADERS)
                    if res.status_code == 200:
                        data = res.json()
                        formats = data.get("formatStreams", [])
                        if not formats:
                            continue
                        if quality == "low":
                            selected = formats[0]
                        elif quality == "medium":
                            selected = formats[len(formats) // 2]
                        else:
                            selected = formats[-1]
                        download_url = selected.get("url")
                        title = data.get("title", "video")
                        r = requests.get(download_url, stream=True, timeout=30, headers=HEADERS)
                        return StreamingResponse(
                            r.iter_content(chunk_size=1024 * 1024),
                            media_type="video/mp4",
                            headers={
                                "Content-Disposition": f'attachment; filename="{title}.mp4"',
                                "Access-Control-Allow-Origin": "*"
                            }
                        )
                except:
                    continue
            return JSONResponse(status_code=500, content={"error": "All instances failed"})

        if format == "audio":
            f, n, m = "bestaudio/best", "audio.mp3", "audio/mpeg"
        else:
            f, n, m = QUALITY.get(quality, QUALITY["high"]), f"video_{quality}.mp4", "video/mp4"

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

        h = {"User-Agent": HEADERS["User-Agent"], "Referer": url}
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
