#!/usr/bin/env bash
# Run ON the pod. Parallel model download with aria2c into the Network Volume.
# Usage: bash download_models.sh models.manifest
# Manifest line format (tab or spaces separated, '#' = comment):
#   <subdir under ComfyUI/models>  <filename>  <url>
# e.g.  checkpoints  model.safetensors  https://huggingface.co/.../resolve/main/model.safetensors
# Gated HF repos need: export HF_TOKEN=hf_xxx   (never commit it)
set -euo pipefail

MANIFEST="${1:?manifest file}"
MODELS="${MODELS_DIR:-/workspace/ComfyUI/models}"
HDR=()
[ -n "${HF_TOKEN:-}" ] && HDR=(--header="Authorization: Bearer $HF_TOKEN")

grep -vE '^\s*(#|$)' "$MANIFEST" | while read -r sub name url; do
  mkdir -p "$MODELS/$sub"
  if [ -s "$MODELS/$sub/$name" ] && [ ! -e "$MODELS/$sub/$name.aria2" ]; then
    echo "skip (exists): $sub/$name"; continue
  fi
  echo "$url|$MODELS/$sub|$name"
done | while IFS='|' read -r url dir name; do
  # -c resume, -x/-s 16 connections per file; up to 3 files at once
  printf '%s\n out=%s\n dir=%s\n' "$url" "$name" "$dir"
done > /tmp/aria2.input

[ -s /tmp/aria2.input ] || { echo "nothing to download"; exit 0; }
aria2c -c -x16 -s16 -k1M -j3 --file-allocation=none --console-log-level=warn \
  --summary-interval=30 "${HDR[@]}" -i /tmp/aria2.input
echo "Downloads done. Verify sizes:"; du -ah "$MODELS" | sort -h | tail -15
