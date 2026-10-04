---
name: comfyui-api-workflow
description: Convert ComfyUI visual graphs to API-format JSON, validate them, submit to /prompt, poll /history/{prompt_id}, parse node execution errors and download results. Use when preparing or running ComfyUI video generation workflows.
---

# comfyui-api-workflow

## API format vs UI format
- UI graph JSON (has `nodes` + `links`) **cannot** be sent to `/prompt`.
- Export from ComfyUI: Settings -> enable Dev mode -> **Save (API Format)**. Result: `{ "<id>": {"class_type": "...", "inputs": {...}}, ... }`.
- A link input is `["<source_node_id>", <output_index>]`; literals are plain values.
- Store workflows in `workspace/workflows/<model>_<purpose>.api.json`; parametrize prompt/seed/frames by editing known node ids, not by regex.

## Endpoints
| Endpoint | Use |
|---|---|
| `POST /prompt` body `{"prompt": <api json>, "client_id": "<uuid>"}` | enqueue -> `{prompt_id, number, node_errors}`; HTTP 400 = validation errors in `node_errors` |
| `GET /history/{prompt_id}` | empty `{}` until finished; then `outputs` + `status` |
| `GET /queue` | running / pending |
| `GET /view?filename=&subfolder=&type=output` | download file |
| `GET /object_info` | installed nodes (verify `class_type` exist) |
| `GET /system_stats` | liveness, GPU/VRAM |

## Scripts
- `scripts/validate_workflow.py wf.json [--object-info URL]` — rejects UI format, dangling links, missing output node, uninstalled node classes.
- `scripts/submit_and_poll.py URL wf.json [--out DIR] [--timeout S]` — submit, poll every 5 s, print node-level errors, download outputs (`gifs`/`videos`/`images` keys; VHS_VideoCombine uses `gifs`).

## Error handling
- 400 on submit: read `node_errors` (missing model file name, wrong value type, missing input). The model filename in the workflow must match exactly a file in `models/<subdir>` (`/object_info/<Node>` lists valid choices).
- `status_str == "error"`: look at the `execution_error` message (`node_id`, `node_type`, `exception_message`). Typical: CUDA OOM -> lower resolution/frames or enable offload; missing custom node -> install via setup skill.
- Behind RunPod proxy a single HTTP request times out ~100 s: never hold requests, poll only.
- Use the `fetch` MCP only for unauthenticated GETs (`/system_stats`, `/object_info`, `/history`); POST needs the python script (via Bash).
