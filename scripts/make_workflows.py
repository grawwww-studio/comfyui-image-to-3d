#!/usr/bin/env python3
"""Regenerate workflows/*.json from gen3d.graph(): API-format graph + UI-format workflow (drag into ComfyUI).
Needs a running ComfyUI (COMFY_URL, default http://127.0.0.1:8188) only to read /object_info for the UI layout.

  python3 scripts/make_workflows.py [--seed 777] [--image stool_met_c1670.jpg]
"""
import argparse, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen3d, api_to_ui  # noqa: E402

TITLES = {"1": "Input photo (copy it to ComfyUI/input)", "2": "BiRefNet (MIT) matte", "4": "Crop to object 1024",
          "5": "DINOv3-L + NAF (Meta DINOv3 licence)", "6": "MoGe-2 (MIT) FOV", "21": "1 Sparse structure (12 steps)",
          "24": "2 Shape 512 (20 steps)", "25": "Upsample: target resolution 1024", "26": "3 Shape at 1024 (12 steps)",
          "29": "4 Texture (12 steps, seed+1)", "33": "Remesh: high-poly reference for the bakes",
          "40": "HI LOD: decimate to 150k", "60": "LO LOD: decimate to 50k", "48": "Save GLB 150k", "68": "Save GLB 50k",
          "50": "UV atlas preview"}

ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, default=777); ap.add_argument("--image", default="stool_met_c1670.jpg")
a = ap.parse_args()
out = HERE.parent / "workflows"; out.mkdir(exist_ok=True)
for m in ("pixal3d", "trellis2"):
    g = gen3d.graph(m, a.image, a.seed, 1024, 2048, 150000, 50000, f"image-to-3d/{Path(a.image).stem}_{m}_s{a.seed}_r1024")
    (out / f"{m}_image_to_3d.api.json").write_text(json.dumps(g, indent=1))
    ui = api_to_ui.convert(g, {k: v for k, v in TITLES.items() if k in g})
    (out / f"{m}_image_to_3d.json").write_text(json.dumps(ui, indent=1))
    print(m, "nodes", len(ui["nodes"]), "links", len(ui["links"]))
