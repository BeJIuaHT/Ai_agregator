#!/usr/bin/env python3
"""Галерея для workspace/output: картинки и видео, сортировка по имени/времени, архивация.

Запуск:  python3 workspace/scripts/gallery_server.py [--port 9000] [--host 0.0.0.0]
Архивация переносит файл из output/<путь> в archive/<тот же путь> (структура папок сохраняется).
Доступ открытый, без токена (любой, кто знает адрес и порт, может смотреть и архивировать).
Перезапуск после правок: workspace/scripts/restart_gallery.sh
Превью картинок строятся через Pillow, если он установлен (кэш в archive/../.thumbs), иначе отдаются оригиналы.
Видео (mp4/webm/mov) играют прямо в карточке (отдаются с поддержкой Range); промт читается из метаданных mp4.
"""
import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import struct
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
VIDEO_EXT = {".mp4", ".webm", ".mov"}
MEDIA_EXT = IMG_EXT | VIDEO_EXT
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
.card video{width:100%;aspect-ratio:1;object-fit:contain;background:#111}
.meta{padding:6px 8px;font-size:12px;word-break:break-all}
.meta small{display:block;opacity:.6;margin-top:2px}
.card button{margin:0 8px 8px}
.card pre{margin:0 8px 8px;padding:6px;background:#111;border-radius:6px;font-size:11px;
  white-space:pre-wrap;word-break:break-word;max-height:240px;overflow:auto;user-select:text}
#lb{position:fixed;inset:0;background:#000d;display:none;align-items:center;justify-content:center;z-index:5}
#lb img,#lb video{max-width:96vw;max-height:96vh}
</style></head><body>
<header>
  <button id="tab-output">Картинки</button>
  <button id="tab-archive">Архив</button>
  <label>Сортировка
    <select id="sort"><option value="name">по имени</option><option value="time">по времени</option></select>
  </label>
  <select id="dir"><option value="asc">↑ по возрастанию</option><option value="desc">↓ по убыванию</option></select>
  <select id="kind"><option value="all">всё</option><option value="image">картинки</option><option value="video">видео</option></select>
  <button id="reload">Обновить</button>
  <span id="count"></span>
</header>
<main id="main"></main>
<div id="lb"><img id="lbimg" hidden><video id="lbvid" controls loop hidden></video></div>
<script>
const $=id=>document.getElementById(id);
const natural=new Intl.Collator(undefined,{numeric:true,sensitivity:'base'});
let files=[], area=localStorage.getItem('galArea')||'output';
const saved=JSON.parse(localStorage.getItem('gal')||'{}');
$('sort').value=saved.sort||'time'; $('dir').value=saved.dir||'desc'; $('kind').value=saved.kind||'all';

function render(){
  localStorage.setItem('gal',JSON.stringify({sort:$('sort').value,dir:$('dir').value,kind:$('kind').value}));
  const k=$('sort').value, m=$('dir').value==='asc'?1:-1;
  const cmp=k==='name'?(a,b)=>natural.compare(a.name,b.name):(a,b)=>a.mtime-b.mtime;
  const groups={};
  const shown=files.filter(f=>$('kind').value==='all'||f.kind===$('kind').value);
  for(const f of shown){(groups[f.dir]??=[]).push(f)}
  const main=$('main'); main.textContent='';
  for(const d of Object.keys(groups).sort(natural.compare)){
    const h=document.createElement('h2'); h.textContent=d||'/'; main.append(h);
    const g=document.createElement('div'); g.className='grid'; main.append(g);
    for(const f of groups[d].sort((a,b)=>m*cmp(a,b))) g.append(card(f));
  }
  $('count').textContent=shown.length+' файлов';
  $('tab-output').style.outline=area==='output'?'2px solid #6aa7ff':'';
  $('tab-archive').style.outline=area==='archive'?'2px solid #6aa7ff':'';
}
function openLb(f){
  const v=f.kind==='video';
  $('lbimg').hidden=v; $('lbvid').hidden=!v;
  if(v){$('lbvid').src='/file?'+q(f);$('lbvid').play().catch(()=>{})} else $('lbimg').src='/file?'+q(f);
  $('lb').style.display='flex';
}
function closeLb(){$('lb').style.display='none';$('lbimg').src='';$('lbvid').pause();$('lbvid').removeAttribute('src');$('lbvid').load()}
const q=f=>'p='+encodeURIComponent(f.path)+'&a='+area;
function card(f){
  const c=document.createElement('div'); c.className='card';
  let media;
  if(f.kind==='video'){
    media=document.createElement('video'); media.src='/file?'+q(f)+'#t=0.1';
    media.controls=true; media.muted=true; media.loop=true; media.playsInline=true; media.preload='metadata';
  } else {
    media=document.createElement('img'); media.loading='lazy'; media.src='/thumb?'+q(f);
  }
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
  const pb=document.createElement('button'); pb.textContent='Промт';
  const pre=document.createElement('pre'); pre.hidden=true;
  pb.onclick=async()=>{
    if(!pre.hidden){pre.hidden=true;return}
    if(!pre.dataset.loaded){
      const r=await fetch('/api/prompt?'+q(f)); const p=await r.json();
      pre.textContent=!p?'Промт в файле не найден':
        'Positive:\\n'+p.positive+(p.negative?'\\n\\nNegative:\\n'+p.negative:'')+
        ['seed','noise_seed','steps','cfg'].filter(k=>k in p).map(k=>'\\n'+k+': '+p[k]).join('');
      pre.dataset.loaded=1;
    }
    pre.hidden=false;
  };
  const btns=[pb];
  const ob=document.createElement('button'); ob.textContent='Открыть';
  ob.onclick=()=>openLb(f); btns.push(ob);
  if(f.kind!=='video') media.onclick=()=>openLb(f);
  c.append(media,meta,...btns,pre,b); return c;
}
async function load(){files=await (await fetch('/api/list?a='+area)).json();render()}
for(const a of ['output','archive'])
  $('tab-'+a).onclick=()=>{area=a;localStorage.setItem('galArea',a);load()};
$('sort').onchange=$('dir').onchange=$('kind').onchange=render; $('reload').onclick=load;
$('lb').onclick=e=>{if(e.target!==$('lbvid'))closeLb()};
document.onkeydown=e=>{if(e.key==='Escape')closeLb()};
load();
</script></body></html>
"""


def png_graph(path):
    """Граф ComfyUI из PNG (tEXt 'prompt')."""
    data = path.read_bytes()
    graph, i = None, 8
    while i + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[i:i + 8])
        if kind == b"tEXt":
            key, _, val = data[i + 8:i + 8 + n].partition(b"\0")
            if key == b"prompt":
                graph = json.loads(val.decode("utf-8", "replace"))
                break
        if kind == b"IDAT":  # метаданные ComfyUI идут до данных изображения
            break
        i += 12 + n
    return graph


def mp4_graph(path):
    """Граф ComfyUI из mp4: moov/udta/meta -> keys + ilst (QuickTime-метаданные, ключ 'prompt')."""
    with path.open("rb") as f:
        pos, size = 0, path.stat().st_size
        while pos + 8 <= size:  # верхний уровень: ищем moov, не читая mdat
            f.seek(pos)
            n, kind = struct.unpack(">I4s", f.read(8))
            hdr = 8
            if n == 1:
                n, hdr = struct.unpack(">Q", f.read(8))[0], 16
            elif n == 0:
                n = size - pos
            if n < hdr:
                return None
            if kind == b"moov":
                moov = f.read(n - hdr)
                break
            pos += n
        else:
            return None
    keys_at = moov.find(b"keys")
    ilst_at = moov.find(b"ilst")
    if keys_at < 0 or ilst_at < 0:
        return None
    count = struct.unpack(">I", moov[keys_at + 8:keys_at + 12])[0]
    names, i = [], keys_at + 12
    for _ in range(count):  # keys: size, namespace(4), name
        n = struct.unpack(">I", moov[i:i + 4])[0]
        names.append(moov[i + 8:i + n].decode("utf-8", "replace"))
        i += n
    i = ilst_at + 4
    end = ilst_at - 4 + struct.unpack(">I", moov[ilst_at - 4:ilst_at])[0]
    while i + 16 <= end:  # item: size, key index(4), data atom: size, 'data', type(4), locale(4), payload
        n, idx = struct.unpack(">II", moov[i:i + 8])
        if 1 <= idx <= len(names) and names[idx - 1] == "prompt":
            return json.loads(moov[i + 24:i + n].decode("utf-8", "replace"))
        i += n
    return None


def read_prompt(path):
    """Достаёт промт из метаданных ComfyUI (PNG или mp4): positive/negative/seed."""
    ext = path.suffix.lower()
    graph = png_graph(path) if ext == ".png" else mp4_graph(path) if ext == ".mp4" else None
    if not isinstance(graph, dict):
        return None

    def text_of(ref):
        node = graph.get(ref[0]) if isinstance(ref, list) and ref else None
        t = node.get("inputs", {}).get("text") if node else None
        return t if isinstance(t, str) else None

    res = {}
    for node in graph.values():
        inp = node.get("inputs", {})
        if "positive" in inp and "negative" in inp:  # сэмплер
            res["positive"], res["negative"] = text_of(inp["positive"]), text_of(inp["negative"])
            for k in ("seed", "noise_seed", "steps", "cfg"):
                if isinstance(inp.get(k), (int, float)):
                    res[k] = inp[k]
            break
    if not res.get("positive"):  # нестандартный граф: все текстовые энкодеры
        texts = [n["inputs"]["text"] for n in graph.values()
                 if "CLIPTextEncode" in n.get("class_type", "") and isinstance(n["inputs"].get("text"), str)]
        res["positive"] = "\n---\n".join(texts) or None
    return res if res.get("positive") else None


class Handler(BaseHTTPRequestHandler):
    output: Path
    archive: Path
    thumbs: Path

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
            if p.is_file() and p.suffix.lower() in MEDIA_EXT:
                st = p.stat()
                rel = p.relative_to(base)
                out.append({"path": rel.as_posix(), "name": p.name, "dir": "" if rel.parent == Path(".") else rel.parent.as_posix(),
                            "mtime": st.st_mtime, "size": st.st_size,
                            "kind": "video" if p.suffix.lower() in VIDEO_EXT else "image"})
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
        """Отдаёт файл потоком с поддержкой Range (нужен <video>: Safari и перемотка)."""
        ctype = ctype or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        start, end, code = 0, size - 1, 200
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
        if m and (m[1] or m[2]):
            if m[1]:
                start, end = int(m[1]), min(int(m[2]), size - 1) if m[2] else size - 1
            else:  # суффикс: последние N байт
                start = max(size - int(m[2]), 0)
            if start >= size or start > end:
                return self.send_bytes(416, b"", extra={"Content-Range": f"bytes */{size}"})
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(max(end - start + 1, 0)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "private, max-age=3600")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with path.open("rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0 and (chunk := f.read(min(1 << 20, left))):
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):  # браузер оборвал загрузку видео
            pass

    # ---- routes
    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path == "/":
            return self.send_bytes(200, PAGE.encode(), "text/html; charset=utf-8")
        if url.path == "/api/list":
            return self.send_bytes(200, json.dumps(self.list_files(self.area(q))).encode(), "application/json")
        if url.path == "/api/prompt":
            src = self.resolve(unquote(q.get("p", [""])[0]), self.area(q))
            if not src or not src.is_file() or src.suffix.lower() not in MEDIA_EXT:
                return self.send_bytes(404, b"not found")
            try:
                info = read_prompt(src)
            except Exception:  # битые метаданные
                info = None
            return self.send_bytes(200, json.dumps(info).encode(), "application/json")
        if url.path in ("/file", "/thumb"):
            src = self.resolve(unquote(q.get("p", [""])[0]), self.area(q))
            if not src or not src.is_file() or src.suffix.lower() not in MEDIA_EXT:
                return self.send_bytes(404, b"not found")
            if url.path == "/file" or src.suffix.lower() in VIDEO_EXT:  # у видео превью нет
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
        try:
            rel = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["path"]
        except (ValueError, KeyError, TypeError):
            return self.send_bytes(400, b"bad request")
        src = self.resolve(rel, src_base)
        if not src or not src.is_file() or src.suffix.lower() not in MEDIA_EXT:
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
    a = ap.parse_args()

    out, arc = a.output.resolve(), a.archive.resolve()
    if out == arc or out in arc.parents or arc in out.parents:
        sys.exit("archive не должен лежать внутри output и наоборот")
    Handler.output, Handler.archive = out, arc
    Handler.thumbs = arc.parent / ".thumbs"
    if Image is None:
        print("Pillow не найден: превью = оригиналы (pip install pillow для лёгких превью)")
    print(f"Слушаю {a.host}:{a.port}, открыть: http://<IP>:{a.port}/")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
