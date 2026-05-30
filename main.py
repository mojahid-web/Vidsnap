from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp, requests, re

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

QUALITY = {
    "low": "best[height<=360]/best",
    "medium": "best[height<=720]/best",
    "high": "best[height<=1080]/best"
}

PIPED_INSTANCES = [
    "https://pipedapi.in.projectsegfau.lt",
    "https://pipedapi.kavin.rocks",
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


def fetch_piped(video_id: str):
    for instance in PIPED_INSTANCES:
        try:
            res = requests.get(
                f"{instance}/streams/{video_id}",
                timeout=8,
                headers=HEADERS
            )
            if res.status_code == 200:
                return res.json()
        except:
            continue
    return None


def opts(u, f):
    return {
        "quiet": True,
        "no_warnings": True,
        "http_headers": HEADERS,
        "socket_timeout": 20,
        "format": f
    }


@app.get("/")
def root():
    return {"status": "GrabSnap API running"}


@app.get("/info")
def info(url: str = Query(...)):
    try:
        if is_youtube(url):
            video_id = extract_video_id(url)
            if not video_id:
                return JSONResponse(status_code=400, content={"error": "Invalid YouTube URL"})

            data = fetch_piped(video_id)
            if not data:
                return JSONResponse(status_code=500, content={"error": "Could not fetch video info"})

            return {
                "title": data.get("title", "Video"),
                "thumbnail": data.get("thumbnailUrl", ""),
                "platform": "YouTube",
                "duration": data.get("duration", 0)
            }

        o = {
            "quiet": True,
            "no_warnings": True,
            "http_headers": HEADERS,
            "socket_timeout": 20
        }
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

    data = fetch_piped(video_id)
    if not data:
        return JSONResponse(status_code=500, content={"error": "All instances failed"})

    formats = []
    for stream in data.get("videoStreams", []):
        if "video/mp4" in stream.get("mimeType", ""):
            formats.append({
                "quality": stream.get("quality", ""),
                "url": stream.get("url", ""),
                "type": "video"
            })

    return {
        "title": data.get("title", "Video"),
        "thumbnail": data.get("thumbnailUrl", ""),
        "formats": formats
    }


@app.get("/download")
def download(url: str = Query(...), quality: str = "high", format: str = "video"):
    try:
        if is_youtube(url):
            video_id = extract_video_id(url)
            if not video_id:
                return JSONResponse(status_code=400, content={"error": "Invalid YouTube URL"})

            data = fetch_piped(video_id)
            if not data:
                return JSONResponse(status_code=500, content={"error": "All instances failed"})

            streams = [
                s for s in data.get("videoStreams", [])
                if "video/mp4" in s.get("mimeType", "")
            ]

            if not streams:
                return JSONResponse(status_code=400, content={"error": "No MP4 formats found"})

            if quality == "low":
                selected = streams[0]
            elif quality == "medium":
                selected = streams[len(streams) // 2]
            else:
                selected = streams[-1]

            download_url = selected.get("url")
            title = data.get("title", "video")

            r = requests.get(
                download_url,
                stream=True,
                timeout=30,
                headers=HEADERS
            )

            return StreamingResponse(
                r.iter_content(chunk_size=1024 * 1024),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f'attachment; filename="{title}.mp4"',
                    "Access-Control-Allow-Origin": "*"
                }
            )

        if format == "audio":
            f, n, m = "bestaudio/best", "audio.mp3", "audio/mpeg"
        else:
            f = QUALITY.get(quality, QUALITY["high"])
            n = f"video_{quality}.mp4"
            m = "video/mp4"

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
