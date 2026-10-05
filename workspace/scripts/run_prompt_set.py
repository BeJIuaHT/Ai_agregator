#!/usr/bin/env python3
"""Generate key frames for a prompt set via ComfyUI API (tunnel on 127.0.0.1:8188).
Prompts are built from scene JSONs by assemble_prompt.build (positive AND per-scene negative), never retyped.
Set file: workspace/prompts/sets/<name>.json. Output: workspace/output/<name>/кадр_N.M.png (N = scene order, M = variant)
Usage: run_prompt_set.py <name> [--variants N] [--spare] [--frames 1,2] [--dry-run]
  --spare   also generate the spare variants (seeds continue after the regular ones)
  --dry-run print prompts, seeds, token estimates, and check the workflow; no network
"""
import argparse, copy, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble_prompt as ap  # noqa: E402

API = "http://127.0.0.1:8188"
WORKFLOW = ROOT / "workspace/workflows/anime_sdxl_t2i.json"

ap_ = argparse.ArgumentParser()
ap_.add_argument("name")
ap_.add_argument("--variants", type=int)
ap_.add_argument("--spare", action="store_true")
ap_.add_argument("--frames")
ap_.add_argument("--dry-run", action="store_true")
args = ap_.parse_args()

cfg = json.loads((ROOT / f"workspace/prompts/sets/{args.name}.json").read_text(encoding="utf-8"))
n_var = args.variants or cfg["variants"]
if args.spare:
    n_var += cfg.get("spare_variants", 0)
frames = [int(x) for x in args.frames.split(",")] if args.frames else list(range(1, len(cfg["scenes"]) + 1))
wf0 = json.loads(WORKFLOW.read_text())
assert wf0["2"]["inputs"]["text"] == "__POSITIVE_PROMPT__" and wf0["3"]["class_type"] == "CLIPTextEncode"

jobs = []  # (frame, variant, workflow)
for n in frames:
    scene_name = cfg["scenes"][n - 1]
    scene = json.loads((ROOT / f"workspace/prompts/scenes/{scene_name}.json").read_text(encoding="utf-8"))
    positive, negative, _ = ap.build(scene)
    tokens, warns = ap.lint(scene, positive)
    if args.dry_run:
        print(f"кадр {n} {scene_name}: ~{tokens} tokens, warnings: {warns or 'none'}\n  + {positive}\n  - {negative}")
    for m in range(1, n_var + 1):
        wf = copy.deepcopy(wf0)
        wf["2"]["inputs"]["text"] = positive
        wf["3"]["inputs"]["text"] = negative
        wf["5"]["inputs"]["seed"] = cfg["seed_base"] + m - 1
        wf["7"]["inputs"]["filename_prefix"] = f"{args.name}_{n}_{m}"
        jobs.append((n, m, wf))

if args.dry_run:
    print(f"\nDRY RUN OK: {len(jobs)} images, seeds {cfg['seed_base']}..{cfg['seed_base'] + n_var - 1}, "
          f"size {wf0['4']['inputs']['width']}x{wf0['4']['inputs']['height']}, out workspace/output/{args.name}/")
    sys.exit(0)


def call(path, data=None):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


queued = [(n, m, json.loads(call("/prompt", {"prompt": wf}))["prompt_id"]) for n, m, wf in jobs]
print(f"queued {len(queued)} jobs", flush=True)

out = ROOT / "workspace/output" / args.name
out.mkdir(parents=True, exist_ok=True)
t0 = time.time()
while queued:
    n, m, pid = queued[0]
    h = json.loads(call(f"/history/{pid}"))
    if pid not in h:
        time.sleep(2)
        continue
    rec = h[pid]
    if rec["status"]["status_str"] != "success":
        print(f"кадр_{n}.{m} FAILED: {rec['status']}", flush=True)
    else:
        img = next(iter(rec["outputs"].values()))["images"][0]
        q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
        (out / f"кадр_{n}.{m}.png").write_bytes(call("/view?" + q))
        print(f"кадр_{n}.{m}.png saved ({time.time() - t0:.0f}s)", flush=True)
    queued.pop(0)
