# Wan 2.2 image-to-video (I2V-A14B + lightx2v 4-step LoRA; TI2V-5B)
Checked 2026-10-05. Sources:
- https://raw.githubusercontent.com/Wan-Video/Wan2.2/main/wan/utils/system_prompt.py (OFFICIAL I2V prompt-extension system prompt = what the model is meant to be fed; primary source)
- https://raw.githubusercontent.com/Wan-Video/Wan2.2/main/wan/configs/shared_config.py , wan_ti2v_5B.py , wan_i2v_A14B.py (official defaults, default negative prompt)
- https://github.com/Wan-Video/Wan2.2 , https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B (5B: 24 fps, 1280x704 / 704x1280)
- https://docs.comfy.org/tutorials/video/wan/wan2_2 (ComfyUI native workflows, 5B / 14B I2V)
- https://huggingface.co/lightx2v/Wan2.2-Lightning and discussion /26 (4 steps, no CFG; the authors confirm slow-motion issue)
- https://github.com/princepainter/ComfyUI-PainterI2V (community fix for slow motion, says to name the motion pace explicitly)
- https://civitai.red/articles/25397/simple-and-effective-wan22-i2v-workflow (search snippet only, page 403: keep CFG 1.0 with lightx2v LoRAs; 1.1-1.5 on the high-noise sampler only if prompt adherence is weak)
- https://wan2.video/wan2.2-guide , https://www.viewcomfy.com/blog/wan2.2_prompt_guide_with_examples , https://unifically.com/blogs/wan-2.2-image-to-video-prompt-guide , https://wink.ai/blog/wan-2-2-image-to-video-prompt-guide (community guides; agree with the official rules)

## Prompt content (I2V)
- The image already defines subject, look, light and composition. The prompt describes ONLY what changes: subject motion, camera, pace. Officially, static descriptions that are visible in the image are removed from the prompt (official I2V system prompt: "avoid adding static scene descriptions; if the user's input already describes elements visible in the image, remove them").
- Official rewritten-prompt rules: <= 100 words, emphasise the main subject's action, KEEP camera wording ("the camera pushes in / pans left / moves from left to right"). Official examples are one or two plain sentences ("A black squirrel focuses on eating, occasionally looking around.", "The camera moves left, then pushes forward to capture a person sitting on a breakwater.").
- Community order: subject movement -> camera movement -> environment motion -> pace. Name a static camera explicitly if wanted, otherwise the model invents a drift.
- One clear action beat per clip. 4-5 s has room for one subject action + one camera move; stacked actions come out smeared. Give an end state ("ends with the sword low beside his leg") so the last second does not drift.
- Concrete verbs and directions ("slashes down and to the left") beat vague ones ("moves", "fights"). Left/right = image left/right.
- Pace words matter: lightx2v 4-step is known to give SLOW motion; write "fast", "quick", "whips", "snaps" explicitly. If still slow: PainterI2V node (motion_amplitude 1.15-1.3), LoRA strength 0.5-0.8 on high-noise, or 3-sampler scheme (plan.md risk section).
- Style words: the image carries the style; one short anchor ("2D anime animation style") is enough and helps keep painted anime from drifting to 3D.
- Length: community says 80-120 words (viewcomfy), official extension caps at 100. We use 60-100 words. Too short -> Wan fills the gap with its own "cinematic" motion.

## Language
- Text encoder umT5-XXL is multilingual; official prompt extension outputs English or Chinese (en/zh variants of the system prompt). English is fine; no need for Chinese. The official default negative is Chinese (see below), keep it Chinese.

## Negative prompt / CFG
- A14B + lightx2v 4-step LoRA: CFG 1.0 (the LoRA is distilled "without the CFG trick"). In ComfyUI at cfg == 1.0 the unconditional branch is skipped, so the negative prompt has NO effect there. We still ship a negative in the built file (harmless, needed by the shared graph); do not expect it to work. (cfg-1 behaviour is from ComfyUI sampler logic, not found on a doc page; the lightx2v card/civitai only say "cfg 1".)
- Raising CFG to 1.1-1.5 on the high-noise sampler is the community knob for prompt adherence; then negative starts to count a little.
- Official A14B settings without LoRA: 40 steps, cfg 3.5/3.5 (low/high), shift 5.0, boundary 0.9. TI2V-5B official: 50 steps, cfg 5.0, shift 5.0, 24 fps, 121 frames; here we run 20-30 steps cfg 5 (plan.md).
- TI2V-5B (cfg 5): negative works. Official default (shared_config.py): `色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走`.
  Our block `blocks/negative/wan_i2v_anime.txt` is a trimmed version for painted anime: removed 色调艳丽 (garish colours), 风格/作品/画作/画面 (style/artwork/painting/picture: would fight the anime look), 杂乱的背景, 背景人很多 (we want skeleton/goblin backgrounds), 倒着走, 三条腿; kept 静态/静止 (static, pushes motion); added 多余的武器, 融合的武器 (extra/fused weapons).

## Frames / resolution (our run)
- Length must be 4n+1: 65 frames @16 fps = 4.06 s (A14B native 16 fps). 5B is natively 24 fps / 121 frames; at 16 fps in our test clips motion will look slower than at 24.
- 704x480 for A14B is within the 480p bucket. TI2V-5B is trained for 1280x704 / 704x1280, 480p is below its training size (quality risk, plan.md).
- I2V in ComfyUI needs no CLIP-vision for Wan 2.2.

## Camera / motion vocabulary that Wan 2.2 follows
push-in / pull-out (dolly in/out), pan left/right, tilt up/down, tracking shot (follows the subject), orbit/arc, handheld, crane up, static camera. One camera move per clip. Speed terms: slowly, steadily, quickly, whip, snap, slow-motion.

## Known failure modes and workaround
- Slow motion with lightx2v 4-step: see pace words above / PainterI2V / 3-sampler. Vertical resolutions suffer more than horizontal (HF discussion /26); we are horizontal.
- Large, fast limb/weapon motion: weapons bend, split or duplicate, hands melt (also the lightx2v card: "extremely large motion may include artifacts"). Workaround: describe one weapon motion per character, keep arcs inside the frame, no weapon swaps, generate 2-4 seeds and pick.
- Crowds and translucent/low-contrast figures: the model treats them as background texture (fade, melt into sky). Keep 1-3 clear subjects.
- Mid-air / ambiguous poses and heavy motion blur in the start frame: the model cannot tell where limbs are, expect morphing. Prefer sharp start frames with readable poses.
- Hidden characters: the model does not add enemies that are off-frame; do not write "attacks the goblin" if no goblin is in the image (the prompt cannot create a subject that is not visible, it only animates what is there; use a camera move to reveal one if needed).
- Text-in-image / subtitles: avoid; negative `字幕`.
- Same seed + same prompt = repeatable; keep one seed note per clip (workflow decides).
