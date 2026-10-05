# Animagine XL 4.0 (cagliostrolab, SDXL, Danbooru tags)
Checked 2026-10-05. Sources:
- https://huggingface.co/cagliostrolab/animagine-xl-4.0 (official card)
- https://anifusion.ai/models/animagine-xl-4/ , https://note.com/kazumu/n/n6390a899bdce (community guides)

## Format
- Danbooru tags, comma separated. Natural language is ineffective (drifts to realistic/odd). Spaces in tags are fine (card examples use spaces).
- Official order: `1girl/1boy/1other, character, series, rating, everything else (any order), quality tags LAST`.
  Quality/score tags at the END of the prompt = strongest effect.
- Quality: `masterpiece, high score, great score, absurdres` (score tags steer harder than best quality).
- Rating: `safe | sensitive | nsfw | explicit`. We use `safe`.
- Era tags `year 2005..2025` optional (not used).
- No weighting needed; (tag:1.2) works in ComfyUI but not used here.

## Negative (supported, official)
`lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry`
Add scene-specific negatives (here: night, dark, sunset, etc. to hold bright daylight; plate armor/helmet for the light-armor knight).
Note: workflows/anime_sdxl_t2i.json node 3 has a hardcoded negative: the pipeline must replace it with the built NEGATIVE.

## Settings
CFG 4-7 (5), steps 25-28 (28), Euler Ancestral, normal scheduler. Resolutions: 1216x832 / 1152x896 / 1344x768 landscape. Workflow already matches.

## Length
SDXL CLIP: 77 tokens per chunk (75 usable). ComfyUI CLIPTextEncode splits longer prompts into several chunks and concatenates them, so >75 works, but: subjects and main action go FIRST (first chunk is strongest), keep total <= ~150 tokens (2 chunks). A comma = 1 token, a tag is ~2-3 tokens. assemble_prompt.py prints a heuristic estimate (no tokenizer installed).

## Camera / subjects
- Camera tags work: wide shot, cowboy shot, from below, from above, from side, dutch angle, dynamic angle, motion blur.
- Multi-subject: count tags (`1boy, 1girl`) set the human count. Non-human monsters are NOT counted with 1boy/2boys; do not use `2boys` for skeletons (it makes extra humans).
- Colour bleeding is strong: red hair tends to bleed into clothes/capes. Keep the knight's palette blue/brown/steel; use red only for the rogue's hair.

## Failure modes and workarounds
- Hands/weapons: fused or extra blades, extra arms. Workaround: 4-6 variants per frame, short unambiguous weapon tags (`holding greatsword`, `two-handed`, `dual wielding, holding dagger`), negative `extra arms, extra swords, fused weapons`.
- Crowds become mush at 5+ figures: name 2-3 distinct undead types per frame, rest only as small distant background.
- Same character across frames drifts without LoRA/IP-Adapter: identical verbatim blocks + fixed seed family; accept hair/face variation.
- "dark fantasy" pulls toward dark/moody; counter with explicit `harsh sunlight, strong shadows, blue sky` and negative `night, dark, sunset, overcast`.
