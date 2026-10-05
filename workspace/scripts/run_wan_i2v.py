#!/usr/bin/env python3
"""Run Wan 2.2 I2V clips through ComfyUI (API format), sequentially, and download the mp4 files.

Variant A: workflows/wan22_i2v_a14b_lightx2v_rife.json (14B high+low fp8 + lightx2v 4-step LoRA)
Variant B: workflows/wan22_ti2v_5b_rife.json           (TI2V-5B fp16, KSampler)
Each run yields two mp4: <base>_16fps.mp4 (decoded frames) and <base>_32fps.mp4 (RIFE x2).

Prompts are parsed from workspace/prompts/built/wan_i2v_<scene>.txt (POSITIVE: / NEGATIVE: / START_FRAME:),
never retyped. The start frame is uploaded through /upload/image.

Examples:
  run_wan_i2v.py --check A                                  # node + model-name check only
  run_wan_i2v.py A --scenes s01 --seeds 101 --length 49 --name probe_A_s01_49f --timeout 480
  run_wan_i2v.py A                                          # 4 scenes x seeds 101 202 (8 clips)
  run_wan_i2v.py B                                          # 4 scenes x seed 101 (4 clips)

Stops on the first error (HTTP 400 node_errors, execution_error in /history, timeout).
On timeout it calls POST /interrupt (ComfyUI only; it never touches RunPod).
Exit codes: 0 ok, 1 error, 2 timeout.
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WF = {
    "A": os.path.join(ROOT, "workspace/workflows/wan22_i2v_a14b_lightx2v_rife.json"),
    "B": os.path.join(ROOT, "workspace/workflows/wan22_ti2v_5b_rife.json"),
}
# node ids of the saved workflows (read from the files, see validate step)
IDS = {
    "A": dict(image="9", pos="10", neg="11", size="12", seed=["13", "14"], steps=["13", "14"],
              base_cv="16", save16="17", rife="18", save32="20", cv32="19"),
    "B": dict(image="5", pos="6", neg="7", size="8", seed=["9"], steps=["9"],
              base_cv="11", save16="12", rife="13", save32="15", cv32="14"),
}
DEFAULT_SEEDS = {"A": [101, 202], "B": [101]}
SCENES = ["s01", "s02", "s03", "s04"]
PROMPTS = os.path.join(ROOT, "workspace/prompts/built/wan_i2v_{}.txt")
OUT_DEFAULT = os.path.join(ROOT, "workspace/output/wan_i2v_test")


def http(url, data=None, headers=None, timeout=60):
    r = urllib.request.Request(url, data=data, headers=headers or {})
    return urllib.request.urlopen(r, timeout=timeout)


def get_json(url):
    return json.load(http(url))


def post_json(url, body):
    return json.load(http(url, json.dumps(body).encode(), {"Content-Type": "application/json"}))


def parse_prompt(scene):
    """Return (positive, negative, start_frame_abs_path) parsed from the built prompt file."""
    txt = open(PROMPTS.format(scene), encoding="utf-8").read()
    parts, key = {}, None
    for line in txt.splitlines():
        s = line.strip()
        if s in ("POSITIVE:", "NEGATIVE:", "START_FRAME:"):
            key = s[:-1]
            parts[key] = []
        elif key:
            parts[key].append(line)
    pos = "\n".join(parts["POSITIVE"]).strip()
    neg = "\n".join(parts["NEGATIVE"]).strip()
    frame = "\n".join(parts["START_FRAME"]).strip()
    frame = frame if os.path.isabs(frame) else os.path.join(ROOT, frame)
    if not (pos and neg and os.path.isfile(frame)):
        raise SystemExit(f"bad prompt file for {scene}: pos={bool(pos)} neg={bool(neg)} frame={frame}")
    return pos, neg, frame


def upload(base, path, name):
    """multipart upload to /upload/image, returns the stored name."""
    b = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    body = b""
    for k, v in (("type", "input"), ("overwrite", "true")):
        body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += (f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
             f"Content-Type: {ctype}\r\n\r\n").encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    r = json.load(http(f"{base}/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={b}"}, 120))
    return r["name"]


def check(base, variant):
    """Verify class_types exist and every model filename is one of the /object_info choices."""
    wf = json.load(open(WF[variant], encoding="utf-8"))
    info = get_json(f"{base}/object_info")
    bad = 0
    for nid, node in wf.items():
        ct = node["class_type"]
        if ct not in info:
            print(f"MISSING node class {ct} (id {nid})")
            bad += 1
            continue
        spec = {**info[ct]["input"].get("required", {}), **info[ct]["input"].get("optional", {})}
        for k, v in node["inputs"].items():
            if isinstance(v, list) or k not in spec:
                continue
            choices = spec[k][0]
            if isinstance(choices, list) and v not in choices:
                if k == "image":  # LoadImage placeholder, replaced after upload
                    continue
                print(f"BAD value node {nid} {ct}.{k}={v!r}; choices: {choices}")
                bad += 1
    print(f"check {variant}: {'OK, all classes and model names match /object_info' if not bad else str(bad) + ' problem(s)'}")
    return bad == 0


def build(variant, pos, neg, image, seed, length, base_name, args):
    wf = json.load(open(WF[variant], encoding="utf-8"))
    ids = IDS[variant]
    wf[ids["image"]]["inputs"]["image"] = image
    wf[ids["pos"]]["inputs"]["text"] = pos
    wf[ids["neg"]]["inputs"]["text"] = neg
    sz = wf[ids["size"]]["inputs"]
    sz.update(width=args.width, height=args.height, length=length)
    for nid in ids["seed"]:
        wf[nid]["inputs"]["noise_seed" if variant == "A" else "seed"] = seed
    if variant == "B":
        if args.steps:
            wf["9"]["inputs"]["steps"] = args.steps
        if args.cfg is not None:
            wf["9"]["inputs"]["cfg"] = args.cfg
    wf[ids["base_cv"]]["inputs"]["fps"] = args.fps
    wf[ids["cv32"]]["inputs"]["fps"] = args.fps * 2
    wf[ids["rife"]]["inputs"]["ckpt_name"] = args.rife
    wf[ids["save16"]]["inputs"]["filename_prefix"] = f"wan_i2v/{base_name}_{args.fps}fps"
    wf[ids["save32"]]["inputs"]["filename_prefix"] = f"wan_i2v/{base_name}_{args.fps * 2}fps"
    return wf


def explain(body):
    print("  ERROR:", (body.get("error") or {}).get("message", body))
    for nid, ne in (body.get("node_errors") or {}).items():
        for e in ne.get("errors", []):
            print(f"  node {nid} [{ne.get('class_type')}]: {e.get('message')} - {e.get('details')}")


def run_one(base, wf, timeout):
    """Submit and poll. Returns (status, history_entry, wall_seconds). status: ok|error|timeout|rejected."""
    t0 = time.time()
    try:
        resp = post_json(f"{base}/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    except urllib.error.HTTPError as e:
        explain(json.loads(e.read() or b"{}"))
        return "rejected", None, 0.0
    pid = resp["prompt_id"]
    print(f"  prompt_id {pid}", flush=True)
    last = 0
    while time.time() - t0 < timeout:
        try:
            hist = get_json(f"{base}/history/{pid}")
        except Exception as e:  # tunnel hiccup: keep polling
            print("  poll error:", e)
            time.sleep(5)
            continue
        if pid in hist:
            h = hist[pid]
            if h.get("status", {}).get("status_str") == "error":
                for kind, d in h["status"].get("messages", []):
                    if kind == "execution_error":
                        print(f"  ERROR node {d.get('node_id')} [{d.get('node_type')}]: "
                              f"{d.get('exception_type')}: {d.get('exception_message')}")
                return "error", h, time.time() - t0
            return "ok", h, time.time() - t0
        if time.time() - last > 30:
            last = time.time()
            print(f"  ... {int(time.time() - t0)} s", flush=True)
        time.sleep(3)
    try:
        post_json(f"{base}/interrupt", {})
    except Exception:
        pass
    return "timeout", None, time.time() - t0


def server_seconds(h):
    """execution_start -> execution_success from /history messages (ms timestamps), or None."""
    ts = {k: d.get("timestamp") for k, d in h.get("status", {}).get("messages", []) if isinstance(d, dict)}
    if ts.get("execution_start") and ts.get("execution_success"):
        return (ts["execution_success"] - ts["execution_start"]) / 1000
    return None


def download(base, h, ids, base_name, fps, out):
    got = {}
    for nid, o in h.get("outputs", {}).items():
        for key in ("images", "videos", "gifs"):
            for f in o.get(key, []):
                if not f.get("filename", "").endswith((".mp4", ".webm", ".mkv")):
                    continue
                tag = {ids["save16"]: fps, ids["save32"]: fps * 2}.get(nid)
                if tag is None:
                    continue
                q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""),
                                            "type": f.get("type", "output")})
                dst = os.path.join(out, f"{base_name}_{tag}fps.mp4")
                with http(f"{base}/view?{q}", timeout=300) as r, open(dst, "wb") as fh:
                    fh.write(r.read())
                got[tag] = dst
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("variant", nargs="?", choices=["A", "B"])
    ap.add_argument("--check", choices=["A", "B"], help="only verify node classes and model names, then exit")
    ap.add_argument("--base", default="http://127.0.0.1:8188", help="ComfyUI base URL (SSH tunnel by default)")
    ap.add_argument("--scenes", nargs="+", default=SCENES, choices=SCENES)
    ap.add_argument("--seeds", nargs="+", type=int, help="default: A 101 202, B 101")
    ap.add_argument("--length", type=int, default=65, help="frames, must be 4n+1 (default 65 = 4.06 s at 16 fps)")
    ap.add_argument("--width", type=int, default=704)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=int, default=16, help="base fps; RIFE output is 2x")
    ap.add_argument("--rife", default="rife47.pth", help="RIFE VFI ckpt_name (rife47.pth, rife49.pth, rife417.pth, ...)")
    ap.add_argument("--steps", type=int, help="variant B only (template: 20)")
    ap.add_argument("--cfg", type=float, help="variant B only (template: 5)")
    ap.add_argument("--name", help="base file name override, e.g. probe_A_s01_49f (single clip only)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per clip before /interrupt")
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()
    base = args.base.rstrip("/")

    if args.check:
        return 0 if check(base, args.check) else 1
    if not args.variant:
        ap.error("variant A or B is required")
    if args.length % 4 != 1:
        ap.error("--length must be 4n+1 (49, 65, 81 ...)")
    seeds = args.seeds or DEFAULT_SEEDS[args.variant]
    jobs = [(s, sd) for s in args.scenes for sd in seeds]
    if args.name and len(jobs) != 1:
        ap.error("--name only with exactly one scene and one seed")
    if not check(base, args.variant):
        return 1
    os.makedirs(args.out, exist_ok=True)
    ids = IDS[args.variant]

    print(f"variant {args.variant}: {len(jobs)} clip(s), {args.width}x{args.height}, {args.length} frames, "
          f"{args.fps}->{args.fps * 2} fps, rife {args.rife}")
    results, t_all = [], time.time()
    for scene, seed in jobs:
        pos, neg, frame = parse_prompt(scene)
        stored = upload(base, frame, f"wan_{scene}_start.png")
        name = args.name or f"{args.variant}_{scene}_seed{seed}"
        print(f"[{name}] frame {os.path.basename(frame)} -> {stored}", flush=True)
        wf = build(args.variant, pos, neg, stored, seed, args.length, name, args)
        status, h, wall = run_one(base, wf, args.timeout)
        if status != "ok":
            print(f"STOP: {name} -> {status} after {wall:.0f} s (first error stops the batch)")
            return 2 if status == "timeout" else 1
        srv = server_seconds(h)
        files = download(base, h, ids, name, args.fps, args.out)
        print(f"  clip {name}: wall {wall:.0f} s" + (f", server execution {srv:.0f} s" if srv else "")
              + f", files: {', '.join(os.path.basename(p) + ' ' + str(os.path.getsize(p) // 1024) + ' KB' for p in files.values())}",
              flush=True)
        if len(files) != 2:
            print(f"STOP: expected 2 mp4 outputs, got {len(files)}: {json.dumps(h.get('outputs'))[:400]}")
            return 1
        results.append((name, wall))
    print(f"DONE {len(results)} clip(s) in {time.time() - t_all:.0f} s; per clip: "
          + ", ".join(f"{n} {w:.0f}s" for n, w in results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
