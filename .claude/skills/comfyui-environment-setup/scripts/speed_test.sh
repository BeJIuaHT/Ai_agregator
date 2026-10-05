#!/usr/bin/env bash
# Run ON the pod, FIRST, before installing anything: download-speed gate for a model URL.
# Usage: bash speed_test.sh <url> [min_MBps=100]
# Reads SAMPLE_MB (default 32) per stream from the real URL and discards it: first 1 stream, then STREAMS
# (default 8) parallel streams at different offsets. Needs a file of at least STREAMS*SAMPLE_MB.
# Exit 0 if the best result >= min_MBps, exit 1 otherwise = STOP, report the host to the orchestrator
# (devops-agent terminates the pod and picks another host). Never grind on a slow host.
set -euo pipefail

URL="${1:?url}"
MIN="${2:-100}"
STREAMS="${STREAMS:-8}"
S=$(( ${SAMPLE_MB:-32} * 1048576 ))
HDR=()
[ -n "${HF_TOKEN:-}" ] && HDR=(-H "Authorization: Bearer $HF_TOKEN")
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

run() {  # n_streams -> MB/s (decimal) aggregated over wall time
  local n="$1" i t0 t1 total
  rm -f "$tmp"/b.*
  t0="$(date +%s.%N)"
  for ((i = 0; i < n; i++)); do
    curl -sSL --fail ${HDR[@]+"${HDR[@]}"} -r "$((i * S))-$((i * S + S - 1))" -o /dev/null \
      -w '%{size_download}\n' "$URL" > "$tmp/b.$i" &
  done
  wait
  t1="$(date +%s.%N)"
  total="$(cat "$tmp"/b.* | awk '{s+=$1} END{print s+0}')"
  awk -v b="$total" -v t0="$t0" -v t1="$t1" 'BEGIN{printf "%.1f", b/(t1-t0)/1e6}'
}

one="$(run 1)"; par="$(run "$STREAMS")"
echo "single stream: ${one} MB/s; ${STREAMS} parallel streams: ${par} MB/s (gate: ${MIN} MB/s)"
if awk -v a="$one" -v b="$par" -v m="$MIN" 'BEGIN{exit !((a>b?a:b) >= m)}'; then
  echo "SPEED OK"
else
  echo "SPEED TOO LOW: stop, do not install or download on this host" >&2
  exit 1
fi
