# Plan: minimal anime text-to-image smoke test on RunPod (budget cap: $1 total)

Status: PROPOSAL, awaiting user approval. Nothing has been created. RUNPOD_ALLOW_SPEND stays `no` until the user says so.
Prices below come from read-only `runpod.sh gpus` on 2026-10-04 (live; stock is "Low" for every cheap GPU, so the plan lists fallbacks).

## 1. Model
- Animagine XL 4.0 (SDXL fine-tune, anime, tag-based prompts), fp16 safetensors as published. No further quantization: 6.94 GB fits a 16 GB GPU with room, and fp8/GGUF would save nothing worth the risk for a one-off test.
- License: CreativeML OpenRAIL++ (commercial use allowed with use restrictions). Repo is NOT gated: no HF token required (HTTP 200 on the direct URL, verified with a HEAD request).
- The VAE is embedded in the checkpoint, so no separate VAE download is needed.
- Why not SD1.5 anime: it saves about 5 GB of download (about 1 minute, under $0.01) but gives much weaker output. Not worth it.

models.manifest rows (dest is relative to ComfyUI root):
| url | dest | size | sha/notes |
|---|---|---|---|
| https://huggingface.co/cagliostrolab/animagine-xl-4.0/resolve/main/animagine-xl-4.0.safetensors | models/checkpoints/animagine-xl-4.0.safetensors | 6,938,434,056 B (6.94 GB) | no token needed |

Fallback if that URL fails: https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors (6.94 GB, same license, ungated).
Total download: 6.94 GB. Custom nodes: none (core ComfyUI nodes only: CheckpointLoaderSimple, CLIPTextEncode, EmptyLatentImage, KSampler, VAEDecode, SaveImage).

## 2. GPU, cloud, datacenter
- Primary: NVIDIA RTX A4000 (16 GB), $0.17/h (cheapest GPU with at least 16 GB; the 8 GB RTX 3070 at $0.13 is rejected, SDXL fp16 would need lowvram and risks OOM, saving only $0.04/h).
- Fallback chain, same request (gpuTypeIds order): RTX A4500 20 GB $0.19/h, RTX 4000 Ada 20 GB $0.20/h, RTX 3090 24 GB $0.22/h, RTX 4090 24 GB $0.34/h.
- The API shows only the lowest price across clouds; A4000 is listed in both Secure and Community. Check the actual price in the create response. Use Secure if its price is at most $0.25/h (more reliable for a short non-resumable test), else Community.
- Datacenter: the read-only API gives no per-DC stock. Since there is NO volume, do not pin a datacenter: omit `dataCenterIds` (or pass the full list) and let RunPod place the pod wherever the GPU is free. This is the main stock-risk mitigation.
- Estimated speed (estimate, not measured): SDXL 1024x1024, 28 steps Euler a, about 12-20 s per image on an A4000 after the first (model load, about 30-60 s).

## 3. Storage: no Network Volume
- Use container disk only: 30 GB (checkpoint 7 GB + ComfyUI + torch deps with margin). Container disk is billed with the pod and disappears on terminate.
- Network Volume rejected: a 10 GB volume costs about $0.70/month and is bound to a datacenter (narrowing stock). For a single run, re-downloading 6.94 GB (about 1-3 min) is cheaper and simpler. Create no volume.
- Note for devops-agent: the current `runpod.sh create-pod` requires a volume ID and a DC and hard-codes containerDiskInGb=50. A no-volume variant is needed: omit networkVolumeId/volumeMountPath, set containerDiskInGb=30, set gpuTypeIds to the chain above, omit dataCenterIds.

## 4. Image, ports
- Image: `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` (already used in runpod.sh, Docker Hub, fast pull). Install ComfyUI from the official repo at pod start (about 2-3 min), instead of a third-party template of unknown trust.
- Ports: `8188/http` (ComfyUI, reachable at `https://<POD_ID>-8188.proxy.runpod.net`) and `22/tcp` (SSH, key via PUBLIC_KEY env). Prefer an SSH tunnel (`ssh -L 8188:localhost:8188`) for API calls so the UI is not exposed on the public proxy URL.
- Setup commands on the pod:
  ```
  cd /workspace 2>/dev/null || cd /root
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git && cd ComfyUI
  pip install -r requirements.txt
  aria2c -x16 -s16 -d models/checkpoints -o animagine-xl-4.0.safetensors \
    https://huggingface.co/cagliostrolab/animagine-xl-4.0/resolve/main/animagine-xl-4.0.safetensors
  nohup python main.py --listen 0.0.0.0 --port 8188 > comfy.log 2>&1 &
  ```
  (If aria2c is missing: `apt-get install -y aria2` or use `wget -c`.)

## 5. Test generation settings
Workflow: core API-format graph (CheckpointLoaderSimple -> 2x CLIPTextEncode -> EmptyLatentImage 832x1216 -> KSampler -> VAEDecode -> SaveImage). Settings per model card: sampler `euler_ancestral`, scheduler `normal`, steps 28, CFG 5, seed fixed. 832x1216 is a native SDXL portrait bucket.
Negative prompt (all runs): `lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry`

Prompts (Animagine tag order: count, character, series, rating, attributes, quality tags):
1. `1girl, silver hair, long hair, blue eyes, school uniform, cherry blossoms, looking at viewer, smile, upper body, safe, masterpiece, high score, great score, absurdres`
2. `1boy, black hair, short hair, red scarf, winter coat, night city, neon lights, snow, cinematic lighting, safe, masterpiece, high score, great score, absurdres`
3. `1girl, orange hair, twintails, green eyes, witch hat, magical staff, forest, glowing particles, fantasy, full body, safe, masterpiece, high score, great score, absurdres`

## 6. Time and cost estimate (A4000 at $0.17/h)
| Phase | Minutes |
|---|---|
| Pod provisioning + image pull | 3-6 |
| ComfyUI install (pip) | 2-4 |
| Checkpoint download (6.94 GB) | 1-3 |
| ComfyUI start + first load | 1-2 |
| 3 images | 1-2 |
| Debugging / retries / download of results | 10 |
| Total expected | about 20-27 |

- Expected cost: about 0.4 h x $0.17 = about $0.07.
- Conservative with margin: 90 min hard cap x $0.17 = $0.26. Worst case on the 4090 fallback ($0.34/h): 90 min = $0.51. Container disk (30 GB) adds about $0.01 or less.
- Every scenario stays below $1. Remaining budget buffer: at least $0.49.

## 7. Success criteria
- ComfyUI `/system_stats` returns 200 and lists the GPU; checkpoint appears in `/object_info/CheckpointLoaderSimple`.
- 3 PNGs saved in `ComfyUI/output/`, 832x1216, non-black, non-noise.
- Visually: anime style, coherent face/hair/colors matching each prompt, no heavy artifacts (minor hand errors acceptable).
- Per-image generation time under 40 s after warm-up; no OOM.
- Total session cost shown on the RunPod billing page under $0.50.
- PNGs downloaded locally to `/home/dev/Ai_agregator/workspace/output/` (scp or `/view` API) BEFORE terminate.

## 8. Mandatory end step: TERMINATE
1. Download outputs (see above).
2. `runpod.sh terminate <POD_ID>` (DELETE, not stop: stopped pods still bill container disk).
3. Verify: `runpod.sh pods` returns `[]` and `runpod.sh volumes` returns `[]`.
4. Safety nets: (a) the job script ends with the terminate call even on error (`trap`); (b) hard limit of 90 minutes: the orchestrator terminates the pod if it is still alive then; (c) the pod start command can also run `sleep 5400; runpodctl remove pod $RUNPOD_POD_ID` in the background as a dead-man switch.
5. Report the pod ID to the orchestrator immediately after creation so it can clean up on failure.

## 9. Risks and assumptions for user confirmation
- Stock is "Low" for all cheap GPUs; creation may fail on the first choice. Fallback chain covers it. Cost stays under $1 even on the 4090.
- Secure vs Community: price per cloud not verifiable via this API (only the minimum is shown). Confirm that Secure at up to $0.25/h is acceptable.
- Pod startup and HF download speeds vary by host; if the download is slower than 20 MB/s, abort and recreate on another host rather than burn time.
- OpenRAIL++ license: fine for a test. Check use restrictions before commercial use.
- Assumption: RunPod account has credit of at least $1 and an SSH key in `workspace/keys/` (already provided for runpod.sh).
- Requires user approval and `RUNPOD_ALLOW_SPEND=yes` before any create call.
