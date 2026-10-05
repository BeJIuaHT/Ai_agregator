---
name: comfyui-environment-setup
description: Generate and run Bash scripts over SSH that install ComfyUI + ComfyUI-Manager + custom nodes on a RunPod pod (torch 2.7+ check included), test download speed against the real model URL, and download model weights (checkpoints/VAE/LoRA/ControlNet) in parallel with curl ranges into /workspace.
---

# comfyui-environment-setup

Scripts in `scripts/` run **on the pod** and are copied via `scp`. `/workspace` is the pod's disk: a Network Volume if the pod was created with one, otherwise the container disk (the default `create-pod-novol` path, about 20 GB usable on a Community pod, wiped on terminate).

| Script | Purpose |
|---|---|
| `speed_test.sh <url> [min_MBps=100]` | Download-speed gate on the real model URL (1 stream, then 8 parallel). Exit 1 = host too slow |
| `setup_comfyui.sh [git_url...]` | ComfyUI, venv, torch 2.7+ check (installs 2.7.1 if older), Manager, VHS, Frame-Interpolation, extra model nodes, `start_comfy.sh` |
| `download_models.sh <manifest>` | 8 parallel `curl -r` ranges per file into one pre-truncated `.part`, renamed when done; skips existing files |
| `models.manifest.template` | Manifest format; copy to `workspace/scripts/models.manifest` and fill per target model |

## Procedure
1. Get host/port from `runpod-management` (`pod <id>` -> publicIp + port mapped to 22).
2. `scp -i $SSH_PRIVATE_KEY_FILE -P <port> .claude/skills/comfyui-environment-setup/scripts/* root@<ip>:/workspace/`
3. **Speed gate first:** `ssh ... 'bash /workspace/speed_test.sh <largest-model-url> 100'`. Exit 1 = stop, report host and speeds to the orchestrator (devops-agent terminates the pod and picks another host). Do nothing else on that host.
4. `ssh -i ... -p <port> root@<ip> 'bash /workspace/setup_comfyui.sh <model-node-urls>'`
5. `ssh ... 'export HF_TOKEN=...; bash /workspace/download_models.sh /workspace/models.manifest'` (long: run under `setsid nohup ... < /dev/null &`, tail the log).
6. Start: `ssh ... 'setsid nohup /workspace/start_comfy.sh > /workspace/comfy.log 2>&1 < /dev/null &'`, then check `curl localhost:8188/system_stats`. Reach the API from the repo through an SSH tunnel to 127.0.0.1:8188.

## Rules
- Use `ssh -o StrictHostKeyChecking=accept-new` for first connect; never disable key auth.
- Everything persistent goes under `/workspace`. Without a volume it is lost on terminate: download results (outputs) to the repo BEFORE the pod is terminated.
- Model URLs/filenames must be real: `download_models.sh` requires HTTP 200 and a size; also verify with `curl -sIL <url> | head` before tens of GB.
- Check `df -h /workspace` before downloads.
- Target model is chosen per task by `model-selector-agent` (`workspace/plan.md`): nodes and manifest stay templates until a plan is approved.

## Lessons from real runs (hard rules)
- **Speed gate first.** Files over 300 MB need at least 100 MB/s; otherwise stop and have the pod recreated on another host. Never grind on a slow host.
- **Torch 2.7+.** The `runpod/pytorch:2.4.0` image has torch 2.4.1, on which current ComfyUI crashes (`comfy_kitchen`, `infer_schema ... list[int]`). `setup_comfyui.sh` fixes it with `pip install torch==2.7.1 ... cu126` (override via `TORCH_VERSION`, `TORCH_INDEX`); or pass an image with torch 2.7+ through `RUNPOD_IMAGE` (verify the tag exists, do not guess).
- **No aria2c.** It is not preinstalled; `download_models.sh` uses curl ranges + `dd conv=notrunc oflag=seek_bytes`, no segment files, no double disk use.
- **Disk.** Community pod `/workspace` is about 20 GB regardless of the requested container disk. For big weights (30+ GB) create the pod with a large container disk (e.g. 100 GB) and run both scripts with `WS=/root/ws` and `MODELS_DIR=/root/ws/ComfyUI/models`.
- **Parallel setup + download is safe.** `download_models.sh` may create `ComfyUI/models` before `setup_comfyui.sh` runs `git clone`; the setup script clones aside and merges, so run them at the same time.
- **Manifest lines:** `<subdir> <filename> <url>`, comments only on their own `#` line (the loop reads `url` as the rest of the line, a trailing `# note` would end up in the URL).
- **Keep ComfyUI alive:** `setsid nohup ... < /dev/null &`.
- **Time box:** 15 minutes for the whole provisioning; report and stop at the limit.
- **pkill trap:** never `pkill -f <pattern>` inside a Bash/ssh command (kills your own shell); use `[x]` bracket patterns, `pgrep -x` or a PID.
