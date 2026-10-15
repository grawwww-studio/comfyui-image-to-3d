#!/bin/bash
# frames from `render.sh ... turn` -> H.264 mp4 (needs ffmpeg).   scripts/turntable_mp4.sh <frames_dir> <out.mp4> [fps=24]
ffmpeg -v error -y -framerate "${3:-24}" -i "$1/turn_%03d.png" -c:v libx264 -crf 18 -pix_fmt yuv420p -movflags +faststart "$2"
