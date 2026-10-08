#!/usr/bin/env python3
"""BRASS INITIATIVE — M05a render farm (pure python, drives Blender headless).

Estimates GPU minutes from a 20-frame probe, applies the degrade ladder if the
episode would bust the budget, renders the frame sequence, and writes
logs/EP##/render_timing.json for the comp and QA stages. Never aborts for budget:
it ships the rung it can afford.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def args_parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--breakdown", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epd", required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return ap.parse_args(argv)


def load_json(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


def blender_bin():
    for cand in ("blender", "Blender"):
        if shutil.which(cand):
            return cand
    sys.exit("blender not found on PATH — render farm needs the Blender box")


def render_range(blender, blend, out_dir, start, end, settings_path):
    os.makedirs(out_dir, exist_ok=True)
    cmd = [blender, "-b", blend,
           "--python-expr",
           ("import json,os,bpy;"
            "s=json.load(open(os.environ['BLR_SETTINGS']));"
            "sc=bpy.context.scene;"
            "sc.render.resolution_x=s['x'];sc.render.resolution_y=s['y'];"
            "sc.render.fps=s['fps'];"
            "eng=[e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items];"
            "sc.render.engine='BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in eng else "
            "('BLENDER_EEVEE' if 'BLENDER_EEVEE' in eng else 'CYCLES');"
            "try: sc.eevee.taa_render_samples=s['samples']; except Exception: pass;"
            "try: sc.cycles.samples=s['samples']; except Exception: pass")]
    env = dict(os.environ, BLR_SETTINGS=settings_path)
    for fr in range(start, end + 1):
        out = os.path.join(out_dir, f"frame_{fr:05d}.png")
        if os.path.exists(out):
            continue
        subprocess.run(cmd + ["-o", os.path.join(out_dir, "frame_####"), "-f", str(fr)],
                       env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(os.path.join(out_dir, "frame_0000.png")):
            os.replace(os.path.join(out_dir, "frame_0000.png"), out)


def main():
    a = args_parse()
    blend = os.path.join(ROOT, a.blend) if not os.path.isabs(a.blend) else a.blend
    breakdown = load_json(a.breakdown, {})
    state = load_json(a.state, {})
    total = int(breakdown.get("total_frames", 31680))
    fps = int(breakdown.get("fps", 24))
    cap = float(state.get("budget", {}).get("gpu_minutes_cap_per_episode", 900))
    out = os.path.join(ROOT, a.out) if not os.path.isabs(a.out) else a.out
    timing_path = os.path.join(ROOT, f"logs/{a.epd}/render_timing.json")

    base = {"x": 1920, "y": 1080, "fps": fps, "samples": 64}
    rungs = []

    # probe: 20 frames at base settings to estimate GPU minutes
    settings_path = os.path.join(out, "render_settings.json")
    write_json(settings_path, base)
    t0 = time.time()
    render_range(shutil.which("blender") or "blender", blend, out, 1, 20, settings_path)
    probe_min = (time.time() - t0) / 60.0
    est_total = probe_min * total / 20.0
    print(f"probe: 20 frames in {probe_min:.2f} min -> est {est_total:.0f} min for {total} frames (cap {cap:.0f})")

    rung = 0
    while est_total > cap and rung < 4:
        rung += 1
        if rung == 1:
            base["samples"] = 32
            rungs.append("R1: samples 64 -> 32")
        elif rung == 2:
            base["samples"] = 24
            rungs.append("R2: hero Cycles shots downgraded (sample floor 24)")
        elif rung == 3:
            base["x"], base["y"] = 1280, 720
            rungs.append("R3: resolution 1920x1080 -> 1280x720 (master upscaled in comp)")
        elif rung == 4:
            base["samples"] = 16
            rungs.append("R4: sample floor 16")
        write_json(settings_path, base)
        t0 = time.time()
        render_range(shutil.which("blender") or "blender", blend, out, 21, 30, settings_path)
        probe_min = (time.time() - t0) / 60.0
        est_total = probe_min * total / 10.0
    if est_total > cap:
        rungs.append("WARN: budget still projected over cap — shipping at floor rung, episode not aborted")

    # full render at the chosen rung
    t0 = time.time()
    render_range(shutil.which("blender") or "blender", blend, out, 1, total, settings_path)
    gpu_min = (time.time() - t0) / 60.0

    write_json(timing_path, {
        "episode": int(a.epd[2:]),
        "frames": total,
        "fps": fps,
        "est_gpu_minutes": round(est_total, 1),
        "actual_gpu_minutes": round(gpu_min, 2),
        "cap": cap,
        "degrade_rungs": rungs,
        "final_settings": base,
        "probe_min_20frames": round(probe_min, 3),
    })
    print(f"render complete: {total} frames, {gpu_min:.1f} gpu min, rungs {rungs or 'none'}")


if __name__ == "__main__":
    main()
