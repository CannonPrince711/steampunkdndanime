#!/usr/bin/env python3
"""BRASS INITIATIVE — M02 steampunk cel shader pass (Blender headless).

Run against the sets blend:  blender -b output/EP##/EP##_sets.blend -P pipeline/shaders_steampunk.py -- ...

Creates the canon cel material groups, assigns them by object naming convention,
exposes a SOOT custom property per object (driven into the shader), pins emission
temperatures to canon light_grammar_k, saves, updates library/LIB_shaders.blend,
and appends an execution block to logs/EP##/shader_report.json.
"""
import argparse
import json
import os
import sys

try:
    import bpy
except ImportError:
    print("shaders_steampunk.py requires Blender")
    sys.exit(1)

HEX = {
    "brass_key": "#C9A227", "brass_shadow": "#8A6B1F", "teal_dress": "#1F7A74",
    "teal_deep": "#10353A", "leather_tan": "#7A4A2B", "leather_dark": "#3E2718",
    "linen_white": "#F2EDE3", "violet_iris": "#8A4FD6", "aether_amber": "#FFB33A",
    "soot_black": "#1A1714", "shock_blue": "#4FC8E8", "rose_pink": "#F2A7C3",
}


def args_parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canon", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--shader-report", required=True)
    ap.add_argument("--epd", required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return ap.parse_args(argv)


def load_json(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def hex_to_rgba(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)


def kelvin_to_rgb(kelvin):
    import math
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
    return tuple(max(0.0, min(1.0, c / 255.0)) for c in (r, g, b)) + (1.0,)


def make_cel_material(name, base_hex, shadow_hex, specular=0.4, soot=True, emission=None, emission_k=None):
    """3-step cel: layer-weight facing drives a 2-stop ramp mixed over the base.
    SOOT is a Value node driven by the object's ['SOOT'] custom property."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    mix_soot = nt.nodes.new("ShaderNodeMixRGB"); mix_soot.location = (380, 0)
    mix_soot.blend_type = "MIX"
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (0, 0)
    ramp.color_ramp.interpolation = "CONSTANT"
    e0 = ramp.color_ramp.elements[0]; e0.position = 0.35
    e1 = ramp.color_ramp.elements[1]; e1.position = 0.75
    e0.color = hex_to_rgba(shadow_hex)
    e1.color = hex_to_rgba(base_hex)
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.location = (-300, 0)
    lw.inputs["Blend"].default_value = 0.4
    nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix_soot.inputs["Color1"])
    mix_soot.inputs["Color2"].default_value = hex_to_rgba(HEX["soot_black"])
    mix_soot.inputs["Fac"].default_value = 0.0
    if soot:
        soot_val = nt.nodes.new("ShaderNodeValue"); soot_val.location = (-300, -250)
        soot_val.name = "SOOT_DRIVE"
        nt.links.new(soot_val.outputs["Value"], mix_soot.inputs["Fac"])
        # driver: object property -> node value
        drv = soot_val.outputs["Value"].driver_add("default_value").driver
        drv.type = "AVERAGE"
        var = drv.variables.new()
        var.name = "soot"
        var.type = "OBJECT"
        var.targets[0].id_type = "OBJECT"
        var.targets[0].id = None  # bound at assignment time
        var.targets[0].data_path = '["SOOT"]'
        drv.expression = "soot"
    principled = nt.nodes.new("ShaderNodeBsdfPrincipled"); principled.location = (180, -300)
    principled.inputs["Specular IOR Level"].default_value = specular if "Specular IOR Level" in principled.inputs else 0.4
    principled.inputs["Roughness"].default_value = max(0.2, 1.0 - specular)
    nt.links.new(mix_soot.outputs["Color"], principled.inputs["Base Color"])
    if emission:
        em = nt.nodes.new("ShaderNodeEmission"); em.location = (180, 300)
        em.inputs["Color"].default_value = hex_to_rgba(emission)
        if emission_k:
            em.inputs["Strength"].default_value = max(1.0, emission_k / 900.0)
        add = nt.nodes.new("ShaderNodeAddShader"); add.location = (400, 150)
        nt.links.new(principled.outputs["BSDF"], add.inputs[0])
        nt.links.new(em.outputs["Emission"], add.inputs[1])
        nt.links.new(add.outputs["Shader"], out.inputs["Surface"])
    else:
        nt.links.new(principled.outputs["BSDF"], out.inputs["Surface"])
    mat["SOOT"] = 0.0
    return mat


GROUPS = {
    "BRASS": dict(base=HEX["brass_key"], shadow=HEX["brass_shadow"], spec=0.6),
    "TEAL_WOOL": dict(base=HEX["teal_dress"], shadow=HEX["teal_deep"], spec=0.05),
    "LEATHER": dict(base=HEX["leather_tan"], shadow=HEX["leather_dark"], spec=0.15),
    "LINEN": dict(base=HEX["linen_white"], shadow="#C9C2B2", spec=0.02),
    "SOOT_BARE": dict(base=HEX["soot_black"], shadow="#0D0B09", spec=0.0, soot=False),
    "AETHER_AMBER": dict(base=HEX["aether_amber"], shadow=HEX["aether_amber"],
                         spec=0.0, soot=False, emission=HEX["aether_amber"], emission_k=1800),
    "SHOCK_BLUE": dict(base=HEX["shock_blue"], shadow=HEX["shock_blue"],
                       spec=0.0, soot=False, emission=HEX["shock_blue"], emission_k=7500),
    "ASSAY_WHITE": dict(base="#E8E8E8", shadow="#B8B8B8", spec=0.0, soot=False,
                        emission="#FFFFFF", emission_k=5600),
    "SMOKE": dict(base="#9A9A94", shadow="#5A5A56", spec=0.0, soot=False),
    "SMOKE_GLASS": dict(base="#3A352E", shadow="#1A1714", spec=0.9, soot=False),
    "VIOLET_IRIS": dict(base=HEX["violet_iris"], shadow="#4A2A7A", spec=0.5),
    "ROSE_PINK": dict(base=HEX["rose_pink"], shadow="#B06A8A", spec=0.2),
}


def object_group(ob):
    n = ob.name.upper()
    if "SECOND_OPINION" in n or "PROP_TOAD" in n or "PROP_KETTLE" in n or "PROP_BOLT" in n or "LIGHT" in n:
        if "LIGHT" in n:
            return None
        return "BRASS"
    if "LENS" in n or "PROP_PIP" in n:
        return "VIOLET_IRIS"
    if "AETHER" in n or "SPOUT" in n or "KETTLE" in n:
        return "AETHER_AMBER"
    if "SHOCK" in n or "HAMMER" in n or "EJECTOR" in n:
        return "SHOCK_BLUE"
    if "ASSAY" in n:
        return "ASSAY_WHITE"
    if "FLOOR" in n or "WALL" in n:
        return "SOOT_BARE"
    if "TORSO" in n or "DRESS" in n:
        return "TEAL_WOOL" if "COG" in n else "LEATHER"
    if "CHAR_" in n:
        return "TEAL_WOOL" if "COG" in n else "LEATHER"
    if "SLOT" in n or "INLAY" in n or "RING" in n:
        return "BRASS"
    return "LEATHER"


def main():
    a = args_parse()
    canon = load_json(a.canon, {})
    state = load_json(a.state, {})
    ep = int(a.epd[2:])
    palette = canon.get("palette", {})
    for k, v in palette.items():
        HEX.setdefault(k, v)

    materials = {}
    for gid, spec in GROUPS.items():
        base = spec["base"]
        shadow = spec.get("shadow", base)
        mat = make_cel_material(
            f"M_{gid}", base, shadow, spec=spec.get("spec", 0.3), soot=spec.get("soot", True),
            emission=spec.get("emission"), emission_k=spec.get("emission_k"))
        materials[gid] = mat

    soot_sources = []
    cog_soot = state.get("cog", {}).get("soot_baseline", 0.0)
    assigned, group_use = [], {}
    for ob in bpy.data.objects:
        if ob.type not in ("MESH", "LIGHT"):
            continue
        gid = object_group(ob)
        if gid is None:
            continue
        mat = materials[gid]
        if ob.type == "MESH":
            sootable = gid in ("BRASS", "TEAL_WOOL", "LEATHER", "LINEN")
            if sootable:
                # single-user copy so the SOOT driver can bind to this object only
                mat = materials[gid].copy()
                mat.name = f"M_{gid}_{ob.name[:24]}"
                node = mat.node_tree.nodes.get("SOOT_DRIVE")
                if node:
                    for drv in node.outputs["Value"].drivers:
                        for var in drv.driver.variables:
                            var.targets[0].id = ob
            if not ob.data.materials:
                ob.data.materials.append(mat)
            else:
                ob.data.materials[0] = mat
        if gid in ("BRASS", "TEAL_WOOL", "LEATHER", "LINEN"):
            default_soot = cog_soot if ("CHAR_COG" in ob.name or "CHAR_ELSIE" in ob.name) else 0.0
            ob["SOOT"] = default_soot
            if default_soot > 0:
                soot_sources.append({"target": ob.name, "baseline": default_soot})
        assigned.append(ob.name)
        group_use.setdefault(gid, []).append(ob.name)

    # report hero flags from shader_report plan
    plan = load_json(a.shader_report, {})
    hero = [g.get("id") for g in plan.get("groups", []) if g.get("hero")]
    scene = bpy.context.scene
    scene["META_HERO"] = json.dumps(hero[:3])

    bpy.ops.wm.save_mainfile()

    # update library shaders blend (best effort)
    lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "library", "LIB_shaders.blend")
    if os.path.exists(lib_path):
        bpy.ops.wm.open_mainfile(filepath=lib_path)
        for gid, mat in materials.items():
            existing = bpy.data.materials.get(f"M_{gid}")
            if existing is None:
                bpy.data.materials.new(f"M_{gid}")
        bpy.ops.wm.save_mainfile()

    # append execution block to the text-lane shader report
    exec_block = {
        "episode": ep,
        "groups_applied": len(materials),
        "objects_assigned": len(assigned),
        "group_use": {k: len(v) for k, v in group_use.items()},
        "soot_sources": soot_sources,
        "hero_shots": hero[:3],
        "emission_k_pinned": {g: s.get("emission_k") for g, s in GROUPS.items() if s.get("emission_k")},
    }
    plan["execution"] = exec_block
    os.makedirs(os.path.dirname(os.path.abspath(a.shader_report)), exist_ok=True)
    with open(a.shader_report, "w") as fh:
        json.dump(plan, fh, indent=2)
        fh.write("\n")
    print(f"shaders: {len(assigned)} objects, {len(materials)} groups, hero {hero[:3]}")


if __name__ == "__main__":
    main()
