#!/usr/bin/env python3
"""Validate a ComfyUI API-format workflow JSON.

Usage: validate_workflow.py workflow_api.json [--object-info http://host:8188]
Checks structure offline; with --object-info also checks class_type exists on the server.
Exit code 0 = valid, 1 = problems found.
"""
import json
import sys
import urllib.request


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    wf = json.load(open(sys.argv[1]))
    errs = []

    if "nodes" in wf and "links" in wf:
        print("ERROR: this is the UI-graph format. In ComfyUI use 'Save (API Format)' "
              "(enable Dev mode options) to get the API format.")
        return 1
    if "prompt" in wf and isinstance(wf["prompt"], dict):
        wf = wf["prompt"]  # accept an already-wrapped payload

    for nid, node in wf.items():
        if not isinstance(node, dict) or "class_type" not in node:
            errs.append(f"node {nid}: missing class_type")
            continue
        if not isinstance(node.get("inputs"), dict):
            errs.append(f"node {nid} ({node['class_type']}): missing inputs object")
            continue
        for k, v in node["inputs"].items():
            # link = [source_node_id (str), output_index (int)]
            if isinstance(v, list):
                if len(v) != 2 or not isinstance(v[1], int):
                    errs.append(f"node {nid}.{k}: bad link {v}")
                elif str(v[0]) not in wf:
                    errs.append(f"node {nid}.{k}: links to missing node {v[0]}")

    outputs = [n for n in wf.values() if isinstance(n, dict) and n.get("class_type", "")
               .startswith(("SaveImage", "VHS_VideoCombine", "SaveAnimated", "SaveVideo", "PreviewImage"))]
    if not outputs:
        errs.append("no output node (SaveImage / VHS_VideoCombine / SaveVideo ...): nothing would execute")

    if "--object-info" in sys.argv:
        base = sys.argv[sys.argv.index("--object-info") + 1].rstrip("/")
        info = json.load(urllib.request.urlopen(f"{base}/object_info", timeout=30))
        for nid, node in wf.items():
            ct = node.get("class_type")
            if ct and ct not in info:
                errs.append(f"node {nid}: class_type '{ct}' not installed on server (missing custom node?)")

    for e in errs:
        print("ERROR:", e)
    print("VALID" if not errs else f"{len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
