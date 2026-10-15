#!/bin/bash
# Render a generated GLB with a stock Blender 4.5 (headless).
#   scripts/render.sh <model.glb> <outdir> <mode> [front_az=0] [size=1080] [samples=64] [level=0] [frames=72]
# modes: stills (front, q34, side, rear, top) | turn (turntable frames, 360 deg) | wire (wireframe, use the 50k GLB) | uv (UV layout) | test
# front_az: rotates the model about the vertical axis until its "front" faces the camera (use `test` mode to find it).
# level:    pitch in degrees about X to stand up a camera-space mesh (Pixal3D output is tilted by the photo's camera pitch).
# Env: BLENDER=/path/to/blender (default: blender on PATH). To use a container instead, set BLENDER to a wrapper script.
set -e
GLB=$(realpath "$1"); OUT=$2; MODE=$3; shift 3
HERE=$(dirname "$(realpath "$0")")
"${BLENDER:-blender}" -b --factory-startup --python-exit-code 1 --python "$HERE/render_glb.py" -- "$GLB" "$(realpath -m "$OUT")" "$MODE" "${1:-0}" "${2:-1080}" "${3:-64}" "${4:-0}" "${5:-72}" | grep -E "DEVICE|RENDER_DONE|Error"
