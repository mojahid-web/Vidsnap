from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp, requests

app = FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
QUALITY={"low":"best[height<=360]/best","medium":"best[height<=720]/best","high":"best[height<=1080]/best"}
def isyt(u):return"youtube.com"in u or"youtu.be"in u
def opts(u,f):
    o={"quiet":True,"no_warnings":True,"http_headers":HEADERS,"socket_timeout":20,"format":f}
    if isyt(u):o["extractor_args"]={"youtube":{"player_client":["android"]}}
    return o
@app.get("/")
def root():return{"status":"GrabSnap API running"}
@app.get("/info")
def info(url:str=Query(...)):
    try:
        o={"quiet":True,"no_warnings":True,"http_headers":HEADERS,"socket_timeout":20}
        if isyt(url):o["extractor_args"]={"youtube":{"player_client":["android"]}}
        with yt_dlp.YoutubeDL(o) as y:
            d=y.extract_info(url,download=False)
            return{"title":d.get("title","Video"),"thumbnail":d.get("thumbnail",""),"platform":d.get("extractor_key","Unknown"),"duration":d.get("duration",0)}
    except Exception as e:return JSONResponse(status_code=400,content={"error":str(e)})
@app.get("/download")
def download(url:str=Query(...),quality:str="high",format:str="video"):
    try:
        if format=="audio":f,n,m="bestaudio/best","audio.mp3","audio/mpeg"
        else:f,n,m=QUALITY.get(quality,QUALITY["high"]),"video_{}.mp4".format(quality),"video/mp4"
        with yt_dlp.YoutubeDL(opts(url,f)) as y:
            d=y.extract_info(url,download=False)
            if"url"in d:du=d["url"]
            elif"requested_formats"in d:du=d["requested_formats"][0]["url"]
            else:
                fl=d.get("formats",[])
                du=fl[-1]["url"]if fl else None
            if not du:return JSONResponse(status_code=400,content={"error":"No URL"})
        r=requests.get(du,stream=True,timeout=30,headers={"User-Agent":HEADERS["User-Agent"],"Referer":url})
        return StreamingResponse(r.iter_content(chunk_size=1024*1024),media_type=m,headers={"Content-Disposition":'attachment; filename="{}"'.format(n),"Access-Control-Allow-Origin":"*"})
    except Exception as e:return JSONResponse(status_code=400,content={"error":str(e)})
