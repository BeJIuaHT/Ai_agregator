#!/usr/bin/env python3
"""Generate storyboard key frames via ComfyUI API (tunnel on 127.0.0.1:8188).
Prompts/negative are parsed from workspace/storyboard.md. Output: workspace/output/storyboard/кадр_N.M.png
Usage: run_storyboard.py [variants=8] [frames=1,2,3,4,5]
"""
import copy, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:8188"
OUT = ROOT / "workspace/output/storyboard"
variants = int(sys.argv[1]) if len(sys.argv) > 1 else 8
frames = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1, 2, 3, 4, 5]

md = (ROOT / "workspace/storyboard.md").read_text(encoding="utf-8")
negative = re.search(r"## Негатив\n`([^`]+)`", md).group(1)
prompts = {int(n): p for n, p in re.findall(r"\*\*(\d)\. [^\n]*\*\*\n`([^`]+)`", md)}
wf0 = json.loads((ROOT / "workspace/workflows/anime_sdxl_t2i.json").read_text())


def call(path, data=None):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


jobs = []
for n in frames:
    for m in range(1, variants + 1):
        wf = copy.deepcopy(wf0)
        wf["2"]["inputs"]["text"] = prompts[n]
        wf["3"]["inputs"]["text"] = negative
        wf["5"]["inputs"]["seed"] = n * 1000 + m
        wf["7"]["inputs"]["filename_prefix"] = f"sb_{n}_{m}"
        pid = json.loads(call("/prompt", {"prompt": wf}))["prompt_id"]
        jobs.append((n, m, pid))
print(f"queued {len(jobs)} jobs", flush=True)

OUT.mkdir(parents=True, exist_ok=True)
pending = list(jobs)
t0 = time.time()
while pending:
    n, m, pid = pending[0]
    h = json.loads(call(f"/history/{pid}"))
    if pid not in h:
        time.sleep(2)
        continue
    rec = h[pid]
    if rec["status"]["status_str"] != "success":
        print(f"кадр_{n}.{m} FAILED: {rec['status']}", flush=True)
        pending.pop(0)
        continue
    img = next(iter(rec["outputs"].values()))["images"][0]
    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
    (OUT / f"кадр_{n}.{m}.png").write_bytes(call("/view?" + q))
    print(f"кадр_{n}.{m}.png saved ({time.time()-t0:.0f}s)", flush=True)
    pending.pop(0)
