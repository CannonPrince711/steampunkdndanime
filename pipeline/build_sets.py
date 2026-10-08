#!/usr/bin/env python3
"""BRASS INITIATIVE — M01 set build (Blender headless).

Reads the text-lane build report and brief, builds (or delta-links) the episode
world, applies accumulated pistol damage as visible part states, and saves
output/EP##/EP##_sets.blend. New assets are written back to the library blends.

All geometry is procedural and deterministic: seeded from episode number per
canon. Dimensions come from logs/EP##/build_report.json (cm), fallback to the
brief, fallback to canon sizes. Missing inputs are synthesized, never blocking.
"""
import argparse
import json
import os
import random
import sys

try:
    import bpy
except ImportError:
    print("build_sets.py requires Blender (run via: blender -b -P pipeline/build_sets.py)")
    sys.exit(1)

import math

PALETTE = {}
CORE_CONTRAPTIONS = {"TOAD", "PIP", "KETTLE", "BRACE"}


def args_parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--brief", required=True)
    ap.add_argument("--breakdown", default=None)
    ap.add_argument("--build-report", default=None)
    ap.add_argument("--delta-mode", default="auto")
    ap.add_argument("--output", required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return ap.parse_args(argv)


def load_json(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def cm(v):
    return float(v) / 100.0


def add_text_block(name, payload):
    tb = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    tb.clear()
    tb.write(json.dumps(payload))
    return tb


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.armatures):
        for b in list(block):
            if b.users == 0:
                block.remove(b)


def new_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def add_box(col, name, size_cm, loc_m=(0, 0, 0), rotate=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc_m)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (cm(size_cm[0]), cm(size_cm[1]), cm(size_cm[2]))
    ob.rotation_euler = (math.radians(rotate[0]), math.radians(rotate[1]), math.radians(rotate[2]))
    bpy.ops.object.transform_apply(scale=True)
    for c in ob.users_collection:
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob


def add_cyl(col, name, r_cm, depth_cm, loc_m=(0, 0, 0), rotate=(0, 0, 0), verts=24):
    bpy.ops.mesh.primitive_cylinder_add(radius=cm(r_cm), depth=cm(depth_cm), vertices=verts, location=loc_m)
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_euler = (math.radians(rotate[0]), math.radians(rotate[1]), math.radians(rotate[2]))
    for c in ob.users_collection:
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob


def add_sphere(col, name, r_cm, loc_m=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=cm(r_cm), location=loc_m, segments=24, ring_count=16)
    ob = bpy.context.active_object
    ob.name = name
    for c in ob.users_collection:
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob


def add_area_light(col, name, kelvin, loc_m, size_m=0.5, power=80.0, color=None):
    light_data = bpy.data.lights.new(name, type="AREA")
    light_data.energy = power
    light_data.size = size_m
    if color:
        light_data.color = color
    else:
        light_data.color = kelvin_to_rgb(kelvin)
    ob = bpy.data.objects.new(name, light_data)
    ob.location = loc_m
    col.objects.link(ob)
    return ob


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


# ------------------------------------------------------------------ assets

def build_pistol(col, name, pistol_state):
    """310 mm break-action. Named parts for damage swaps."""
    parts = {}
    L = 0.310
    x0 = -L / 2
    parts["frame"] = add_box(col, f"{name}_PART_FRAME", [18, 6, 9], (x0 + 0.09, 0, 0.02))
    parts["barrel"] = add_cyl(col, f"{name}_PART_BARREL", 1.6, 14, (x0 + 0.22, 0, 0.02), rotate=(0, 90, 0))
    parts["cylinder_block"] = add_cyl(col, f"{name}_PART_CYLINDER_BLOCK", 3.2, 5, (x0 + 0.115, 0, 0.02), rotate=(0, 90, 0), verts=12)
    parts["ejector_rod"] = add_cyl(col, f"{name}_PART_EJECTOR_ROD", 0.7, 9, (x0 + 0.115, 0, 0.055), rotate=(0, 90, 0), verts=8)
    parts["hammer"] = add_box(col, f"{name}_PART_HAMMER", [3.5, 3.5, 7], (x0 + 0.045, 0, 0.045))
    parts["grip"] = add_box(col, f"{name}_PART_GRIP", [6.5, 4.5, 16], (x0 + 0.045, 0, -0.055), rotate=(-18, 0, 0))
    parts["brass_inlay"] = add_box(col, f"{name}_PART_BRASS_INLAY", [5.5, 4.7, 1.2], (x0 + 0.05, 0, -0.045), rotate=(-18, 0, 0))

    root = bpy.data.objects.new(name, None)
    col.objects.link(root)
    for part_name, ob in parts.items():
        ob.parent = root

    # apply accumulated damage from state
    for dmg in pistol_state.get("damage", []):
        target = None
        d = str(dmg).lower()
        for part_name in parts:
            if part_name.split("_")[-1] in d or part_name in d:
                target = parts[part_name]
                break
        if target is None:
            continue
        if "warp" in d or "bend" in d or "break" in d:
            target.rotation_euler = (math.radians(22), target.rotation_euler[1], target.rotation_euler[2])
        elif "missing" in d or "lost" in d:
            target.hide_render = True
            target.hide_viewport = True
    for mod in pistol_state.get("modifications", []):
        m = str(mod).lower()
        if "brace" in m:
            add_box(col, f"{name}_MOD_HAND_BRACE", [4, 8, 4], (-L / 2 + 0.02, 0, 0.0))
        elif "inlay" in m:
            parts["brass_inlay"].scale = (1.0, 1.25, 1.0)
        elif "file" in m:
            parts["cylinder_block"].scale = (0.96, 0.96, 1.0)
    return root


def build_contraption(col, name, spec):
    """One real motion each, deterministic shape per id."""
    size = cm(spec.get("size_cm", 30))
    root = bpy.data.objects.new(name, None)
    col.objects.link(root)
    if name.endswith("TOAD") or "TOAD" in name:
        body = add_cyl(col, f"{name}_BODY", 14, 42, (0, 0, 0.18), rotate=(0, 90, 0))
        head = add_sphere(col, f"{name}_HEAD", 9, (0.30, 0, 0.18))
        piston = add_cyl(col, f"{name}_PISTON", 4, 18, (0.42, 0, 0.18), rotate=(0, 90, 0), verts=12)
    elif name.endswith("PIP") or "PIP" in name:
        body = add_box(col, f"{name}_BODY", [12, 10, 14], (0, 0, 0.07))
        lens = add_cyl(col, f"{name}_LENS", 4, 3, (0, 0.06, 0.09), rotate=(90, 0, 0), verts=16)
    elif name.endswith("KETTLE") or "KETTLE" in name:
        body = add_cyl(col, f"{name}_BODY", 16, 34, (0, 0, 0.17))
        spout = add_cyl(col, f"{name}_SPOUT", 3.5, 12, (0.14, 0, 0.26), rotate=(0, 65, 0), verts=12)
        valve = add_cyl(col, f"{name}_VALVE", 2.5, 6, (0, 0, 0.36), verts=8)
    elif name.endswith("BRACE") or "BRACE" in name:
        ring = add_cyl(col, f"{name}_RING", 10, 2.5, (0, 0, 0.15), rotate=(90, 0, 0), verts=24)
        pin = add_cyl(col, f"{name}_PIN", 1.5, 24, (0, 0, 0.15), rotate=(0, 0, 0), verts=8)
    else:
        body = add_box(col, f"{name}_BODY", [24, 18, 18], (0, 0, 0.09))
        rotor = add_cyl(col, f"{name}_ROTOR", 5, 8, (0, 0.10, 0.14), rotate=(90, 0, 0), verts=12)
        parts = [ob for ob in col.objects if ob.name.startswith(name)]
        head, piston = None, None
    for ob in col.objects:
        if ob.name.startswith(name) and ob.parent is None:
            ob.parent = root
    return root


def build_character(col, name, height_cm, hair_hex=None):
    h = cm(height_cm)
    root = bpy.data.objects.new(name, None)
    col.objects.link(root)
    head_r = h / 13.0
    torso_h = h * 0.38
    leg_h = h * 0.42
    torso = add_cyl(col, f"{name}_TORSO", max(8.0, h * 0.16), torso_h * 100, (0, 0, leg_h + torso_h / 2), verts=16)
    head = add_sphere(col, f"{name}_HEAD", head_r * 100, (0, 0, leg_h + torso_h + head_r))
    hip = add_cyl(col, f"{name}_HIP", max(7.0, h * 0.14), 10, (0, 0, leg_h * 0.97), verts=16)
    for side, sx in (("L", -1), ("R", 1)):
        arm = add_cyl(col, f"{name}_ARM_{side}", 2.6, torso_h * 80, (sx * (h * 0.22 + 0.03), 0, leg_h + torso_h / 2), verts=10)
        hand = add_sphere(col, f"{name}_HAND_{side}", 2.8, (sx * (h * 0.22 + 0.03), 0, leg_h + 0.02))
        leg = add_cyl(col, f"{name}_LEG_{side}", 3.4, leg_h * 85, (sx * 0.045, 0, leg_h * 0.45), verts=10)
        foot = add_box(col, f"{name}_FOOT_{side}", [7, 12, 4], (sx * 0.045, 0.02, 0.02))
    parts = [ob for ob in col.objects if ob.name.startswith(name)]
    for ob in parts:
        ob.parent = root
    if "COG" in name.upper() or "ELSIE" in name.upper():
        for i in range(4):
            tok = add_cyl(col, f"{name}_SLOT_TOKEN_{i}", 1.2, 0.8,
                          (-0.06 + i * 0.032, 0.07, leg_h * 0.85), rotate=(90, 0, 0), verts=8)
            tok.parent = root
    return root


def build_set(col, set_spec, ep_seed):
    bbox = set_spec.get("bbox_cm", [1200, 800, 450])
    w, d, hgt = cm(bbox[0]), cm(bbox[1]), cm(bbox[2])
    rng = random.Random(ep_seed)
    floor = add_box(col, f"{set_spec['name']}_FLOOR", [bbox[0], bbox[1], 6], (0, 0, -0.03))
    for i, (wx, wy, rot) in enumerate([(-w / 2, 0, 90), (w / 2, 0, 90), (0, -d / 2, 0)]):
        if rng.random() < 0.9:
            add_box(col, f"{set_spec['name']}_WALL_{i}", [d if rot else bbox[0], 12, hgt * 100],
                    (wx, wy, hgt / 2), rotate=(0, 0, rot))
    fixtures = set_spec.get("light_fixtures", [{"temp_k": 2700, "n": 3}])
    for fi, fix in enumerate(fixtures):
        temp = fix.get("temp_k", 2700)
        for k in range(fix.get("n", 2)):
            lx = rng.uniform(-w / 2 + 0.5, w / 2 - 0.5)
            ly = rng.uniform(-d / 2 + 0.5, d / 2 - 0.5)
            add_area_light(col, f"{set_spec['name']}_LIGHT_{fi}_{k}", temp,
                           (lx, ly, hgt - 0.3), power=fix.get("power_w", 80))
    return floor


def delta_link_library(lib_path, wanted_collections):
    """Link (not append) collections from an existing library blend."""
    if not os.path.exists(lib_path):
        return []
    linked = []
    with bpy.data.libraries.load(lib_path, link=True) as (src, dst):
        available = [c for c in src.collections if c in wanted_collections]
        dst.collections = available
        for coll in dst.collections:
            if coll is not None:
                bpy.context.scene.collection.children.link(coll)
                linked.append(coll.name)
    return linked


def push_to_library(ep, episode_blend_abs):
    """Append this episode's named collections into the library blends (best effort)."""
    kind_prefix = {
        "LIB_sets.blend": "EP{ep:02d}_SET",
        "LIB_props.blend": "EP{ep:02d}_PROP",
        "LIB_characters.blend": "EP{ep:02d}_CHAR",
    }
    for fname, prefix in kind_prefix.items():
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "library", fname)
        if not os.path.exists(path):
            continue
        wanted = [c.name for c in bpy.data.collections if c.name.startswith(prefix.format(ep=ep))]
        if not wanted:
            continue
        bpy.ops.wm.open_mainfile(filepath=path)
        added = []
        with bpy.data.libraries.load(episode_blend_abs, link=False) as (src, dst):
            names = [n for n in wanted if n in src.collections]
            dst.collections = names
            for coll in dst.collections:
                if coll is not None:
                    lib_coll = bpy.data.collections.new(f"{coll.name}_LIB")
                    for ob in coll.objects:
                        lib_coll.objects.link(ob)
                    bpy.context.scene.collection.children.link(lib_coll)
                    added.append(coll.name)
        bpy.ops.wm.save_mainfile()
        if added:
            print(f"library updated: {fname} (+{len(added)})")


def main():
    a = args_parse()
    state = load_json(a.state, {})
    brief = load_json(a.brief, {})
    build_report = load_json(a.build_report, {}) if a.build_report else {}
    ep = int(brief.get("episode_number", state.get("next_episode", 1)))
    ep_seed = 1000 + ep

    clear_scene()
    reused, built = [], []

    delta = a.delta_mode != "off" and (a.delta_mode == "auto" or ep > 1)
    if delta:
        known_sets = set(state.get("assets", {}).get("sets_built", []))
        known_props = set(state.get("assets", {}).get("props_built", []))
        known_chars = set(state.get("assets", {}).get("characters_built", []))
        lib_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "library")
        reused += delta_link_library(os.path.join(lib_root, "LIB_sets.blend"), list(known_sets))
        reused += delta_link_library(os.path.join(lib_root, "LIB_props.blend"), list(known_props))
        reused += delta_link_library(os.path.join(lib_root, "LIB_characters.blend"), list(known_chars))

    pistol_state = state.get("pistol", {})

    # sets
    sets = build_report.get("sets", [])
    if not sets:
        loc = brief.get("primary_location", "BRASSMOUTH")
        sets = [{"id": f"SET_{loc.upper().replace(' ', '_')[:24]}", "name": loc,
                 "bbox_cm": [1200, 800, 450],
                 "light_fixtures": [{"temp_k": 2700, "n": 3}]}]
    for s in sets:
        if delta and s.get("name") in set(reused):
            continue
        col = new_collection(f"EP{ep:02d}_{s['name'].upper().replace(' ', '_')[:24]}")
        build_set(col, s, ep_seed)
        built.append(s.get("name", s.get("id")))

    # props: pistol + contraptions
    prop_col = new_collection(f"EP{ep:02d}_PROPS")
    build_pistol(prop_col, f"EP{ep:02d}_PROP_SECOND_OPINION", pistol_state)
    built.append("Second Opinion")
    contraptions = state.get("contraptions", [])
    brief_ct = brief.get("new_contraption")
    if brief_ct and brief_ct.get("id"):
        contraptions.append({"id": brief_ct["id"], "status": "intact", "condition": 1.0})
    seen = set()
    for ct in contraptions:
        cid = ct.get("id", "")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        spec = dict(brief_ct) if (brief_ct and brief_ct.get("id") == cid) else {}
        spec.setdefault("size_cm", 30)
        if delta and f"PROP_{cid}" in set(reused):
            continue
        build_contraption(prop_col, f"EP{ep:02d}_PROP_{cid}", spec)
        built.append(cid)

    # characters
    char_col = new_collection(f"EP{ep:02d}_CHARACTERS")
    party = {
        "Rose": 172, "Barrik": 198, "Tev": 176, "Cog": 158, "Ilva": 165,
    }
    for cname, h in party.items():
        if delta and f"CHAR_{cname}" in set(reused):
            continue
        build_character(char_col, f"EP{ep:02d}_CHAR_{cname}", h)
        built.append(cname)

    scene = bpy.context.scene
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.fps = 24
    add_text_block("META_BUILD", {
        "episode": ep,
        "mode": "delta" if (delta and reused) else "full",
        "reused": reused,
        "built": built,
        "delta_stats": {
            "assets_reused": len(reused),
            "assets_built": len(built),
            "percent_reused": round(100.0 * len(reused) / max(1, len(reused) + len(built)), 1),
        },
    })
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    episode_blend_abs = os.path.abspath(a.output)
    bpy.ops.wm.save_as_mainfile(filepath=episode_blend_abs)
    print(f"saved {a.output} (reused {len(reused)}, built {len(built)})")
    if not (delta and reused):
        push_to_library(ep, episode_blend_abs)


if __name__ == "__main__":
    main()
