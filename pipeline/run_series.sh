#!/usr/bin/env bash
# BRASS INITIATIVE — machine lane driver (Blender box).
#
# Usage:
#   bash pipeline/run_series.sh          # all machine stages for the current episode
#   bash pipeline/run_series.sh M01      # one stage: M01 sets | M02 shaders | M03 lookdev
#                                        #         M04 anim  | M05 render+comp+qa
#
# Each successful stage appends its id to logs/EP##/machine_done.json. That file is
# what the series runner (and the Claude Desktop loop) use to know the lane is done.
set -u

cd "$(dirname "$0")/.."

STAGE="${1:-all}"

if [ ! -f canon/series_state.json ]; then
  echo "ERROR: canon/series_state.json missing"
  exit 1
fi

EP=$(python3 -c "import json;print(json.load(open('canon/series_state.json'))['next_episode'])")
SE=$(python3 -c "import json;print(json.load(open('canon/series_state.json'))['season'])")
TAG=$(printf "S%02dE%02d" "$SE" "$EP")
EPD=$(printf "EP%02d" "$EP")

mkdir -p "output/$EPD/frames" "logs/$EPD" "canon/episodes/$EPD" "scripts/$EPD" "library"

mark_done() {
  python3 - "$EPD" "$1" <<'PYEOF'
import json, os, sys
epd, step = sys.argv[1], sys.argv[2]
path = f"logs/{epd}/machine_done.json"
done = []
if os.path.exists(path):
    try:
        done = json.load(open(path))
    except Exception:
        done = []
if step not in done:
    done.append(step)
    with open(path, "w") as fh:
        json.dump(done, fh, indent=2)
        fh.write("\n")
PYEOF
  echo "[$TAG] $1 marked done"
}

need_file() {
  if [ ! -f "$1" ]; then
    echo "[$TAG] BLOCKED: missing $1 (text lane output — run the matching agent in chat first)"
    exit 3
  fi
}

stage_M01() {
  need_file "logs/$EPD/build_report.json"
  need_file "canon/episodes/$EPD/brief.json"
  echo "[$TAG] building sets"
  blender -b -P pipeline/build_sets.py -- \
    --state canon/series_state.json \
    --brief "canon/episodes/$EPD/brief.json" \
    --breakdown "canon/episodes/$EPD/breakdown.json" \
    --build-report "logs/$EPD/build_report.json" \
    --delta-mode auto \
    --output "output/$EPD/${EPD}_sets.blend" || exit 1
  mark_done M01_sets
}

stage_M02() {
  need_file "output/$EPD/${EPD}_sets.blend"
  need_file "logs/$EPD/shader_report.json"
  echo "[$TAG] shaders"
  blender -b "output/$EPD/${EPD}_sets.blend" -P pipeline/shaders_steampunk.py -- \
    --canon canon/series_canon.json \
    --state canon/series_state.json \
    --shader-report "logs/$EPD/shader_report.json" \
    --epd "$EPD" || exit 1
  mark_done M02_shaders
}

stage_M03() {
  need_file "output/$EPD/${EPD}_sets.blend"
  need_file "logs/$EPD/lookdev_report.json"
  echo "[$TAG] lookdev"
  blender -b "output/$EPD/${EPD}_sets.blend" -P pipeline/looklab.py -- \
    --canon canon/series_canon.json \
    --state canon/series_state.json \
    --lookdev-report "logs/$EPD/lookdev_report.json" \
    --breakdown "canon/episodes/$EPD/breakdown.json" \
    --epd "$EPD" \
    --output "output/$EPD/${EPD}_lookdev.blend" || exit 1
  mark_done M03_lookdev
}

stage_M04() {
  need_file "output/$EPD/${EPD}_lookdev.blend"
  need_file "canon/episodes/$EPD/choreo.json"
  need_file "canon/episodes/$EPD/lipsync.json"
  need_file "canon/episodes/$EPD/breakdown.json"
  echo "[$TAG] animation"
  blender -b "output/$EPD/${EPD}_lookdev.blend" -P pipeline/animate_fx.py -- \
    --breakdown "canon/episodes/$EPD/breakdown.json" \
    --choreo "canon/episodes/$EPD/choreo.json" \
    --lipsync "canon/episodes/$EPD/lipsync.json" \
    --anim-report "logs/$EPD/anim_report.json" \
    --epd "$EPD" \
    --output "output/$EPD/${EPD}_anim.blend" || exit 1
  mark_done M04_anim
}

stage_M05() {
  need_file "output/$EPD/${EPD}_anim.blend"
  need_file "canon/episodes/$EPD/breakdown.json"
  echo "[$TAG] render"
  python3 pipeline/render_farm.py \
    --blend "output/$EPD/${EPD}_anim.blend" \
    --breakdown "canon/episodes/$EPD/breakdown.json" \
    --state canon/series_state.json \
    --out "output/$EPD/frames" \
    --epd "$EPD" || exit 1

  echo "[$TAG] comp"
  blender -b "output/$EPD/${EPD}_anim.blend" -P pipeline/comp_setup.py -- \
    --frames "output/$EPD/frames" \
    --breakdown "canon/episodes/$EPD/breakdown.json" \
    --render-timing "logs/$EPD/render_timing.json" \
    --epd "$EPD" \
    --output "output/$EPD/${EPD}_master.mov" || exit 1

  echo "[$TAG] qa"
  python3 pipeline/qa_audit.py \
    --breakdown "canon/episodes/$EPD/breakdown.json" \
    --frames "output/$EPD/frames" \
    --comp-frames "output/$EPD/comp_frames" \
    --render-timing "logs/$EPD/render_timing.json" \
    --epd "$EPD" \
    --report "logs/$EPD/production_report.json" || exit 1
  mark_done M05_render_comp_qa
}

case "$STAGE" in
  M01) stage_M01 ;;
  M02) stage_M02 ;;
  M03) stage_M03 ;;
  M04) stage_M04 ;;
  M05) stage_M05 ;;
  all) stage_M01; stage_M02; stage_M03; stage_M04; stage_M05 ;;
  *) echo "unknown stage: $STAGE (use M01..M05 or all)"; exit 1 ;;
esac

echo "[$TAG] done"
