#!/usr/bin/env python3
"""BRASS INITIATIVE — M04 animation & FX (Blender headless).

Run against the lookdev blend:  blender -b output/EP##/EP##_lookdev.blend -P pipeline/animate_fx.py -- ...

Keys the full 31,680 frames: cameras on the breakdown lens grammar, bodies on the
choreo beat chains, mouths on the lipsync viseme tracks, and SOOT as step keys that
land and stay. Saves EP##_anim.blend and appends an execution block to the anim report.
"""
import argparse
import json
import math
import os
import sys

try:
    import bpy
except ImportError:
    print("animate_fx.py requires Blender")
    sys.exit(1)

VISEME_MAP = {
    "o": ("V_MOUTH_OPEN", 0.9), "b": ("V_MOUTH_OPEN", 0.3), "c": ("V_MOUTH_OPEN", 0.0),
    "e": ("V_MOUTH_OPEN", 0.4), "i": ("V_MOUTH_OPEN", 0.2), "u": ("V_MOUTH_OPEN", 0.6),
    " ": ("V_MOUTH_OPEN", 0.0), "w": ("V_MOUTH_WIDE", 0.6),
}
FPS = 24


def args_parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--breakdown", required=True)
    ap.add_argument("--choreo", required=True)
    ap.add_argument("--lipsync", required=True)
    ap.add_argument("--anim-report", required=True)
    ap.add_argument("--epd", required=True)
    ap.add_argument("--output", required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return ap.parse_args(argv)


def load_json(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def find_root(prefix):
    for ob in bpy.data.objects:
        if ob.name == prefix:
            return ob
    return None


def find_head(name_prefix):
    for ob in bpy.data.objects:
        if ob.name.startswith(name_prefix) and "HEAD" in ob.name and ob.type == "MESH":
            return ob
    return None


def key_soot(target_name, scene_id, frm, frm_to, soot_from, soot_to):
    """Soot lands and stays: a step, not a ramp."""
    ob = find_root(target_name)
    if ob is None:
        return False
    ob["SOOT"] = soot_from
    ob.keyframe_insert('["SOOT"]', frame=frm)
    ob["SOOT"] = soot_to
    ob.keyframe_insert('["SOOT"]', frame=frm_to)
    return True


def key_camera(sc, ep):
    cam = find_root(f"CAM_{sc.get('scene_id', 'S00')}")
    if cam is None:
        return
    s = int(sc.get("start_frame", 1))
    e = int(sc.get("end_frame", s + 24))
    lens = float(sc.get("lens_mm", 35))
    cam.data.lens = lens
    # dolly speed per lens grammar
    speeds = {24: 0.4, 35: 0.8, 50: 0.0, 85: 0.2, 135: 0.0}
    speed = speeds.get(round(lens), 0.4)
    travel = speed * (e - s) / FPS
    cam.location = (0, 4.5 + travel, 1.4)
    cam.keyframe_insert("location", frame=s)
    cam.location = (0, 4.5, 1.4 - travel * 0.3)
    cam.keyframe_insert("location", frame=e)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def key_beat(beat, fight, ep):
    """Move the named combatants for one library beat. Deterministic, meter-true."""
    bid = beat.get("beat_id", "")
    frm = int(beat.get("at_frame", fight.get("start_frame", 1)))
    frames = int(beat.get("frames", 12))
    chain = {b.get("beat_id"): b for b in fight.get("chain", [])}
    plan = FLOOR_PLANS.get(fight.get("scene_id", ""), {})
    movers = []
    if bid.startswith("FIRE_") or bid == "WINDUP_PISTOL":
        movers = ["COG"]
    elif bid in ("STRIKE_MELEE", "DODGE_STEP"):
        movers = list(plan.keys())[:2]
    elif bid in ("TOAD_PUNCH", "KETTLE_BREATH", "CINDER_PAT", "SNUFF_BLOW",
                 "BOLT_DRIVE", "CROWN_LIFT", "VIGIL_RAKE", "BRACE_LATCH", "MOTH_PROBE",
                 "DOCKLIGHT_FLARE", "PIP_SPOT", "ECHO_EYE"):
        movers = ["COG"]
    for who in movers:
        root = find_root(f"EP{ep:02d}_CHAR_{who.upper()}")
        if root is None:
            pos = plan.get(who.lower(), plan.get(who, None))
            if pos is None:
                continue
            root = find_root(f"EP{ep:02d}_CHAR_{who.upper()}")
        if root is None:
            continue
        if bid == "DODGE_STEP":
            dx, dy = 0.5, 0.0
        elif bid == "STRIKE_MELEE":
            dx, dy = 0.3, 0.0
        elif bid.startswith("FIRE_"):
            dx, dy = 0.1, 0.0
        else:
            dx, dy = 0.15, 0.0
        root.location.x = 0.0
        root.keyframe_insert("location", index=0, frame=frm)
        root.location.x = dx
        root.keyframe_insert("location", index=0, frame=frm + frames // 2)
        root.location.x = 0.0
        root.keyframe_insert("location", index=0, frame=frm + frames)
        if bid == "FIRE_SHOCK" or bid == "FIRE_OVERCHARGE":
            # soot burst target: the opposing combatant
            for other in plan:
                if other not in movers:
                    ob = find_root(f"EP{ep:02d}_CHAR_{other.upper()}")
                    if ob is not None:
                        cur = ob.get("SOOT", 0.0)
                        key_soot(f"EP{ep:02d}_CHAR_{other.upper()}", fight.get("scene_id", ""),
                                 frm + 4, frm + 5, cur, min(0.9, cur + 0.05))
    # soot persistence for the fight's listed accumulations
    for entry in fight.get("soot_persistence", []):
        target = entry.get("target", "")
        parts = target.split(".")
        who = parts[0].upper()
        ob = find_root(f"EP{ep:02d}_CHAR_{who}")
        if ob is None:
            continue
        ob["SOOT"] = min(0.9, float(entry.get("delta_pct", 4)) / 100.0)
        ob.keyframe_insert('["SOOT"]', frame=int(beat.get("at_frame", frm)) + 4)


def key_lipsync(line, ep):
    char = str(line.get("char", "")).upper()
    head = find_head(f"EP{ep:02d}_CHAR_{char}")
    if head is None or not head.data.shape_keys:
        return False
    s, e = int(line.get("start_frame", 1)), int(line.get("end_frame", 2))
    track = str(line.get("viseme_track", "cccc"))
    per = max(1, (e - s) // max(1, len(track)))
    for i, ch in enumerate(track):
        entry = VISEME_MAP.get(ch, VISEME_MAP["c"])
        key_name, val = entry
        kb = head.data.shape_keys.key_blocks.get(key_name)
        if kb is None:
            continue
        kb.value = val
        kb.keyframe_insert("value", frame=s + i * per)
    for kb in head.data.shape_keys.key_blocks:
        if kb.name.startswith("V_") and kb.name != "Basis":
            kb.value = 0.0
            kb.keyframe_insert("value", frame=e + 2)
    return True


FLOOR_PLANS = {}


def main():
    global FLOOR_PLANS
    a = args_parse()
    breakdown = load_json(a.breakdown, {"scenes": []})
    choreo = load_json(a.choreo, {"fights": [], "non_fight_motion": [], "reloads": []})
    lipsync = load_json(a.lipsync, {"lines": []})
    ep = int(a.epd[2:])

    FLOOR_PLANS = {fp.get("scene_id", ""): {p.get("who", "").lower(): p
                                            for p in fp.get("positions", [])}
                   for fp in choreo.get("floor_plans", [])}

    scene = bpy.context.scene
    total = int(breakdown.get("total_frames", 31680))
    scene.frame_start = 1
    scene.frame_end = total
    scene.render.fps = FPS

    beats_keyed, beats_missing = 0, []
    scenes_sorted = sorted(breakdown.get("scenes", []), key=lambda s: int(s.get("start_frame", 1)))
    for sc in scenes_sorted:
        key_camera(sc, ep)
        cam = find_root(f"CAM_{sc.get('scene_id', 'S00')}")
        if cam is not None:
            scene.camera = cam
            scene.keyframe_insert("camera", frame=int(sc.get("start_frame", 1)))

    for fight in choreo.get("fights", []):
        for beat in fight.get("chain", []):
            key_beat(beat, fight, ep)
            beats_keyed += 1
    for motion in choreo.get("non_fight_motion", []):
        root = find_root(f"EP{ep:02d}_PROP_{str(motion.get('subject', '')).upper()}")
        if root is None:
            beats_missing.append(f"non_fight_motion:{motion.get('subject')}")
            continue
        frm = int(motion.get("at_frame", 1))
        frames = int(motion.get("frames", 12))
        root.rotation_euler[2] = 0.0
        root.keyframe_insert("rotation_euler", index=2, frame=frm)
        root.rotation_euler[2] = math.radians(12)
        root.keyframe_insert("rotation_euler", index=2, frame=frm + frames // 2)
        root.rotation_euler[2] = 0.0
        root.keyframe_insert("rotation_euler", index=2, frame=frm + frames)
        beats_keyed += 1

    # reloads: trigger the pistol reload action at the right frame
    for rl in choreo.get("reloads", []):
        root = find_root(f"EP{ep:02d}_PROP_SECOND_OPINION")
        if root is None:
            beats_missing.append("reload:pistol missing")
            continue
        act = bpy.data.actions.get(f"ACT_RELOAD_PROP_SECOND_OPINION") or \
            bpy.data.actions.get("ACT_RELOAD_EP{0:02d}_PROP_SECOND_OPINION".format(ep))
        if act:
            root.animation_data_create()
            root.animation_data.action = act
            root.animation_data.action.frame_offset = int(rl.get("at_frame", 1)) - 1
        beats_keyed += 1

    lines_keyed = 0
    for line in lipsync.get("lines", []):
        if key_lipsync(line, ep):
            lines_keyed += 1

    # soot: every scene's start carries the accumulated value (lands and stays)
    for fight in choreo.get("fights", []):
        for entry in fight.get("soot_persistence", []):
            who = str(entry.get("target", "")).split(".")[0].upper()
            ob = find_root(f"EP{ep:02d}_CHAR_{who}")
            if ob is not None and "SOOT" not in ob.keys():
                ob["SOOT"] = min(0.9, float(entry.get("delta_pct", 4)) / 100.0)

    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.output))

    plan = load_json(a.anim_report, {})
    plan["execution"] = {
        "episode": ep,
        "total_frames": total,
        "beats_keyed": beats_keyed,
        "beats_missing": beats_missing,
        "dialogue_lines_keyed": lines_keyed,
        "saved_to": os.path.relpath(a.output, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.anim_report)), exist_ok=True)
    with open(a.anim_report, "w") as fh:
        json.dump(plan, fh, indent=2)
        fh.write("\n")
    print(f"anim: {beats_keyed} beats, {lines_keyed} lines keyed, {total} frames -> {a.output}")


if __name__ == "__main__":
    main()
