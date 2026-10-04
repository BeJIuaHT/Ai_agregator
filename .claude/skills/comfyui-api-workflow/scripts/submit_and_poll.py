#!/usr/bin/env python3
"""Submit an API-format workflow to ComfyUI, poll /history/{id}, download outputs.

Usage: submit_and_poll.py <base_url> <workflow_api.json> [--out DIR] [--timeout SEC]
  base_url e.g. http://localhost:8188 or https://<podId>-8188.proxy.runpod.net
Exit codes: 0 ok, 1 execution error, 2 timeout, 3 submit rejected (validation).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def req(url, data=None):
    r = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                               headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(r, timeout=60)


def explain_node_errors(body: dict):
    print("ERROR:", body.get("error", {}).get("message", body))
    for nid, ne in (body.get("node_errors") or {}).items():
        for e in ne.get("errors", []):
            print(f"  node {nid} [{ne.get('class_type')}]: {e.get('message')} - {e.get('details')}")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 3
    base, wf_path = sys.argv[1].rstrip("/"), sys.argv[2]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "workspace/output"
    timeout = int(sys.argv[sys.argv.index("--timeout") + 1]) if "--timeout" in sys.argv else 1800
    os.makedirs(out, exist_ok=True)

    wf = json.load(open(wf_path))
    try:
        resp = json.load(req(f"{base}/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())}))
    except urllib.error.HTTPError as e:  # 400 = validation failure with node_errors
        explain_node_errors(json.loads(e.read() or b"{}"))
        return 3
    pid = resp["prompt_id"]
    print("prompt_id:", pid)

    t0 = time.time()
    while time.time() - t0 < timeout:
        hist = json.load(req(f"{base}/history/{pid}"))
        if pid in hist:
            h = hist[pid]
            st = h.get("status", {})
            if st.get("status_str") == "error":
                for kind, d in st.get("messages", []):
                    if kind == "execution_error":
                        print(f"ERROR in node {d.get('node_id')} [{d.get('node_type')}]: "
                              f"{d.get('exception_type')}: {d.get('exception_message')}")
                return 1
            files = []
            for nid, o in h.get("outputs", {}).items():
                for key in ("gifs", "videos", "images"):  # VHS_VideoCombine -> 'gifs'
                    for f in o.get(key, []):
                        q = urllib.parse.urlencode({"filename": f["filename"],
                                                    "subfolder": f.get("subfolder", ""),
                                                    "type": f.get("type", "output")})
                        dst = os.path.join(out, f["filename"])
                        with req(f"{base}/view?{q}") as r, open(dst, "wb") as fh:
                            fh.write(r.read())
                        files.append(dst)
            print("DONE:", json.dumps(files))
            return 0 if files else 1
        time.sleep(5)
    print("TIMEOUT after", timeout, "s; prompt may still run. Check /queue.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
