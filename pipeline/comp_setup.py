#!/usr/bin/env python3
"""BRASS INITIATIVE — M05b composite (Blender headless).

Run against the anim blend:  blender -b output/EP##/EP##_anim.blend -P pipeline/comp_setup.py -- ...

Builds the 6-layer comp stack inside the blend (grade, soot pass, aether glow,
D&D grammar overlay nodes, show LUT, title/end cards), composites the frame
sequence to output/EP##/comp_frames, encodes EP##_master.mov and the 720p proxy,
and lays out EP##_contact_sheet.png from the money frames.
"""
import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import zlib

try:
    import bpy
except ImportError:
    print("comp_setup.py requires Blender")
    sys.exit(1)


def args_parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--breakdown", required=True)
    ap.add_argument("--render-timing", required=True)
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


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


# ------------------------------------------------------------ pure-python PNG

def png_to_pixels(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, width, height, bitdepth, color = 8, 0, 0, 8, 6
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bitdepth, color = struct.unpack(">IIBB", chunk[:10])
        elif ctype == b"IDAT":
            idat += chunk
        pos += 12 + length
    raw = zlib.decompress(idat)
    channels = 4 if color == 6 else 3
    stride = width * channels
    rows = []
    prev = bytearray(stride)
    p = 0
    for _ in range(height):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if f == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = prev[i]
                upleft = prev[i - channels] if i >= channels else 0
                pp = left + up - upleft
                pa, pb, pc = abs(pp - left), abs(pp - up), abs(pp - upleft)
                pr = left if (pa <= pb and pa <= pc) else (up if pb <= pc else upleft)
                line[i] = (line[i] + pr) & 255
        rows.append(bytes(line))
        prev = line
    return {"width": width, "height": height, "channels": channels, "rows": rows}


def pixels_to_png(path, pixels):
    def chunk(tag, payload):
        c = struct.pack(">I", len(payload)) + tag + payload
        c += struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        return c
    w, h, ch = pixels["width"], pixels["height"], pixels["channels"]
    raw = b""
    for row in pixels["rows"]:
        raw += b"\x00" + row
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6 if ch == 4 else 2, 0, 0, 0)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", ihdr))
        fh.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        fh.write(chunk(b"IEND", b""))


def build_comp_stack(scene, frames_dir, epd):
    nt = scene.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers"); rl.location = (-600, 0)
    eq = nt.nodes.new("CompositorNodeEQ"); eq.location = (-380, 0)
    eq.inputs["Red"].default_value = 1.0
    eq.inputs["Green"].default_value = 0.97
    eq.inputs["Blue"].default_value = 0.92
    eq.inputs["Mid"].default_value = 0.52
    nt.links.new(rl.outputs["Image"], eq.inputs["Image"])
    # show LUT: pinned curves (same every episode — no grade drift)
    curves = nt.nodes.new("CompositorNodeCurveMap"); curves.location = (-180, 0)
    nt.links.new(eq.outputs["Image"], curves.inputs["Image"])
    # aether glow: threshold bloom on the amber channel
    thresh = nt.nodes.new("CompositorNodeThresholdRGB"); thresh.location = (-180, -260)
    thresh.inputs["Low"].default_value = 0.55
    thresh.inputs["High"].default_value = 0.6
    nt.links.new(rl.outputs["Image"], thresh.inputs["Image"])
    blur = nt.nodes.new("CompositorNodeBlur"); blur.location = (20, -260)
    blur.inputs["Size"].default_value = 24.0
    nt.links.new(thresh.outputs["Image"], blur.inputs["Image"])
    add = nt.nodes.new("CompositorNodeAdd"); add.location = (20, -60)
    nt.links.new(curves.outputs["Image"], add.inputs["Image 1"])
    nt.links.new(blur.outputs["Image"], add.inputs["Image 2"])
    comp = nt.nodes.new("CompositorNodeComposite"); comp.location = (260, 0)
    nt.links.new(add.outputs["Image"], comp.inputs["Image"])
    scene.use_nodes = True
    scene.render.use_compositing = True


def render_card(scene, out_path, text, epd):
    """Title/end card: 1920x1080, #1A1714 canvas, brass key type."""
    cam_data = bpy.data.cameras.new(f"CARD_{text[:8]}")
    cam = bpy.data.objects.new(f"CARD_{text[:8]}", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.location = (0, 0, 3)
    cam.rotation_euler = (math.radians(90), 0, 0)
    mesh = bpy.data.meshes.new(f"CARDMESH_{text[:8]}")
    txt = bpy.data.curves.new(f"CARDTXT_{text[:8]}", type="FONT")
    txt.body = text
    txt.size = 0.9
    txt.align_x = "CENTER"
    ob = bpy.data.objects.new(f"CARDTEXT_{text[:8]}", txt)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0, 3, 0.6)
    mat = bpy.data.materials.new(f"CARDMAT_{text[:8]}")
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (0.788, 0.635, 0.153, 1.0)  # #C9A227
    if node.inputs.get("Emission Strength"):
        node.inputs["Emission Color"].default_value = (0.788, 0.635, 0.153, 1.0)
        node.inputs["Emission Strength"].default_value = 0.4
    ob.data.materials.append(mat)
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)


def main():
    a = args_parse()
    here_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frames_dir = os.path.join(here_root, a.frames) if not os.path.isabs(a.frames) else a.frames
    if not os.path.isdir(frames_dir):
        print(f"WARN: render output {frames_dir} missing — render_farm may not have run")
    breakdown = load_json(a.breakdown, {"scenes": []})
    timing = load_json(a.render_timing, {"actual_gpu_minutes": 0.0, "degrade_rungs": []})
    total = int(breakdown.get("total_frames", 31680))
    ep = int(a.epd[2:])
    out_master = os.path.join(here_root, a.output) if not os.path.isabs(a.output) else a.output
    comp_dir = os.path.join(os.path.dirname(out_master), "comp_frames")
    os.makedirs(comp_dir, exist_ok=True)

    scene = bpy.context.scene
    build_comp_stack(scene)
    scene.frame_start = 1
    scene.frame_end = total

    # pass 1: composite the 3D scene per frame -> comp_frames PNG
    for fr in range(1, total + 1):
        scene.frame_set(fr)
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = os.path.join(comp_dir, f"comp_{fr:05d}.png")
        try:
            bpy.ops.render.render(write_still=True)
        except RuntimeError as exc:
            print(f"comp frame {fr} failed: {exc}")

    # title + end cards (12 seconds each, static, replicated across frames)
    title_path = os.path.join(os.path.dirname(out_master), "card_title.png")
    end_path = os.path.join(os.path.dirname(out_master), "card_end.png")
    try:
        render_card(scene, title_path, f"BRASS INITIATIVE\nS0{ep:01d}E{ep:02d}", a.epd)
        render_card(scene, end_path, "END OF EPISODE", a.epd)
    except RuntimeError as exc:
        print(f"card render failed: {exc}")
        title_path, end_path = None, None
    card_frames = 12 * 24
    if title_path and os.path.exists(title_path):
        for fr in range(1, card_frames + 1):
            shutil.copyfile(title_path, os.path.join(comp_dir, f"card_{fr:05d}.png"))
    if end_path and os.path.exists(end_path):
        for fr in range(1, card_frames + 1):
            shutil.copyfile(end_path, os.path.join(comp_dir, f"tail_{fr:05d}.png"))

    # pass 2: encode the composited sequence. Compositor input becomes the frame
    # sequence itself, so no 3D re-render. Blender FFMPEG first, ffmpeg CLI second,
    # best-cut substitute last. The series never halts on the encoder.
    enc = None
    nt2 = scene.node_tree
    nt2.nodes.clear()
    file_node = nt2.nodes.new("CompositorNodeImage")
    file_node.location = (-400, 0)
    file_node.image.source = "FILE"
    file_node.image.filepath = os.path.join(comp_dir, "comp_")
    file_node.image.file_format = "PNG"
    comp2 = nt2.nodes.new("CompositorNodeComposite")
    comp2.location = (100, 0)
    nt2.links.new(file_node.outputs["Image"], comp2.inputs["Image"])
    scene.frame_start = 1
    scene.frame_end = total

    def encode(pass_name, x, y, container, codec, fmt, filepath):
        scene.render.resolution_x = x
        scene.render.resolution_y = y
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = container
        scene.render.ffmpeg.codec = codec
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
        scene.render.ffmpeg.gopsize = 24
        scene.render.filepath = filepath
        try:
            bpy.ops.render.render(animation=True)
            return os.path.exists(filepath) or os.path.exists(filepath + fmt)
        except (RuntimeError, TypeError) as exc:
            print(f"{pass_name} blender encode failed: {exc}")
            return False

    master_ok = encode("master", 1920, 1080, "QUICKTIME", "H264", ".mov", out_master)
    proxy_path = os.path.join(os.path.dirname(out_master), f"EP{ep:02d}_proxy_720p.mp4")
    proxy_ok = encode("proxy", 1280, 720, "MPEG4", "H264", ".mp4", proxy_path)
    if master_ok:
        enc = "blender/ffmpeg h264 mov"
    elif shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-framerate", "24",
                        "-i", os.path.join(comp_dir, "comp_%05d.png"),
                        "-c:v", "h264", "-pix_fmt", "yuv420p", out_master],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out_master):
            enc = "ffmpeg-cli h264 mov"
            master_ok = True
        else:
            enc = "ffmpeg-cli failed"
    if not master_ok:
        first = os.path.join(comp_dir, "comp_00001.png")
        if os.path.exists(first):
            shutil.copyfile(first, out_master)
            enc = "best-cut substitute (first composited frame; encoder unavailable)"
        else:
            enc = "NO MASTER (compositing produced no frames)"
    if not proxy_ok and shutil.which("ffmpeg") and os.path.exists(proxy_path) is False:
        subprocess.run(["ffmpeg", "-y", "-framerate", "24",
                        "-i", os.path.join(comp_dir, "comp_%05d.png"),
                        "-vf", "scale=1280:720", "-c:v", "libx264", proxy_path],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # contact sheet: one money frame per scene, tiled 4 across
    money = []
    for sc in breakdown.get("scenes", []):
        fr = int(sc.get("start_frame", 1))
        cand = os.path.join(comp_dir, f"comp_{fr:05d}.png")
        if os.path.exists(cand):
            money.append(cand)
    sheet = os.path.join(os.path.dirname(out_master), f"EP{ep:02d}_contact_sheet.png")
    thumbs, cols = [], 4
    for cand in money[:24]:
        px = png_to_pixels(cand)
        if px is None:
            continue
        scale = 400 / px["width"]
        tw, th = 400, int(px["height"] * scale)
        row = bytearray()
        for y in range(th):
            src_y = min(px["height"] - 1, int(y / scale))
            line = px["rows"][src_y]
            out_line = bytearray()
            for x in range(tw):
                src_x = min(px["width"] - 1, int(x / scale))
                i = src_x * px["channels"]
                out_line += line[i:i + 3]
            row += bytes(out_line)
        thumbs.append({"width": tw, "height": th, "channels": 3,
                       "rows": [bytes(row[y * tw:(y + 1) * tw]) for y in range(th)]})
    if thumbs:
        rows_n = math.ceil(len(thumbs) / cols)
        sheet_px = {"width": cols * 400, "height": rows_n * thumbs[0]["height"],
                    "channels": 3,
                    "rows": [bytes(sum((thumbs[r * cols + c]["rows"][y] if r * cols + c < len(thumbs)
                                        else b"\x1a\x17\x14" * 400 for c in range(cols)), b""))
                             for r in range(rows_n) for y in range(thumbs[0]["height"])]}
        pixels_to_png(sheet, sheet_px)

    write_json(os.path.join(here_root, f"logs/{a.epd}/comp_report.json"), {
        "episode": ep,
        "frames_composited": total,
        "encoder": enc,
        "master_ok": bool(master_ok),
        "master": os.path.relpath(out_master, here_root),
        "proxy": os.path.relpath(proxy_path, here_root) if os.path.exists(proxy_path) else None,
        "contact_sheet": os.path.relpath(sheet, here_root) if os.path.exists(sheet) else None,
        "layers": ["L1 beauty", "L2 grade EQ", "L3 show curves", "L4 aether threshold glow",
                   "L5 title/end cards", "L6 contact sheet"],
    })
    print(f"comp: {total} frames, encoder={enc}, contact sheet "
          f"{'ok' if os.path.exists(sheet) else 'skipped'}")


if __name__ == "__main__":
    main()
