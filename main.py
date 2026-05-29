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
    "low": "best[height<=360]/best",
    "medium": "best[height<=720]/best",
    "high": "best[height<=1080]/best",
}


def is_youtube(url):
    return "youtube.com" in url or "youtu.be" in url


def build_opts(url, fmt):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "http_headers": HEADERS,
        "socket_timeout": 20,
        "format": fmt,
    }
    if is_youtube(url):
        opts["extractor_args"] = {
            "youtube": {
                "player_client": ["android"],
            }
        }
    return opts


@app.get("/")
def root():
    return {"status": "GrabSnap API running", "version": "2.0"}


@app.get("/info")
def get_info(url: str = Query(...)):
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "http_headers": HEADERS,
            "socket_timeout": 20,
        }
        if is_youtube(url):
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android"],
                }
            }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title", "Video"),
                "thumbnail": info.get("thumbnail", ""),
                "platform": info.get("extractor_key", "Unknown"),
                "duration": info.get("duration", 0),
            }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.get("/download")
def download(url: str = Query(...), quality: str = "high", format: str = "video"):
    try:
        if format == "audio":
            fmt = "bestaudio/best"
            fname = "audio.mp3"
            mediatype = "audio/mpeg"
        else:
            fmt = QUALITY_MAP.get(quality, QUALITY_MAP["high"])
            fname = "video_{}.mp4".format(quality)
            mediatype = "video/mp4"

        opts = build_opts(url, fmt)

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
                return JSONResponse(status_code=400, content={"error": "Could not extract URL"})

        r = requests.get(
            direct_url,
            stream=True,
            timeout=30,
            headers={"User-Agent": HEADERS["User-Agent"], "Referer": url},
        )

        return StreamingResponse(
            r.iter_content(chunk_size=1024 * 1024),
            media_type=mediatype,
            headers={
                "Content-Disposition": 'attachment; filename="{}"'.format(fname),
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
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
                "Access-Control-Allow-Origin": "*",
            }
        )

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
