#!/usr/bin/env bash
# Run ON the pod (via ssh). Installs ComfyUI + Manager + video nodes into /workspace (volume or container disk).
# Idempotent: safe to re-run. Usage: bash setup_comfyui.sh [extra_node_git_url ...]
set -euo pipefail

WS="${WS:-/workspace}"
COMFY="$WS/ComfyUI"
NODES="$COMFY/custom_nodes"

apt-get update -qq && apt-get install -y -qq git ffmpeg curl >/dev/null

# download_models.sh may run in parallel and create $COMFY/models first; `git clone` refuses a non-empty dir,
# so clone aside and merge on top (keeps files that are already downloading).
if [ ! -d "$COMFY/.git" ]; then
  tmp="$COMFY.clone.$$"
  git clone https://github.com/comfyanonymous/ComfyUI.git "$tmp"
  mkdir -p "$COMFY"
  cp -a "$tmp"/. "$COMFY"/
  rm -rf "$tmp"
fi

# venv lives on the volume so it survives pod recreation
[ -d "$WS/venv" ] || python3 -m venv --system-site-packages "$WS/venv"
. "$WS/venv/bin/activate"
pip install -q -U pip
# Current ComfyUI needs torch 2.7+ (the runpod/pytorch:2.4.0 image ships 2.4.1 and ComfyUI crashes on it)
if ! python -c 'import sys, torch; sys.exit(0 if tuple(map(int, torch.__version__.split("+")[0].split(".")[:2])) >= (2, 7) else 1)' 2>/dev/null; then
  pip install -q "torch==${TORCH_VERSION:-2.7.1}" torchvision torchaudio --index-url "${TORCH_INDEX:-https://download.pytorch.org/whl/cu126}"
fi
python -c 'import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())'
pip install -q -r "$COMFY/requirements.txt"

clone_node() {
  local url="$1" dir="$NODES/$(basename "${1%.git}")"
  [ -d "$dir/.git" ] && git -C "$dir" pull -q || git clone -q "$url" "$dir"
  [ -f "$dir/requirements.txt" ] && pip install -q -r "$dir/requirements.txt" || true
}

mkdir -p "$NODES"
clone_node https://github.com/ltdrdata/ComfyUI-Manager.git
clone_node https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
clone_node https://github.com/Fannovel16/ComfyUI-Frame-Interpolation.git
# Model-specific nodes (decided once the target model is chosen), e.g.:
#   Wan2.1:  https://github.com/kijai/ComfyUI-WanVideoWrapper.git
#   Hunyuan: https://github.com/kijai/ComfyUI-HunyuanVideoWrapper.git
#   CogVideoX: https://github.com/kijai/ComfyUI-CogVideoXWrapper.git
#   AnimateDiff: https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git
for u in "$@"; do clone_node "$u"; done

# Frame-Interpolation needs its install script (downloads cupy etc.)
[ -f "$NODES/ComfyUI-Frame-Interpolation/install.py" ] && python "$NODES/ComfyUI-Frame-Interpolation/install.py" || true

cat > "$WS/start_comfy.sh" <<EOF
#!/usr/bin/env bash
. $WS/venv/bin/activate
cd $COMFY && exec python main.py --listen 0.0.0.0 --port 8188
EOF
chmod +x "$WS/start_comfy.sh"
echo "OK: ComfyUI installed. Start with: nohup $WS/start_comfy.sh > $WS/comfy.log 2>&1 &"
