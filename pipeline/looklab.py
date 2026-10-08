#!/usr/bin/env python3
"""BRASS INITIATIVE — M03 rig & lookdev (Blender headless).

Run against the sets blend:  blender -b output/EP##/EP##_sets.blend -P pipeline/looklab.py -- ...

Rigs every character (armature + viseme shape keys), gives contraptions a CONDITION
damage shape key driven from series_state.json, rigs Second Opinion with a reload
action at the state's reload_frames, places one canon-lens camera and canon-temperature
lights per breakdown scene, and saves EP##_lookdev.blend.
"""
import argparse
import json
import math
import os
import sys

try:
    import bpy
except ImportError:
    print("looklab.py requires Blender")
    sys.exit(1)

from mathutils import Vector


def args_parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canon", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--lookdev-report", required=True)
    ap.add_argument("--breakdown", required=True)
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


def find_members(prefix):
    return [ob for ob in bpy.data.objects if ob.name.startswith(prefix)]


def build_armature(root, height_m, name):
    arm_data = bpy.data.armatures.new(f"ARM_{name}")
    arm = bpy.data.objects.new(f"ARM_{name}", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    h = height_m
    leg_h, torso_h = h * 0.42, h * 0.38

    def bone(nm, head, tail, parent=None):
        b = eb.new(nm)
        b.head, b.tail = Vector(head), Vector(tail)
        if parent:
            b.parent = parent
            b.use_connect = False
        return b

    pelvis = bone("pelvis", (0, 0, leg_h * 0.97), (0, 0, leg_h * 1.02))
    spine1 = bone("spine.01", (0, 0, leg_h * 1.02), (0, 0, leg_h + torso_h * 0.35), pelvis)
    spine2 = bone("spine.02", (0, 0, leg_h + torso_h * 0.35), (0, 0, leg_h + torso_h * 0.7), spine1)
    spine3 = bone("spine.03", (0, 0, leg_h + torso_h * 0.7), (0, 0, leg_h + torso_h), spine2)
    neck = bone("neck", (0, 0, leg_h + torso_h), (0, 0, leg_h + torso_h + 0.04), spine3)
    head = bone("head", (0, 0, leg_h + torso_h + 0.04), (0, 0, h), neck)
    for side, sx in (("L", -1), ("R", 1)):
        shoulder = bone(f"shoulder.{side}", (sx * 0.06, 0, leg_h + torso_h * 0.92),
                        (sx * 0.16, 0, leg_h + torso_h * 0.92), spine3)
        upper = bone(f"upper_arm.{side}", (sx * 0.16, 0, leg_h + torso_h * 0.92),
                     (sx * 0.18, 0, leg_h + torso_h * 0.45), shoulder)
        lower = bone(f"lower_arm.{side}", (sx * 0.18, 0, leg_h + torso_h * 0.45),
                     (sx * 0.19, 0, leg_h + 0.08), upper)
        hand = bone(f"hand.{side}", (sx * 0.19, 0, leg_h + 0.08),
                    (sx * 0.20, 0, leg_h * 0.02), lower)
        hip = bone(f"thigh.{side}", (sx * 0.045, 0, leg_h * 0.95),
                   (sx * 0.045, 0, leg_h * 0.5), pelvis)
        shin = bone(f"shin.{side}", (sx * 0.045, 0, leg_h * 0.5),
                    (sx * 0.045, 0, leg_h * 0.06), hip)
        foot = bone(f"foot.{side}", (sx * 0.045, 0, leg_h * 0.06),
                    (sx * 0.045, 0.09, leg_h * 0.02), shin)
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def add_viseme_keys(ob):
    """Jaw/mouth shape keys on any head mesh so lipsync always has targets."""
    if not ob.data.shape_keys:
        ob.shape_key_add(name="Basis")
        for key, (axis, amt) in {
            "V_JAW": (Vector((0, 0, -1)), 0.06),
            "V_MOUTH_OPEN": (Vector((0, 0, -0.5)), 0.035),
            "V_MOUTH_WIDE": (Vector((1, 0, 0)), 0.02),
            "V_BROW_UP": (Vector((0, 0, 1)), 0.012),
            "V_BROW_DOWN": (Vector((0, 0, -1)), 0.012),
        }.items():
            sk = ob.shape_key_add(name=key, from_mix=False)
            for v in sk.data:
                v.co += axis * amt
    return True


def add_condition_key(members, condition):
    """One DAMAGE shape key across the contraption's meshes, set from state."""
    for ob in members:
        if ob.type != "MESH" or not ob.data:
            continue
        if not ob.data.shape_keys:
            ob.shape_key_add(name="Basis")
        if "DAMAGE" not in (ob.data.shape_keys.key_blocks.keys() if ob.data.shape_keys else []):
            sk = ob.data.shape_key_add(name="DAMAGE", from_mix=False)
            for v in sk.data:
                n = ob.data.vertices[v.index].normal
                v.co += n * (1.0 - condition) * 0.04
        kb = ob.data.shape_keys.key_blocks["DAMAGE"]
        kb.value = (1.0 - condition) * 0.6
        ob["CONDITION"] = condition


def rig_pistol(prefix, reload_frames):
    """Break-action + cylinder reload action, keyed at the state's frame count."""
    parts = {p: find_root(f"{prefix}_PART_{p}") for p in
             ("FRAME", "BARREL", "CYLINDER_BLOCK", "EJECTOR_ROD", "HAMMER", "GRIP", "BRASS_INLAY")}
    cyl = parts.get("CYLINDER_BLOCK")
    hammer = parts.get("HAMMER")
    grip = parts.get("GRIP")
    if cyl is None:
        return None
    act = bpy.data.actions.new(f"ACT_RELOAD_{prefix}")
    cyl.animation_data_create()
    cyl.animation_data.action = act
    f1, f2, f3, f4 = 1, int(reload_frames * 0.3), int(reload_frames * 0.6), reload_frames
    # break open: barrel pivot — approximated by rotating barrel+block as a unit around grip
    for ob, d in ((cyl, -0.5), (hammer, 0.9)):
        if ob is None:
            continue
        ob.animation_data_create()
        ob.animation_data.action = act
        for fr, val in ((f1, 0.0), (f2, d), (f3, d), (f4, 0.0)):
            ob.rotation_euler[1] = val
            ob.keyframe_insert("rotation_euler", index=1, frame=fr)
    for fr, val in ((f1, 0.0), (f2, -math.radians(30)), (f3, -math.radians(120)), (f4, -math.radians(180))):
        cyl.rotation_euler[1] = val
        cyl.keyframe_insert("rotation_euler", index=1, frame=fr)
    return act


def kelvin_to_rgb(kelvin):
    t = kelvin / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        r = 329.698727446 * (t - 60) ** -0.1332047592
        g = 288.1221695283 * (t - 60) ** -0.0755148492
    if t >= 66:
        b = 255.0
    elif t <= 19:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10) - 305.0447927307
    return tuple(max(0.0, min(1.0, c / 255.0)) for c in (r, g, b))


def main():
    a = args_parse()
    canon = load_json(a.canon, {})
    state = load_json(a.state, {})
    breakdown = load_json(a.breakdown, {"scenes": []})
    ep = int(a.epd[2:])
    heights = {"CHAR_ROSE": 1.72, "CHAR_BARRIK": 1.98, "CHAR_TEV": 1.76,
               "CHAR_COG": 1.58, "CHAR_ILVA": 1.65}

    rigs, damage_applied = [], []
    for cname, h in heights.items():
        prefix = f"EP{ep:02d}_{cname}"
        root = find_root(prefix)
        if root is None:
            continue
        members = find_members(prefix)
        mesh = next((m for m in members if m.type == "MESH" and "HEAD" in m.name), None)
        if mesh:
            add_viseme_keys(mesh)
        arm = build_armature(root, h, cname)
        bpy.ops.object.select_all(action="DESELECT")
        for m in members:
            if m.type == "MESH":
                m.select_set(True)
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        try:
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        except RuntimeError:
            for m in members:
                if m.type == "MESH":
                    m.parent = arm
        cog_soot = state.get("cog", {}).get("soot_baseline", 0.0) if cname == "CHAR_COG" else 0.0
        for m in members:
            if m.type == "MESH":
                m["SOOT"] = cog_soot
        # belt tokens track available cylinders
        if cname == "CHAR_COG":
            avail = state.get("pistol", {}).get("cylinders_available", [])
            order = ["SHOCK", "SMOKE", "GRAPNEL", "OVERCHARGE"]
            for i, cid in enumerate(order):
                tok = find_root(f"{prefix}_SLOT_TOKEN_{i}")
                if tok:
                    tok.hide_render = cid not in avail
                    tok.hide_viewport = cid not in avail
        rigs.append({"id": cname, "bones": len(arm.data.bones),
                     "shape_keys": len(mesh.data.shape_keys.key_blocks) if (mesh and mesh.data.shape_keys) else 0,
                     "soot_props": ([m.name for m in members if m.type == "MESH" and m.get("SOOT", 0) > 0]) or ["none (baseline 0)"]})

    # contraption condition keys
    contraptions = {c.get("id"): c for c in state.get("contraptions", [])}
    for ct in state.get("contraptions", []):
        cid = ct.get("id", "")
        members = [ob for ob in find_members(f"EP{ep:02d}_PROP_{cid}") if ob.name.startswith(f"EP{ep:02d}_PROP_{cid}")]
        if not members:
            continue
        cond = float(ct.get("condition", 1.0))
        add_condition_key(members, cond)
        damage_applied.append({"target": cid, "state_entry": f"condition={cond}",
                               "visual": "DAMAGE shape key" if cond < 1.0 else "none"})

    # pistol reload action
    reload_frames = int(state.get("pistol", {}).get("reload_frames", 26))
    act = rig_pistol(f"EP{ep:02d}_PROP_SECOND_OPINION", reload_frames)
    part_swaps = [str(d) for d in state.get("pistol", {}).get("damage", [])]

    # per-scene cameras and lights
    lookdev_frames = []
    for sc in breakdown.get("scenes", []):
        sid = sc.get("scene_id", "S00")
        lens = float(sc.get("lens_mm", 35))
        temp = float(sc.get("light_k", 2700))
        cam_data = bpy.data.cameras.new(f"CAM_{sid}")
        cam_data.lens = lens
        cam = bpy.data.objects.new(f"CAM_{sid}", cam_data)
        cam.location = (0, 4.5, 1.4)
        cam.rotation_euler = (math.radians(87), 0, 0)
        bpy.context.scene.collection.objects.link(cam)
        key = bpy.data.lights.new(f"KEY_{sid}", type="AREA")
        key.energy = 150
        key.color = kelvin_to_rgb(temp)
        key.size = 1.2
        key_ob = bpy.data.objects.new(f"KEY_{sid}", key)
        key_ob.location = (2.5, 2.5, 3.2)
        bpy.context.scene.collection.objects.link(key_ob)
        lookdev_frames.append({"scene_id": sid, "frame": int(sc.get("start_frame", 1)),
                               "light_k": temp, "lens_mm": lens,
                               "notes": "money frame at scene start"})

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = int(breakdown.get("total_frames", 31680))
    scene.render.fps = int(canon.get("series", {}).get("fps", 24))
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.frame_set(1)
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.output))

    plan = load_json(a.lookdev_report, {})
    plan["execution"] = {
        "episode": ep,
        "rigs": rigs,
        "damage_applied": damage_applied,
        "pistol": {"reload_frames": reload_frames, "part_swaps": part_swaps,
                   "reload_action": act.name if act else None},
        "lookdev_frames": lookdev_frames,
        "saved_to": os.path.relpath(a.output, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.lookdev_report)), exist_ok=True)
    with open(a.lookdev_report, "w") as fh:
        json.dump(plan, fh, indent=2)
        fh.write("\n")
    print(f"lookdev: {len(rigs)} rigs, {len(lookdev_frames)} cameras, reload {reload_frames}f")


if __name__ == "__main__":
    main()
