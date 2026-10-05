#!/usr/bin/env bash
# Run ON the pod. Parallel model download into ComfyUI/models with plain curl (aria2c is not in the image).
# Usage: bash download_models.sh models.manifest
# Manifest line format (tab or spaces separated, '#' = comment):
#   <subdir under ComfyUI/models>  <filename>  <url>
# e.g.  checkpoints  model.safetensors  https://huggingface.co/.../resolve/main/model.safetensors
# Gated HF repos need: export HF_TOKEN=hf_xxx   (never commit it)
# Method: STREAMS parallel `curl -r` ranges piped to `dd conv=notrunc oflag=seek_bytes` into ONE pre-truncated
# <file>.part, renamed when every range succeeded. No segment files, no double disk use. Files are fetched one
# after another; an interrupted download is restarted from zero (the .part is removed).
# Env: MODELS_DIR (default /workspace/ComfyUI/models), STREAMS (8), MIN_PARALLEL_BYTES (8 MiB: smaller = 1 stream)
set -euo pipefail

MANIFEST="${1:?manifest file}"
MODELS="${MODELS_DIR:-/workspace/ComfyUI/models}"
STREAMS="${STREAMS:-8}"
MIN_PAR="${MIN_PARALLEL_BYTES:-8388608}"
HDR=()
[ -n "${HF_TOKEN:-}" ] && HDR=(-H "Authorization: Bearer $HF_TOKEN")

size_of() {  # final Content-Length after redirects
  curl -sIL ${HDR[@]+"${HDR[@]}"} "$1" | tr -d '\r' | awk 'tolower($1)=="content-length:"{l=$2} END{print l+0}'
}

chunk_dl() {  # url part start end  (3 attempts; a retry rewrites the same byte range)
  local url="$1" part="$2" s="$3" e="$4" try
  for try in 1 2 3; do
    if curl -sSL --fail ${HDR[@]+"${HDR[@]}"} -r "$s-$e" "$url" \
       | dd of="$part" bs=1M conv=notrunc oflag=seek_bytes seek="$s" status=none; then
      return 0
    fi
    echo "range $s-$e failed (attempt $try)" >&2
  done
  return 1
}

fetch() {  # url dest
  local url="$1" dest="$2" size n=1 chunk i s e p ok=1 pids=()
  [ "$(curl -sIL -o /dev/null ${HDR[@]+"${HDR[@]}"} -w '%{http_code}' "$url")" = 200 ] \
    || { echo "ERROR: $url did not answer HTTP 200" >&2; return 1; }
  size="$(size_of "$url")"
  [ "$size" -gt 0 ] || { echo "ERROR: cannot read size of $url" >&2; return 1; }
  if [ "$size" -ge "$MIN_PAR" ] \
     && [ "$(curl -sL -o /dev/null ${HDR[@]+"${HDR[@]}"} -r 0-0 -w '%{http_code}' "$url")" = 206 ]; then
    n="$STREAMS"  # server honours Range
  fi
  chunk=$(( (size + n - 1) / n ))
  rm -f "$dest.part"
  truncate -s "$size" "$dest.part"
  for ((i = 0; i < n; i++)); do
    s=$((i * chunk)); e=$((s + chunk - 1))
    [ "$e" -ge "$size" ] && e=$((size - 1))
    [ "$s" -le "$e" ] || break
    chunk_dl "$url" "$dest.part" "$s" "$e" &
    pids+=("$!")
  done
  for p in "${pids[@]}"; do wait "$p" || ok=0; done
  if [ "$ok" != 1 ]; then rm -f "$dest.part"; echo "ERROR: download failed: $url" >&2; return 1; fi
  mv "$dest.part" "$dest"
}

todo=0
while read -r sub name url; do
  mkdir -p "$MODELS/$sub"
  if [ -s "$MODELS/$sub/$name" ]; then
    echo "skip (exists): $sub/$name"; continue
  fi
  todo=1
  echo "download: $sub/$name"
  SECONDS=0
  fetch "$url" "$MODELS/$sub/$name"
  bytes="$(stat -c %s "$MODELS/$sub/$name")"
  echo "done: $sub/$name $((bytes / 1048576)) MiB in ${SECONDS}s (~$((bytes / 1048576 / (SECONDS > 0 ? SECONDS : 1))) MiB/s)"
done < <(grep -vE '^\s*(#|$)' "$MANIFEST")

[ "$todo" = 1 ] || echo "nothing to download"
echo "Verify sizes:"; du -ah "$MODELS" | sort -h | tail -15
