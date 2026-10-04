#!/usr/bin/env bash
# Run ON the pod (via ssh). Installs ComfyUI + Manager + video nodes into the Network Volume.
# Idempotent: safe to re-run. Usage: bash setup_comfyui.sh [extra_node_git_url ...]
set -euo pipefail

WS="${WS:-/workspace}"
COMFY="$WS/ComfyUI"
NODES="$COMFY/custom_nodes"

apt-get update -qq && apt-get install -y -qq aria2 git ffmpeg curl >/dev/null

[ -d "$COMFY/.git" ] || git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFY"

# venv lives on the volume so it survives pod recreation
[ -d "$WS/venv" ] || python3 -m venv --system-site-packages "$WS/venv"
. "$WS/venv/bin/activate"
pip install -q -U pip
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
