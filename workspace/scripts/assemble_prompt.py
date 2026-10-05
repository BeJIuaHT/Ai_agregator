#!/usr/bin/env python3
"""Assemble a prompt from reusable blocks listed in a scene JSON.

Blocks live in workspace/prompts/blocks/<category>/<name>.txt (one block = one file, text verbatim).
Scene JSON (workspace/prompts/scenes/<scene>.json):
{
  "style": "animagine",                       # blocks/style/animagine.txt
  "negative": "animagine",                    # blocks/negative/animagine.txt
  "shot": "medium shot, low angle",           # free text: camera/composition
  "characters": [{"character": "knight", "outfit": "knight_plate", "action": "swinging sword overhead"}],
  "location": "grassland_forest_edge",
  "extras": ["goblins_2"],                    # blocks/extras/*.txt: crowd, props, weather, lighting
  "action": "free text: what happens in the scene",
  "motion": "optional, video models only: camera + subject motion over the clip (omit for images)",
  "lead": "1boy, 1girl, safe",                # tags format: placed FIRST (subject count, rating) per Animagine order
  "quality": "quality_animagine",             # blocks/style/*.txt placed LAST (tags format); "style" then goes before it
  "plot_ru": "ignored by the script",
  "format": "tags"                            # tags (SDXL/Danbooru) | natural (Wan/Flux/LTX sentences)
}
Usage: assemble_prompt.py <scene.json|name> [--out workspace/prompts/built] [--json]
Prints positive and negative prompt; writes <out>/<scene>.txt. Duplicate tags are removed (order kept).
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOCKS = ROOT / "workspace/prompts/blocks"
SCENES = ROOT / "workspace/prompts/scenes"


def block(category, name):
    p = BLOCKS / category / f"{name}.txt"
    if not p.exists():
        sys.exit(f"missing block: {p.relative_to(ROOT)}")
    return p.read_text(encoding="utf-8").strip()


def dedupe(parts):
    seen, out = set(), []
    for tag in (t.strip() for part in parts for t in part.split(",")):
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


def build(scene):
    chars = []
    for c in scene.get("characters", []):
        outfit = block("outfits", c["outfit"]) if c.get("outfit") else ""
        chars.append([block("characters", c["character"]), outfit, c.get("action", "")])
    extras = [block("extras", e) for e in scene.get("extras", [])]
    location = block("locations", scene["location"]) if scene.get("location") else ""
    style = block("style", scene["style"]) if scene.get("style") else ""
    if scene.get("format", "tags") == "tags":
        quality = block("style", scene["quality"]) if scene.get("quality") else ""
        body = [scene.get("shot", "")] + [", ".join(x for x in c if x) for c in chars] \
            + extras + [location, scene.get("action", "")]
        # lead (subject count, rating) first, style + quality last; legacy scenes (no lead/quality) keep style first
        if scene.get("lead") or quality:
            parts = [scene.get("lead", "")] + body + [style, quality]
        else:
            parts = [style] + body
        positive = ", ".join(dedupe(parts))
    else:  # natural language: one sentence per element, in reading order
        def sentence(s):
            return s.strip().rstrip(".") + "." if s and s.strip() else ""
        sents = [sentence(scene.get("shot", ""))]
        sents += [" ".join(sentence(x) for x in c) for c in chars]
        sents += [sentence(e) for e in extras]
        sents += [sentence(location), sentence(scene.get("action", "")), sentence(style)]
        positive = " ".join(s for s in sents if s)
    negative = block("negative", scene["negative"]) if scene.get("negative") else ""
    return positive, negative, scene.get("motion", "")


def est_tokens(text):
    """Heuristic CLIP token estimate (no tokenizer installed): words*1.2 + commas."""
    import re
    words = re.findall(r"[A-Za-z0-9]+", text)
    return round(len(words) * 1.2 + text.count(","))


def lint(scene, positive):
    warns = []
    tags = {t.strip().lower() for t in positive.split(",")}
    if "1boy" in tags and ("2boys" in tags or "multiple boys" in tags):
        warns.append("1boy conflicts with 2boys/multiple boys")
    if "1girl" in tags and ("2girls" in tags or "multiple girls" in tags):
        warns.append("1girl conflicts with 2girls/multiple girls")
    n = est_tokens(positive)
    if n > 225:
        warns.append(f"positive ~{n} tokens > 225 (more than 3 CLIP chunks)")
    return n, warns


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    src = Path(args[0])
    if not src.exists():
        src = SCENES / (args[0] if args[0].endswith(".json") else args[0] + ".json")
    out_dir = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "workspace/prompts/built"
    scene = json.loads(src.read_text(encoding="utf-8"))
    positive, negative, motion = build(scene)
    n, warns = lint(scene, positive)
    print(f"[{src.stem}] positive ~{n} tokens (chunks of 75), tags={len(positive.split(','))}; warnings: {warns or 'none'}", file=sys.stderr)
    text = f"POSITIVE:\n{positive}\n\nNEGATIVE:\n{negative}\n" + (f"\nMOTION:\n{motion}\n" if motion else "")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{src.stem}.txt").write_text(text, encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps({"positive": positive, "negative": negative, "motion": motion}, ensure_ascii=False))
    else:
        print(text)
