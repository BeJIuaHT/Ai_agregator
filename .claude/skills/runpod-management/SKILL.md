---
name: runpod-management
description: Build and send RunPod API requests (REST v1 + GraphQL) to find GPUs (RTX 4090 / A100 80GB / H100), create Network Volumes, deploy Pods with a volume and ports 8188+22, and stop/terminate them. Use for any RunPod resource management.
---

# runpod-management

All authenticated calls go through `scripts/runpod.sh` (curl + Bearer token from `.env`).
The `fetch` MCP cannot send auth headers or POST, so do not use it for RunPod.
**Creating anything billable is blocked unless `RUNPOD_ALLOW_SPEND=yes`.** The flag stays `no` until the user approves a plan; never edit it yourself.

## Commands
| Command | Notes |
|---|---|
| `gpus`, `dcs`, `pods`, `pod <id>`, `volumes` | read-only, free |
| `create-pod-novol <name> [SECURE\|COMMUNITY] [disk_gb=30]` | billable. No volume, no datacenter pin, GPU chain A4000 -> A4500 -> 4000 Ada -> 3090 -> 4090. Cloud defaults to SECURE (Community is cheaper: pass it explicitly). GPUs listed above `RUNPOD_MAX_PRICE` (default 0.25 $/h) are dropped; none left = abort, nothing created |
| `create-volume <name> <size_gb> <dcId>` + `create-pod <name> <volumeId> <dcId> <gpuTypeId> [cloud]` | billable, volume path (see below) |
| `start <id>` | billable. A stopped Community pod often cannot restart (host has no free GPU): do not plan on resuming |
| `stop <id>` | keeps the disk, still bills disk |
| `terminate <id>` | full delete: do this once outputs are downloaded |
| `terminate-all` | emergency cleanup: deletes ALL pods, leaves volumes, prints what is left. Free, no flag needed |
| `delete-volume <id>` | volume bills until deleted |

Env overrides: `RUNPOD_IMAGE` (default `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`, torch 2.4.1; `setup_comfyui.sh` upgrades torch to 2.7.1 on it, or pass an image with torch 2.7+ whose tag you verified), `RUNPOD_MAX_PRICE`.

## Workflow, no volume (current default for short runs)
1. `runpod.sh gpus` (read-only): check price and stock. 2. `create-pod-novol <name> COMMUNITY 30`; compare the reported price with the limit given by the orchestrator, if higher: `terminate` at once. 3. Poll `pod <id>` until `desiredStatus=RUNNING` and `publicIp`/`portMappings` (SSH on the mapped port for 22/tcp). 4. After the run `terminate <id>`, then `pods` and `volumes` must be `[]`. Community pod `/workspace` is only about 20 GB.

## Workflow with a Network Volume (optional: weights reused across sessions)
1. `runpod.sh gpus` — read-only; pick GPU by priority: RTX 4090 -> A100 80GB -> H100 (check `stockStatus`, price; pick Secure vs Community).
2. `runpod.sh dcs` — choose a datacenter where the GPU is in stock. **A Network Volume is bound to one datacenter, and the Pod must run in that same datacenter.**
3. `runpod.sh create-volume <name> <size_gb> <dcId>` — model storage (Wan2.1 14B needs ~100-150 GB).
4. `runpod.sh create-pod <name> <volumeId> <dcId> <gpuTypeId> [SECURE|COMMUNITY]`
5. Poll `runpod.sh pod <id>` until `desiredStatus=RUNNING` and `portMappings`/`publicIp` are present (SSH on mapped port for 22/tcp).
6. When done: `terminate <id>`; the volume keeps billing until `delete-volume`.

## GPU type IDs (REST `gpuTypeIds`)
- `NVIDIA GeForce RTX 4090`
- `NVIDIA A100 80GB PCIe`, `NVIDIA A100-SXM4-80GB`
- `NVIDIA H100 80GB HBM3`, `NVIDIA H100 PCIe`
Verify exact IDs against the `gpus` output; they change.

## Templates

GraphQL — GPU search (POST https://api.runpod.io/graphql):
```graphql
query { gpuTypes { id displayName memoryInGb secureCloud communityCloud
  lowestPrice(input:{gpuCount:1}) { minimumBidPrice uninterruptablePrice stockStatus } } }
```

REST — create Network Volume (POST https://rest.runpod.io/v1/networkvolumes):
```json
{ "name": "comfy-models", "size": 150, "dataCenterId": "EU-RO-1" }
```

REST — create Pod (POST https://rest.runpod.io/v1/pods):
```json
{
  "name": "comfy-video", "computeType": "GPU", "cloudType": "SECURE",
  "gpuTypeIds": ["NVIDIA GeForce RTX 4090"], "gpuCount": 1,
  "dataCenterIds": ["EU-RO-1"],
  "networkVolumeId": "<VOLUME_ID>", "volumeMountPath": "/workspace",
  "containerDiskInGb": 50,
  "imageName": "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
  "ports": ["8188/http", "22/tcp"], "supportPublicIp": true,
  "env": { "PUBLIC_KEY": "<ssh-ed25519 AAAA...>" }
}
```
Stop: `POST /pods/{id}/stop` · Terminate: `DELETE /pods/{id}` · List: `GET /pods` · Volumes: `GET|DELETE /networkvolumes[/{id}]`.

## Access after deploy
- ComfyUI: `https://<podId>-8188.proxy.runpod.net` (proxy; ~100 s request timeout, so poll `/history`, don't hold requests).
- SSH: use `publicIp` + external port from `portMappings["22"]` (not the proxy).

## Rules
- Before any create: state GPU, hourly price, datacenter, volume size and get orchestrator OK.
- Record returned IDs in `.env` (`RUNPOD_POD_ID`, `RUNPOD_VOLUME_ID`).
- On any error after creation, terminate the pod before retrying.
- Docs: https://docs.runpod.io/api-reference (re-check field names if a call returns 400).
