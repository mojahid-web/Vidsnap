from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp, requests, os, random

app = FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
TIKTOK_HEADERS={"User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 14_4_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1","Referer":"https://www.tiktok.com/"}
QUALITY={"low":"best[height<=360]/best","medium":"best[height<=720]/best","high":"best[height<=1080]/best"}
COOKIES="cookies.txt"
PUSER="yyolaowf"
PPASS="wd7dnrcwbeys"
PROXIES=["38.154.203.95:5863","198.105.121.200:6462","64.137.96.74:6641","209.127.138.10:5784","38.154.185.97:6370","84.247.60.125:6095","142.111.67.146:5611","191.96.254.138:6185","31.58.9.4:6077","64.137.10.153:5803"]
def proxy():return"http://{}:{}@{}".format(PUSER,PPASS,random.choice(PROXIES))
def isyt(u):return"youtube.com"in u or"youtu.be"in u
def istt(u):return"tiktok.com"in u
def opts(u,f):
    h=TIKTOK_HEADERS if istt(u) else HEADERS
    o={"quiet":True,"no_warnings":True,"http_headers":h,"socket_timeout":30,"format":f}
    if isyt(u):
        o["extractor_args"]={"youtube":{"player_client":["web"]}}
        o["proxy"]=proxy()
        if os.path.exists(COOKIES):o["cookiefile"]=COOKIES
    if istt(u):o["extractor_args"]={"tiktok":{"webpage_download":True}}
    return o
@app.get("/")
def root():return{"status":"GrabSnap API running"}
@app.get("/info")
def info(url:str=Query(...)):
    try:
        h=TIKTOK_HEADERS if istt(url) else HEADERS
        o={"quiet":True,"no_warnings":True,"http_headers":h,"socket_timeout":30}
        if isyt(url):
            o["extractor_args"]={"youtube":{"player_client":["web"]}}
            o["proxy"]=proxy()
            if os.path.exists(COOKIES):o["cookiefile"]=COOKIES
        if istt(url):o["extractor_args"]={"tiktok":{"webpage_download":True}}
        with yt_dlp.YoutubeDL(o) as y:
            d=y.extract_info(url,download=False)
            return{"title":d.get("title","Video"),"thumbnail":d.get("thumbnail",""),"platform":d.get("extractor_key","Unknown"),"duration":d.get("duration",0)}
    except Exception as e:
        msg=str(e)
        if istt(url) and("blocked"in msg.lower() or"unable to extract"in msg.lower()):msg="TikTok has blocked this server IP. Try Instagram or YouTube instead."
        return JSONResponse(status_code=400,content={"error":msg})
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
            if not du:return JSONResponse(status_code=400,content={"error":"No URL found"})
        h=TIKTOK_HEADERS if istt(url) else {"User-Agent":HEADERS["User-Agent"],"Referer":url}
        pr={"http":proxy(),"https":proxy()}if isyt(url) else None
        r=requests.get(du,stream=True,timeout=60,headers=h,proxies=pr)
        return StreamingResponse(r.iter_content(chunk_size=1024*1024),media_type=m,headers={"Content-Disposition":'attachment; filename="{}"'.format(n),"Access-Control-Allow-Origin":"*"})
    except Exception as e:
        msg=str(e)
        if istt(url) and("blocked"in msg.lower() or"unable to extract"in msg.lower()):msg="TikTok has blocked this server IP. Try Instagram or YouTube instead."
        return JSONResponse(status_code=400,content={"error":msg})
