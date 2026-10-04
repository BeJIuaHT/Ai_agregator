---
name: runpod-management
description: Build and send RunPod API requests (REST v1 + GraphQL) to find GPUs (RTX 4090 / A100 80GB / H100), create Network Volumes, deploy Pods with a volume and ports 8188+22, and stop/terminate them. Use for any RunPod resource management.
---

# runpod-management

All authenticated calls go through `scripts/runpod.sh` (curl + Bearer token from `.env`).
The `fetch` MCP cannot send auth headers or POST, so do not use it for RunPod.
**Creating anything billable is blocked unless `RUNPOD_ALLOW_SPEND=yes`.** During preparation it stays `no`.

## Workflow (strict order)
1. `runpod.sh gpus` — read-only; pick GPU by priority: RTX 4090 -> A100 80GB -> H100 (check `stockStatus`, price; pick Secure vs Community).
2. `runpod.sh dcs` — choose a datacenter where the GPU is in stock. **A Network Volume is bound to one datacenter, and the Pod must run in that same datacenter.**
3. `runpod.sh create-volume <name> <size_gb> <dcId>` — model storage (Wan2.1 14B needs ~100-150 GB).
4. `runpod.sh create-pod <name> <volumeId> <dcId> <gpuTypeId> [SECURE|COMMUNITY]`
5. Poll `runpod.sh pod <id>` until `desiredStatus=RUNNING` and `portMappings`/`publicIp` are present (SSH on mapped port for 22/tcp).
6. When done: `stop <id>` (keeps container disk, still bills disk) or `terminate <id>` (full delete). Volume keeps billing until `delete-volume`.

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
