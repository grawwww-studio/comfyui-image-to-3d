#!/bin/bash
# Stills + wireframe + UV layout for every run folder under a directory, the way the case-study renders were made.
#   scripts/render_all.sh <runs_dir> [front_az=0] [level=0]
# (the two numbers were chosen by eye per run with `render.sh ... test`; see README, "Camera-space meshes")
set -e
HERE=$(dirname "$(realpath "$0")")
for d in "$1"/*/; do d=${d%/}
  hi=$(ls "$d"/*_hi_*.glb | head -1); lo=$(ls "$d"/*_lo_*.glb | head -1)
  "$HERE/render.sh" "$hi" "$d/stills" stills "${2:-0}" 1080 64 "${3:-0}"
  "$HERE/render.sh" "$lo" "$d/wire" wire "${2:-0}" 1080 16 "${3:-0}"
  "$HERE/render.sh" "$hi" "$d/uv" uv
done
