#!/bin/bash
# Download the pinned model files into a ComfyUI models/ folder and verify sha256 + size. Nothing here is redistributed by this repo:
# the files come straight from Hugging Face. By downloading the DINOv3 file you accept the Meta DINOv3 licence (see README).
#   scripts/fetch_models.sh /path/to/ComfyUI/models [--check]      (--check: only verify what is already there)
set -u
M=${1:?usage: fetch_models.sh <ComfyUI/models dir> [--check]}; CHECK=${2:-}
# subdir | file | bytes | sha256 | url
while IFS='|' read -r sub file size sha url; do
  [ -z "$file" ] && continue
  dst="$M/$sub/$file"; mkdir -p "$M/$sub"
  if [ ! -f "$dst" ]; then
    [ "$CHECK" = "--check" ] && { echo "MISSING $sub/$file"; continue; }
    curl -fL --retry 3 -o "$dst" "$url" || { echo "DOWNLOAD FAILED $url"; continue; }
  fi
  got=$(sha256sum "$dst" | cut -d' ' -f1)
  [ "$got" = "$sha" ] && echo "OK       $sub/$file" || echo "BAD SHA  $sub/$file (got $got)"
done <<'LIST'
diffusion_models|pixal3d_int8_convrot.safetensors|5584555824|4621eac3b715484f79303c7152af641fe0b2b14f4d0e3d394fd6922d00f955ec|https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/diffusion_models/pixal3d_int8_convrot.safetensors
diffusion_models|trellis_2_int8_convrot.safetensors|5253048192|d01952ad137213f6a868f86b6b877026276f84af5eec23069217475a0bad3a31|https://huggingface.co/Comfy-Org/TRELLIS.2/resolve/main/diffusion_models/trellis_2_int8_convrot.safetensors
clip_vision|dino_v3_L_naf_fp32.safetensors|1215214176|4ad2ec4e0879a5b5b04cd97325cc37da954a7b6edca5170b86510f17f2b2290f|https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/clip_vision/dino_v3_L_naf_fp32.safetensors
vae|trellis_2_shape_vae_bf16.safetensors|1095844024|de0cb4949a76c59ee5c091a995a69bcc8c51d5aeda939f0c641a50d2a72341f4|https://huggingface.co/Comfy-Org/TRELLIS.2/resolve/main/vae/trellis_2_shape_vae_bf16.safetensors
vae|trellis_2_texture_vae_bf16.safetensors|948461364|714e5ebf094a610e12a8e3b5175c18a62f37f6ea4218acb6073644456b73ab0e|https://huggingface.co/Comfy-Org/TRELLIS.2/resolve/main/vae/trellis_2_texture_vae_bf16.safetensors
geometry_estimation|moge_2_vitl_normal_fp16.safetensors|661859924|cb1a692d03235671e959e81360d7b4d9f44aefadb1f852d6ca6aa17799d5e31f|https://huggingface.co/Comfy-Org/MoGe/resolve/main/geometry_estimation/moge_2_vitl_normal_fp16.safetensors
background_removal|birefnet.safetensors|444473596|9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154|https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors
LIST
