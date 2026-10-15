# Third-party notices

The MIT licence in `LICENSE` covers only code written for this repository (`scripts/`, the README and results text).
It does not cover the items below.

## ComfyUI workflow template (workflows/)
`workflows/*.json` were rebuilt by hand from the template `3d_pixal3d_trellis2_image_to_model` that ships with ComfyUI 0.37.0
in the Python package `comfyui-workflow-templates` 0.11.66 (the template JSON lives in `comfyui-workflow-templates-json` 0.1.92).
Checked inside a ComfyUI 0.37.0 container on 2026-10-15 (`pip show`, `dist-info/licenses/LICENSE`): the package is declared
**MIT, "Copyright (c) 2023-present Comfy Org"**. Anything derived from that template stays under that MIT notice, which is:

    MIT License
    Copyright (c) 2023-present Comfy Org
    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
    documentation files (the "Software"), to deal in the Software without restriction ... (standard MIT text;
    the full text is in the package's LICENSE file)

Node settings, node wiring and defaults (CFG override, RescaleCFG, sampler names, remesh/bake settings) come from that template;
what differs (upsample 1024, 2048 textures, 150k and 50k decimation branches, seeds) is described in the README.

## Models (not included, not redistributed)
| Model | Licence | Source |
|---|---|---|
| Pixal3D | MIT, TencentARC | https://github.com/TencentARC/Pixal3D , https://huggingface.co/TencentARC/Pixal3D |
| TRELLIS.2-4B | MIT, Microsoft | https://github.com/microsoft/TRELLIS.2 , https://huggingface.co/microsoft/TRELLIS.2-4B |
| BiRefNet | MIT | https://huggingface.co/ZhengPeng7/BiRefNet |
| MoGe-2 | MIT (code and model card; DINOv2 code inside MoGe is Apache-2.0, Meta) | https://github.com/microsoft/MoGe , https://huggingface.co/Ruicheng/moge-2-vitl |
| DINOv3 ViT-L/16 (+ NAF upsampler) | **Meta DINOv3 licence** (not MIT) | https://ai.meta.com/resources/models-and-libraries/dinov3-license |

The ComfyUI-native repacks (int8 ConvRot Pixal3D and TRELLIS.2, VAEs, MoGe, BiRefNet, DINOv3+NAF) are published by Comfy-Org on
Hugging Face; `scripts/fetch_models.sh` downloads them from there.

**Built with DINOv3.** Both Pixal3D and TRELLIS.2 condition on DINOv3 features. The DINOv3 weights are **not** in this repo and
must not be added to it: Meta's licence lets you use them, but redistribution requires including the licence and the
"Built with DINOv3" notice. Obtain them yourself and read the licence at the link above. The Comfy-Org file
`dino_v3_L_naf_fp32.safetensors` does not say which DINOv3 checkpoint it contains; it has the structure of a DINOv3 ViT-L plus a
NAF block, and we treat it as DINOv3 under Meta's licence (byte identity with Meta's own release was not checked).
Do not use the Bria RMBG models as background remover for commercial work (RMBG-2.0 is CC BY-NC); this repo uses BiRefNet.

The Pixal3D release carries a non-binding "Responsible Use" notice (no non-consensual or sexualised likeness, minors, impersonation).
Please read it before using the model.

## Input photos (inputs/)
- `stool_met_c1670.jpg`: Stool, c.1670, The Metropolitan Museum of Art, Bequest of Irwin Untermyer, 1973 (1974.28.25). CC0 (Met Open Access).
  Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Stool_MET_DP159799.jpg
- `thonet14_borrillo.jpg`: Thonet No. 14 style chair, photo by Antonio Borrillo, CC0.
  Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Chair.JPG
  (on inspection it is a black tubular-metal chair with a cane-print seat, not an original bentwood one.)

## Other tools
Blender 4.5 (GPL, used as an external program; no Blender code is included). ComfyUI (GPL-3.0) is called over its HTTP API only.
