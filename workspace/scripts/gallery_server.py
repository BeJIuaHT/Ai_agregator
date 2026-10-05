#!/usr/bin/env python3
"""Галерея для workspace/output: превью, сортировка по имени/времени, архивация.

Запуск:  python3 workspace/scripts/gallery_server.py [--port 9000] [--host 0.0.0.0]
Архивация переносит файл из output/<путь> в archive/<тот же путь> (структура папок сохраняется).
Доступ защищён токеном (печатается при старте; после первого входа ставится cookie).
Превью строятся через Pillow, если он установлен (кэш в archive/../.thumbs), иначе отдаются оригиналы.
"""
import argparse
import hashlib
import http.cookies
import json
import mimetypes
import secrets
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None

WORKSPACE = Path(__file__).resolve().parent.parent
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
THUMB_SIZE = 360
lock = threading.Lock()

PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Галерея</title>
<style>
:root{color-scheme:dark}
body{margin:0;font:14px system-ui,sans-serif;background:#16181c;color:#e6e6e6}
header{position:sticky;top:0;z-index:2;display:flex;gap:8px;flex-wrap:wrap;align-items:center;
  padding:10px 14px;background:#20232a;border-bottom:1px solid #333}
select,button{background:#2b2f38;color:inherit;border:1px solid #444;border-radius:6px;padding:6px 10px;font:inherit}
button{cursor:pointer} button:hover{background:#3a3f4b}
#count{margin-left:auto;opacity:.7}
main{padding:14px}
h2{margin:18px 0 8px;font-size:15px;opacity:.8;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
.card{background:#20232a;border-radius:8px;overflow:hidden;display:flex;flex-direction:column}
.card img{width:100%;aspect-ratio:1;object-fit:cover;background:#111;cursor:zoom-in}
.meta{padding:6px 8px;font-size:12px;word-break:break-all}
.meta small{display:block;opacity:.6;margin-top:2px}
.card button{margin:0 8px 8px}
#lb{position:fixed;inset:0;background:#000d;display:none;align-items:center;justify-content:center;z-index:5}
#lb img{max-width:96vw;max-height:96vh}
</style></head><body>
<header>
  <button id="tab-output">Картинки</button>
  <button id="tab-archive">Архив</button>
  <label>Сортировка
    <select id="sort"><option value="name">по имени</option><option value="time">по времени</option></select>
  </label>
  <select id="dir"><option value="asc">↑ по возрастанию</option><option value="desc">↓ по убыванию</option></select>
  <button id="reload">Обновить</button>
  <span id="count"></span>
</header>
<main id="main"></main>
<div id="lb"><img id="lbimg"></div>
<script>
const $=id=>document.getElementById(id);
const natural=new Intl.Collator(undefined,{numeric:true,sensitivity:'base'});
let files=[], area=localStorage.getItem('galArea')||'output';
const saved=JSON.parse(localStorage.getItem('gal')||'{}');
$('sort').value=saved.sort||'time'; $('dir').value=saved.dir||'desc';

function render(){
  localStorage.setItem('gal',JSON.stringify({sort:$('sort').value,dir:$('dir').value}));
  const k=$('sort').value, m=$('dir').value==='asc'?1:-1;
  const cmp=k==='name'?(a,b)=>natural.compare(a.name,b.name):(a,b)=>a.mtime-b.mtime;
  const groups={};
  for(const f of files){(groups[f.dir]??=[]).push(f)}
  const main=$('main'); main.textContent='';
  for(const d of Object.keys(groups).sort(natural.compare)){
    const h=document.createElement('h2'); h.textContent=d||'/'; main.append(h);
    const g=document.createElement('div'); g.className='grid'; main.append(g);
    for(const f of groups[d].sort((a,b)=>m*cmp(a,b))) g.append(card(f));
  }
  $('count').textContent=files.length+' файлов';
  $('tab-output').style.outline=area==='output'?'2px solid #6aa7ff':'';
  $('tab-archive').style.outline=area==='archive'?'2px solid #6aa7ff':'';
}
const q=f=>'p='+encodeURIComponent(f.path)+'&a='+area;
function card(f){
  const c=document.createElement('div'); c.className='card';
  const img=document.createElement('img'); img.loading='lazy';
  img.src='/thumb?'+q(f); img.onclick=()=>{$('lbimg').src='/file?'+q(f);$('lb').style.display='flex'};
  const meta=document.createElement('div'); meta.className='meta';
  meta.textContent=f.name;
  const s=document.createElement('small');
  s.textContent=new Date(f.mtime*1000).toLocaleString()+' · '+(f.size/1048576).toFixed(2)+' МБ'; meta.append(s);
  const b=document.createElement('button'); b.textContent=area==='output'?'Архивировать':'Восстановить';
  b.onclick=async()=>{
    b.disabled=true;
    const r=await fetch(area==='output'?'/api/archive':'/api/restore',{method:'POST',body:JSON.stringify({path:f.path})});
    if(r.ok){files=files.filter(x=>x.path!==f.path);render()} else {b.disabled=false;alert('Ошибка: '+await r.text())}
  };
  c.append(img,meta,b); return c;
}
async function load(){files=await (await fetch('/api/list?a='+area)).json();render()}
for(const a of ['output','archive'])
  $('tab-'+a).onclick=()=>{area=a;localStorage.setItem('galArea',a);load()};
$('sort').onchange=$('dir').onchange=render; $('reload').onclick=load;
$('lb').onclick=()=>{$('lb').style.display='none';$('lbimg').src=''};
load();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    output: Path
    archive: Path
    thumbs: Path
    token: str

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # ---- helpers
    def send_bytes(self, code, body, ctype="text/plain; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, query):
        cookie = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        got = cookie["gal_token"].value if "gal_token" in cookie else ""
        given = query.get("token", [got])[0]
        return secrets.compare_digest(given, self.token)

    def resolve(self, rel, base):
        """Относительный путь -> абсолютный внутри base, иначе None (защита от ../)."""
        p = (base / rel).resolve()
        return p if p.is_relative_to(base) else None

    def area(self, q):
        return self.archive if q.get("a", ["output"])[0] == "archive" else self.output

    def list_files(self, base):
        out = []
        if not base.is_dir():
            return out
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in IMG_EXT:
                st = p.stat()
                rel = p.relative_to(base)
                out.append({"path": rel.as_posix(), "name": p.name, "dir": "" if rel.parent == Path(".") else rel.parent.as_posix(),
                            "mtime": st.st_mtime, "size": st.st_size})
        return out

    def thumb_for(self, src):
        if Image is None:
            return src, None
        key = hashlib.sha1(f"{src}{src.stat().st_mtime_ns}".encode()).hexdigest()
        dst = self.thumbs / f"{key}.jpg"
        if not dst.exists():
            self.thumbs.mkdir(parents=True, exist_ok=True)
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((THUMB_SIZE, THUMB_SIZE))
                im.save(dst, "JPEG", quality=80)
        return dst, "image/jpeg"

    def send_file(self, path, ctype=None):
        ctype = ctype or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_bytes(200, path.read_bytes(), ctype, {"Cache-Control": "private, max-age=3600"})

    # ---- routes
    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if not self.authorized(q):
            return self.send_bytes(403, "Нужен токен: откройте /?token=...".encode())
        headers = {"Set-Cookie": f"gal_token={self.token}; HttpOnly; SameSite=Strict; Path=/"}
        if url.path == "/":
            return self.send_bytes(200, PAGE.encode(), "text/html; charset=utf-8", headers)
        if url.path == "/api/list":
            return self.send_bytes(200, json.dumps(self.list_files(self.area(q))).encode(), "application/json")
        if url.path in ("/file", "/thumb"):
            src = self.resolve(unquote(q.get("p", [""])[0]), self.area(q))
            if not src or not src.is_file() or src.suffix.lower() not in IMG_EXT:
                return self.send_bytes(404, b"not found")
            if url.path == "/file":
                return self.send_file(src)
            try:
                path, ctype = self.thumb_for(src)
            except Exception:  # битый файл -> оригинал
                path, ctype = src, None
            return self.send_file(path, ctype)
        self.send_bytes(404, b"not found")

    def do_POST(self):
        route = urlparse(self.path).path
        if route not in ("/api/archive", "/api/restore"):
            return self.send_bytes(404, b"not found")
        src_base, dst_base = (self.output, self.archive) if route == "/api/archive" else (self.archive, self.output)
        if not self.authorized({}):
            return self.send_bytes(403, b"forbidden")
        try:
            rel = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["path"]
        except (ValueError, KeyError, TypeError):
            return self.send_bytes(400, b"bad request")
        src = self.resolve(rel, src_base)
        if not src or not src.is_file() or src.suffix.lower() not in IMG_EXT:
            return self.send_bytes(404, b"not found")
        with lock:
            dst = dst_base / src.relative_to(src_base)
            dst.parent.mkdir(parents=True, exist_ok=True)
            n = 1
            while dst.exists():  # не затираем файл с тем же именем
                dst = dst.with_name(f"{src.stem}_{n}{src.suffix}")
                n += 1
            shutil.move(str(src), str(dst))
        self.log_message("%s %s -> %s", route.rsplit("/", 1)[1], rel, dst.relative_to(dst_base))
        self.send_bytes(200, b"ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--output", type=Path, default=WORKSPACE / "output")
    ap.add_argument("--archive", type=Path, default=WORKSPACE / "archive")
    ap.add_argument("--token", default=secrets.token_urlsafe(12))
    a = ap.parse_args()

    out, arc = a.output.resolve(), a.archive.resolve()
    if out == arc or out in arc.parents or arc in out.parents:
        sys.exit("archive не должен лежать внутри output и наоборот")
    Handler.output, Handler.archive, Handler.token = out, arc, a.token
    Handler.thumbs = arc.parent / ".thumbs"
    if Image is None:
        print("Pillow не найден: превью = оригиналы (pip install pillow для лёгких превью)")
    print(f"Открыть: http://<IP>:{a.port}/?token={a.token}")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
