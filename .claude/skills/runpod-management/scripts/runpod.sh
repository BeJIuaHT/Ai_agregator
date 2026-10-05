#!/usr/bin/env bash
# RunPod helper: REST v1 (rest.runpod.io/v1) + GraphQL (api.runpod.io/graphql)
# Usage: runpod.sh <command> [args]   (loads .env from repo root)
# Read-only: gpus | dcs | pods | pod <id> | volumes
# Billable (need RUNPOD_ALLOW_SPEND=yes): create-volume | create-pod
# Billable, no volume: create-pod-novol <name> [SECURE|COMMUNITY] [disk_gb]
# Stop/cleanup: start <id> (billable) | stop <id> | terminate <id> | delete-volume <id>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
[ -f "$ROOT/.env" ] && set -a && . "$ROOT/.env" && set +a
: "${RUNPOD_API_KEY:?RUNPOD_API_KEY is not set (.env)}"

REST="https://rest.runpod.io/v1"
GQL="https://api.runpod.io/graphql"
AUTH=(-H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json")

rest() { curl -sS --fail-with-body "${AUTH[@]}" -X "$1" "$REST$2" ${3:+-d "$3"}; echo; }
gql()  { curl -sS --fail-with-body "${AUTH[@]}" -X POST "$GQL" -d "$(python3 -c 'import json,sys;print(json.dumps({"query":sys.argv[1]}))' "$1")"; echo; }
need_spend() {
  [ "${RUNPOD_ALLOW_SPEND:-no}" = "yes" ] || { echo "BLOCKED: set RUNPOD_ALLOW_SPEND=yes in .env (user approval required)" >&2; exit 3; }
}

cmd="${1:-help}"; shift || true
case "$cmd" in
  gpus)  # prices + stock for priority GPUs
    gql 'query { gpuTypes { id displayName memoryInGb secureCloud communityCloud
      lowestPrice(input:{gpuCount:1}) { minimumBidPrice uninterruptablePrice stockStatus } } }' ;;
  dcs)   # datacenters (pick one where the target GPU is in stock; volume is bound to it)
    gql 'query { dataCenters { id name location } }' ;;
  pods)    rest GET /pods ;;
  pod)     rest GET "/pods/${1:?pod id}" ;;
  volumes) rest GET /networkvolumes ;;
  create-volume) # <name> <size_gb> <dataCenterId>
    need_spend
    body=$(python3 -c 'import json,sys;print(json.dumps({"name":sys.argv[1],"size":int(sys.argv[2]),"dataCenterId":sys.argv[3]}))' "${1:?name}" "${2:?size_gb}" "${3:?dataCenterId}")
    rest POST /networkvolumes "$body" ;;
  create-pod)    # <name> <networkVolumeId> <dataCenterId> <gpuTypeId> [cloud=SECURE|COMMUNITY]
    need_spend
    pub="$(cat "$ROOT/${SSH_PUBLIC_KEY_FILE:-workspace/keys/runpod_ed25519.pub}")"
    body=$(python3 - "$@" "$pub" <<'PY'
import json,sys
name,vol,dc,gpu=sys.argv[1:5]
cloud=sys.argv[5] if len(sys.argv)>6 else "SECURE"
pub=sys.argv[-1]
print(json.dumps({
  "name":name,"computeType":"GPU","cloudType":cloud,
  "gpuTypeIds":[gpu],"gpuCount":1,"dataCenterIds":[dc],
  "networkVolumeId":vol,"volumeMountPath":"/workspace",
  "containerDiskInGb":50,
  "imageName":"runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
  "ports":["8188/http","22/tcp"],
  "supportPublicIp":True,
  "env":{"PUBLIC_KEY":pub}}))
PY
)
    rest POST /pods "$body" ;;
  create-pod-novol) # <name> [cloud=SECURE|COMMUNITY] [disk_gb=30]  (no volume, no DC pin, GPU chain in order)
    need_spend
    pub="$(cat "$ROOT/${SSH_PUBLIC_KEY_FILE:-workspace/keys/runpod_ed25519.pub}")"
    body=$(python3 - "${1:?name}" "${2:-SECURE}" "${3:-30}" "$pub" <<'PY'
import json,sys
name,cloud,disk,pub=sys.argv[1:5]
print(json.dumps({
  "name":name,"computeType":"GPU","cloudType":cloud,
  "gpuTypeIds":["NVIDIA RTX A4000","NVIDIA RTX A4500","NVIDIA RTX 4000 Ada Generation","NVIDIA GeForce RTX 3090","NVIDIA GeForce RTX 4090"],
  "gpuTypePriority":"custom","gpuCount":1,
  "containerDiskInGb":int(disk),
  "imageName":"runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
  "ports":["8188/http","22/tcp"],
  "supportPublicIp":True,
  "env":{"PUBLIC_KEY":pub}}))
PY
)
    rest POST /pods "$body" ;;
  stop)          rest POST "/pods/${1:?pod id}/stop" ;;
  start)         need_spend; rest POST "/pods/${1:?pod id}/start" ;;
  terminate)     rest DELETE "/pods/${1:?pod id}" ;;
  delete-volume) rest DELETE "/networkvolumes/${1:?volume id}" ;;
  *) sed -n '2,7p' "${BASH_SOURCE[0]}" ;;
esac
