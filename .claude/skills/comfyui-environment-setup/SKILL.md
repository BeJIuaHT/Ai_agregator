---
name: comfyui-environment-setup
description: Generate and run Bash scripts over SSH that install ComfyUI + ComfyUI-Manager + video custom nodes (VideoHelperSuite, Frame-Interpolation, model-specific nodes) on a RunPod pod, and download model weights (checkpoints/VAE/LoRA/ControlNet) in parallel with aria2c into the Network Volume.
---

# comfyui-environment-setup

Scripts in `scripts/` run **on the pod** (`/workspace` = Network Volume), copied via `scp`:

| Script | Purpose |
|---|---|
| `setup_comfyui.sh [git_url...]` | ComfyUI, venv on volume, Manager, VHS, Frame-Interpolation, extra model nodes, `start_comfy.sh` |
| `download_models.sh <manifest>` | aria2c parallel (16 conn/file, 3 files at once), resumable, skips existing |
| `models.manifest.template` | Manifest format; copy to `workspace/scripts/models.manifest` and fill per target model |

## Procedure
1. Get host/port from `runpod-management` (`pod <id>` -> publicIp + port mapped to 22).
2. `scp -i $SSH_PRIVATE_KEY_FILE -P <port> .claude/skills/comfyui-environment-setup/scripts/* root@<ip>:/workspace/`
3. `ssh -i ... -p <port> root@<ip> 'bash /workspace/setup_comfyui.sh <model-node-urls>'`
4. `ssh ... 'export HF_TOKEN=...; bash /workspace/download_models.sh /workspace/models.manifest'` (long: run under `nohup`/`tmux`, tail the log).
5. Start: `ssh ... 'nohup /workspace/start_comfy.sh > /workspace/comfy.log 2>&1 &'`, then check `curl localhost:8188/system_stats`.

## Rules
- Use `ssh -o StrictHostKeyChecking=accept-new` for first connect; never disable key auth.
- Everything persistent goes under `/workspace` (volume); container disk is wiped on terminate.
- Model URLs/filenames must be real: verify each URL with `curl -sIL <url> | head` (HTTP 200/302) before downloading tens of GB.
- Check `df -h /workspace` before downloads.
- Target model is not chosen yet: nodes and manifest stay as templates until the user decides.
