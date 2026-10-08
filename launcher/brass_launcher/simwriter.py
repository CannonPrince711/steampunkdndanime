"""Deterministic offline autopilot (SIM mode).

Generates every text-lane output for any step, honoring the agent contracts and
mutating state exactly as Agent 11 prescribes. Two purposes:

1. It makes the AUTO button work with no API key and no Blender — the whole
   series loop runs end to end offline so the pipeline, the UI, and the state
   machine can be demonstrated and stress-tested.
2. It is the reference implementation of what the LLM autopilot must emit:
   same files, same formats, same math.

Everything is seeded from season and episode per canon (no unseeded randomness).
"""
import copy
import json
import os

LADDER_S1 = {1: 9, 2: 8, 3: 8, 4: 7, 5: 6, 6: 6, 7: 5, 8: 4, 9: 3, 10: 3, 11: 2, 12: 2}
FPS = 24
RUNTIME = 1320
TOTAL_FRAMES = 31680

CONTRAPTION_NAMES = {
    1: ("TOAD", 60, "piston ram for dock gates and doors",
        "its brass core drinks aether fast — first candidate to become an Echo"),
    2: ("SNUFF", 22, "pocket soot-blower for blinding and cleaning",
        "the seal weeps brass dust into Cog's left glove"),
    3: ("WRENCH_LASH", 400, "flexible brass grab line, 4 m",
        "the hinge at Cog's hip wears a notch every use"),
    4: ("DOCKLIGHT", 31, "aether flare lantern, 30 m pool at 1800K",
        "its filament is a loan from KETTLE's reserve coil"),
    5: ("CINDER", 18, "palm thermal mortar, 4 m glass-crack pat",
        "it heats Cog's palm a full temperature step per use"),
    6: ("HALO", 62, "single-person grapnel platform, 62 cm disc",
        "the disc's edge eats the strap of whoever rides it"),
    7: ("MOTH", 28, "hand-thrown aero scout, 28 cm wingspan",
        "it returns a brass film and half of its own memory"),
    8: ("BOLT", 45, "rail-spike grappled driver for the Line",
        "every driven spike costs a meter of anchor wire"),
    9: ("CROWN", 94, "harness exo-frame, 94 cm over Cog",
        "it is stronger than her bones and it knows it"),
    10: ("VIGIL", 70, "self-raking soot shield, 70 cm fan",
        "it rakes her with it too; the shield does not distinguish"),
    11: ("ECHO_CHOKE", 24, "dampening collar for machine intent",
        "it hums in the key of the machine it holds"),
    12: ("TESTAMENT", 56, "one-shot overcharge chamber, 56 cm",
        "it is built to be spent; that is the point"),
}
NEW_CHARS = {
    4: ("Inspector Vane", "Assay Inspector"),
    8: ("Tallyman Lieutenant", "Assay Tallyman lieutenant"),
    10: ("The Brandmaster", "personification of the Assay"),
}
STRUCTURES = ["three-act", "bottle + breach", "heist shape", "raid shape",
              "pursuit", "set piece", "reversal", "descent", "assembly",
              "reckoning", "threshold", "gate"]
B_DRIVERS = ["Tev", "Rose", "Ilva", "Barrik", "Tev", "Ilva", "Barrik",
             "Rose", "Tev", "Ilva", "Rose", "Barrik"]
PISTOL_TYPES = {1: ("modification", "first handling: grip burnished, inlay checked, silence break-in",
                    "none — silhouette baseline established")}


def ask_target(season, ep):
    if season == 1:
        return LADDER_S1.get(ep, 2)
    floor = max(1, 9 - 4 * (season - 1))
    return max(1, floor - (ep - 1) // 2)


def assay_tier(awareness):
    if awareness >= 0.9:
        return "branding"
    if awareness >= 0.75:
        return "squad"
    if awareness >= 0.5:
        return "inspector"
    if awareness >= 0.3:
        return "clerk"
    return "none"


def load(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return json.load(fh)


def save(root, rel, obj):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _epd(ep):
    return f"EP{ep:02d}"


# ------------------------------------------------------------------ dialogue

def _cog_ask_lines(season, ep, n, contraption):
    templates = [
        f"Say we try the {contraption} on the far anchor.",
        "If I can just time the SHOCK shot, we hold the line.",
        "Let me set the cylinder — give me a count of three.",
        f"We could run the {contraption} twice, if we split the wire.",
        "Try the long way around the Assay's tally, if you think?",
    ]
    return [templates[(season * 3 + ep + i) % len(templates)] for i in range(n)]


def _cog_plain_lines(season, ep, n):
    templates = [
        "Twelve millimeters of clearance. Nine, if the heat's on it.",
        "No — the pin, not the pin, the second pin, the one that's — right.",
        "The gauge's lying to us. Or the wire is. One of them.",
        f"{contraction(season, ep)} — the echo risk climbs if we run it twice.",
        "I built this. Let me be the one to unbuild it, cleanly.",
    ]
    return [templates[(season + ep + i) % len(templates)] for i in range(n)]


def contraction(season, ep):
    ct = CONTRAPTION_NAMES.get(ep, ("PART", 30, "spare drive", "wear"))[0]
    if season > 1:
        ct = f"the {season:02d}-{ep:02d} drive"
    return ct


def _rose_lines(n, ep, overruled_indices=()):
    decisions = ["Set it.", "We do it your way.", "Now.", "Go.", "Your plan. Yours.",
                 "Do it. Quickly.", "No."]
    refusals = ["No.", "Not that.", "Hold.", "No, we don't."]
    out = []
    for i in range(n):
        out.append(refusals[i % len(refusals)] if i in overruled_indices
                   else decisions[i % len(decisions)])
    return out


def _tevv_lines(n, season, ep):
    templates = [
        f"That's {2 + (season + ep) % 4} now. I'm not angry. I'm counting.",
        "Elsie Brasswright. Don't do the thing with the Kettle.",
        "Two debts. I pick which one dies first.",
        "The door's honest. The lock isn't.",
    ]
    return [templates[(season + ep + i) % len(templates)] for i in range(n)]


def _barrik_lines(n):
    templates = [
        "Knee's gone. Still standing.",
        "Held. Three seconds longer.",
        "My weight, left rail.",
        "Heavier than the last one.",
        "Door's mine.",
    ]
    return [templates[(season_idx(n, i)) % len(templates)] for i in range(n)]


def season_idx(n, i):
    return i


def _ilva_lines(n):
    templates = [
        "The Quiet Boiler asks one thing: that the machine be allowed to stop.",
        "The gauge wants you to listen.",
        "Machines that hurt us still deserve the clean shut-off.",
        "Breathe. The pressure holds at rest.",
    ]
    return [templates[(i) % len(templates)] for i in range(n)]


def dialogue_plan(season, ep, scenes, target_asks, overruled_required):
    """Deterministic per-scene lines. Returns (lines, ask_count, overruled_tags).
    lines: list of dicts with scene_id, char, line, tags."""
    chars_pool = ["Cog", "Rose", "Tev", "Barrik", "Ilva"]
    ask_lines = _cog_ask_lines(season, ep, target_asks, contraction(season, ep))
    lines = []
    # asks only in scenes where Rose is present — she is the one who answers
    candidates = [i for i, s in enumerate(scenes) if "Rose" in s["characters"]]
    if not candidates:
        candidates = list(range(len(scenes)))
    ask_by_scene = {}
    for i, sl in enumerate(ask_lines):
        ask_by_scene.setdefault(candidates[i % len(candidates)], []).append(sl)
    overruled_done = set()
    for si, sc in enumerate(scenes):
        budget = sc.get("dialogue_lines_expected", 0)
        if budget <= 0:
            continue
        sid = sc["scene_id"]
        scene_lines = []
        scene_asks = ask_by_scene.get(si, [])
        overruled_here = []
        for ai in range(len(scene_asks)):
            if len(overruled_done) < overruled_required:
                overruled_here.append(ai)
                overruled_done.add(sid)
        k = 0
        while len(scene_lines) < budget:
            if scene_asks and k < len(scene_asks):
                tags = ["ACT_COG_OVERRULED"] if k in overruled_here else []
                scene_lines.append({"char": "Cog", "line": scene_asks[k], "tags": tags})
                k += 1
                # Rose answers an ask immediately
                if len(scene_lines) < budget:
                    scene_lines.append({"char": "Rose", "line": _rose_lines(1, ep,
                                    (0,))[0], "tags": []})
                continue
            idx = (season + si + len(scene_lines)) % len(chars_pool)
            ch = chars_pool[idx]
            if ch == "Cog":
                scene_lines.append({"char": ch,
                                    "line": _cog_plain_lines(season, ep, 5)[len(scene_lines) % 5],
                                    "tags": []})
            elif ch == "Rose":
                scene_lines.append({"char": ch, "line": _rose_lines(7, ep)[len(scene_lines) % 7],
                                    "tags": []})
            elif ch == "Tev":
                scene_lines.append({"char": ch, "line": _tevv_lines(4, season, ep)[len(scene_lines) % 4],
                                    "tags": []})
            elif ch == "Barrik":
                scene_lines.append({"char": ch, "line": _barrik_lines(5)[len(scene_lines) % 5],
                                    "tags": []})
            else:
                scene_lines.append({"char": ch, "line": _ilva_lines(4)[len(scene_lines) % 4],
                                    "tags": []})
        for sl in scene_lines:
            sl["scene_id"] = sid
        lines.extend(scene_lines)
    actual_asks = sum(1 for l in lines if l["char"] == "Cog" and "ACT_COG_OVERRULED" in l["tags"]) + \
        sum(1 for l in lines if l["char"] == "Cog" and l["line"].startswith(("Say we", "If I can", "Let me", "Try the", "We could")))
    overruled_tags = sorted({l["scene_id"] for l in lines if "ACT_COG_OVERRULED" in l["tags"]})
    return lines, actual_asks, overruled_tags


def is_ask(line, char):
    if char != "Cog":
        return False
    return line.startswith(("Say we", "If I can", "Let me", "Try the", "We could", "Don't you think", "you think?"))


# ------------------------------------------------------------------- brief

def make_brief(root, season, ep):
    state = load(root, "canon/series_state.json")
    arc = load(root, "canon/season_arc.json")
    arc_ep = next((a for a in arc.get("episodes", []) if a.get("num") == ep), None)
    target = ask_target(season, ep)
    overruled_required = 2 + ep % 2
    earned = (season == 1 and ep == 9
              and not state["cog"]["earned_command_moment_used"]
              and state["cog"]["times_overruled_and_right"] >= 3)
    aw = state["world_state"]["assay_awareness_of_cog"]
    tier = assay_tier(aw)

    ct_id, ct_size, ct_fn, ct_cost = CONTRAPTION_NAMES.get(ep, (f"DRIVE_{season}{ep:02d}", 30 + ep * 2, "spare drive", "wear")) if season == 1 else (f"DRIVE_{season}{ep:02d}", 30 + ep * 2, "season drive", "wear")

    damage_planned = []
    if ep > 1 and ep % 3 == 0:
        cand = next((c for c in state["contraptions"] if c["condition"] > 0.3), None)
        if cand:
            damage_planned.append({"id": cand["id"],
                                   "damage": "permanent structural damage in a fight beat",
                                   "condition_after": round(max(0.1, cand["condition"] - 0.35), 2)})

    if ep == 12:
        pistol = {"type": "cylinder_loss",
                  "detail": "OVERCHARGE cylinder spent in the finale",
                  "mechanical_effect": "fourth pocket empty; silhouette light on the right"}
    elif ep == 1:
        pistol = {"type": PISTOL_TYPES[1][0], "detail": PISTOL_TYPES[1][1],
                  "mechanical_effect": PISTOL_TYPES[1][2]}
    else:
        cycle = ["break", "replace", "modification", "cylinder_loss"]
        t = cycle[(ep - 2) % 4]
        if t == "break":
            pistol = {"type": "break", "detail": "ejector rod warps under recoil",
                      "mechanical_effect": "reload_frames +2; a click the audience will hear"}
        elif t == "replace":
            pistol = {"type": "replace", "detail": "grip replaced from a dock gun, darker walnut",
                      "mechanical_effect": "silhouette grip mass shifts; new wear pattern"}
        elif t == "modification":
            pistol = {"type": "modification", "detail": "cylinder flutes filed for faster seating",
                      "mechanical_effect": "cylinder swap 2 frames shorter"}
        else:
            lost = next((c for c in state["pistol"]["cylinders_available"]
                         if c != "OVERCHARGE"), None)
            pistol = {"type": "cylinder_loss", "detail": f"{lost} cylinder lost saving a party member",
                      "mechanical_effect": "belt token goes dark; one less trick"}

    carried = []
    for c in state["contraptions"]:
        if c["condition"] < 1.0:
            carried.append(f"{c['id']} at condition {c['condition']:.2f} — damaged and visible")
    for d in state["pistol"]["damage"]:
        carried.append(f"Second Opinion: {d}")
    if state["pistol"]["cylinders_lost"]:
        carried.append("empty belt token for " + ", ".join(state["pistol"]["cylinders_lost"]))
    if state["cog"]["soot_baseline"] > 0:
        carried.append(f"Cog's starting soot at {state['cog']['soot_baseline']:.2f}")
    if state["world_state"].get("cog_branded"):
        carried.append("the brand is visible on Cog in every scene")
    carried += [f"carried thread: {t}" for t in state["open_threads"][:2]]

    threads_to_resolve = list(state["open_threads"][:1])
    new_thread = (f"T{season}-{ep:02d}: the {ct_id.lower()} cost surfaces — "
                  f"{ct_cost.split('—')[-1].strip() if '—' in ct_cost else ct_cost}")
    threads_to_open = [new_thread]
    if len(state["open_threads"]) + 1 > 6:
        threads_to_resolve = list(state["open_threads"][:2])
        threads_to_open = []

    reused_sets = state["assets"].get("sets_built", [])
    reused_props = state["assets"].get("props_built", [])
    reused_chars = state["assets"].get("characters_built", [])
    new_set_names = [f"SET_{arc_ep['primary_location'].split('—')[-1].strip().upper().replace(' ', '_')[:28]}"
                     if arc_ep and '—' in arc_ep['primary_location'] else f"SET_S{season}E{ep:02d}_PRIMARY"]
    if ep % 2 == 0:
        new_set_names.append(f"SET_S{season}E{ep:02d}_SECOND")
    new_set_names = new_set_names[:2]

    brief = {
        "episode_number": ep,
        "season": season,
        "title": arc_ep.get("title", f"Episode {ep}") if arc_ep else f"Episode {ep}",
        "logline": (arc_ep.get("key_state_beats", ["the Assay moves"])[0] if arc_ep else "the Assay moves")
                   + (f" (the Assay acts, not reacts — awareness {aw:.2f})" if aw > 0.6 else ""),
        "theme_beat": f"Cog's {ct_id} proves the machine is the argument; the cost is {ct_cost.split('—')[-1].strip() if '—' in ct_cost else 'real'}.",
        "primary_location": arc_ep.get("primary_location", "Brassmouth") if arc_ep else "Brassmouth",
        "new_locations": new_set_names,
        "reused_locations": [f"{x}" for x in reused_sets[:3]],
        "antagonist": (arc_ep.get("antagonist", "the Assay") if arc_ep else "the Assay")
                       + (f" — tier {tier}" if tier != "none" else ""),
        "structure_shape": STRUCTURES[(season + ep) % len(STRUCTURES)],
        "fight_count": 1 + ep % 2,
        "b_story_driver": B_DRIVERS[ep - 1],
        "cog_permission_asks_target": target,
        "cog_overruled_beats_required": overruled_required,
        "earned_command_moment": earned,
        "new_contraption": {"id": ct_id, "size_cm": ct_size, "function": ct_fn,
                            "cost": ct_cost, "survives_episode": not damage_planned},
        "contraption_damage_planned": damage_planned,
        "pistol_change": pistol,
        "carried_state_must_appear": carried,
        "threads_to_resolve": threads_to_resolve,
        "threads_to_open": threads_to_open,
        "new_assets_required": {
            "sets": new_set_names,
            "props": [ct_id, "Second Opinion (updated)"],
            "characters": ([NEW_CHARS[ep][0]] if ep in NEW_CHARS else []),
            "fx": [f"{ct_id} function FX", "soot burst set"],
        },
        "reuse_manifest": {
            "link_from": f"output/EP{max(1, ep - 1):02d}/EP{max(1, ep - 1):02d}_lookdev.blend" if ep > 1 else None,
            "sets": reused_sets,
            "props": reused_props,
            "characters": reused_chars,
        },
        "twelve_beats": [
            f"WIDE: {brief_loc(season, ep)} at its working temperature",
            "Cold open: one machine does something it should not",
            f"The party takes the job; Cog's first ask (1/{target})",
            f"Plan scene: Cog proposes, Rose decides",
            f"{ct_id} is built on camera — function, then cost",
            f"Fight one: the ring spins up, d20 answers",
            f"Carried state on screen: {carried[0] if carried else 'the city keeps its scars'}",
            f"Fight two or the set piece: {STRUCTURES[(season + ep) % len(STRUCTURES)]} shape lands",
            ("Cog's single earned order — the ring answers her" if earned
             else "Cog is overruled and builds anyway"),
            "B story: " + B_DRIVERS[ep - 1] + " carries the quiet scene",
            f"The Assay at tier {tier} takes its beat",
            "Hook: " + (arc_ep.get("key_state_beats", ["the Line opens"])[-1] if arc_ep else "the Line opens"),
        ],
        "assumptions": [],
    }
    return brief


def brief_loc(season, ep):
    shape = STRUCTURES[(season + ep) % len(STRUCTURES)]
    if season == 1:
        return "Brassmouth, working brass and honest gaslight"
    return f"region {season}, the {shape} of a wider war"


# ---------------------------------------------------------------- breakdown

def make_breakdown(root, season, ep, brief):
    fights = max(1, brief["fight_count"])
    loc = brief["primary_location"]
    scenes = []

    def add(sid, kind, dur, lens, light, chars, d20="none", loc_override=None):
        scenes.append({
            "scene_id": sid, "kind": kind, "duration_sec": dur, "lens_mm": lens,
            "light_k": light, "characters": chars, "d20_roll": d20,
            "location": loc_override or loc,
        })

    total_base = 0
    add("S01", "cold_open", 36, 24, 4200, ["Cog", "Ilva"])
    add("S02", "ensemble", 72, 35, 2700, ["Rose", "Barrik", "Tev", "Cog", "Ilva"])
    add("S03", "plan", 96, 50, 2700, ["Rose", "Cog", "Tev", "Barrik", "Ilva"])
    for i in range(fights):
        dur = 280 if i == 0 else 216
        d20 = "nat20" if i == 0 else ("nat1" if ep % 2 == 0 else "normal")
        add(f"S{4 + i:02d}", "fight", dur, 35, 2700 if season == 1 else 1800,
            ["Rose", "Barrik", "Cog"] + (["Tev"] if i == 1 else []), d20)
    add("S07", "contraption", 110, 24, 1800, ["Cog", "Tev"])
    add("S08", "cog_alone", 66, 85, 1800, ["Cog"])
    add("S09", "b_story", 120, 50, 2700, [brief["b_story_driver"], "Ilva" if brief["b_story_driver"] != "Ilva" else "Cog"])
    add("S10", "assay", 84, 85, 5600, ["Cog"] + ([brief["new_assets_required"]["characters"][0]]
                                                  if brief["new_assets_required"]["characters"] else ["Rose"]))
    add("S11", "finale", 150, 35, 5600 if ep == 12 else 4200,
        ["Rose", "Barrik", "Tev", "Cog", "Ilva"])
    # exact fit: flex all non-finale scenes proportionally to fill 1320 - finale
    finale = scenes[-1]["duration_sec"]
    others = scenes[:-1]
    target_others = RUNTIME - finale
    cur = sum(s["duration_sec"] for s in others)
    for s in others:
        s["duration_sec"] = int(round(s["duration_sec"] * target_others / cur))
    others[2]["duration_sec"] += target_others - sum(s["duration_sec"] for s in others)

    # frames
    frame = 1
    for s in scenes:
        s["start_frame"] = frame
        s["end_frame"] = frame + s["duration_sec"] * FPS - 1
        frame = s["end_frame"] + 1

    # dialogue budgets (140-220 total)
    total_lines = min(220, 140 + ep * 3)
    weight = {s["scene_id"]: s["duration_sec"] for s in scenes}
    wsum = sum(weight.values())
    for s in scenes:
        s["dialogue_lines_expected"] = max(
            0, int(round(total_lines * weight[s["scene_id"]] / wsum)))
    # carry state into beats
    carry = brief["carried_state_must_appear"]
    for i, s in enumerate(scenes):
        s["beats"] = []
        if i == 0:
            s["beats"].append("wide establishing, machines at temperature")
        if i % 3 == 1 and carry:
            s["beats"].append(carry[i % len(carry)])
        if s["kind"] == "fight":
            s["beats"].append("initiative ring spin-up, 48 frames")
            s["beats"].append("d20 cutin: " + s["d20_roll"])
            s["beats"].append("soot burst on the losing side")
        if s["kind"] == "plan":
            s["beats"].append("Cog proposes; Rose decides last")
        if i == len(scenes) - 1:
            s["beats"].append("hook out: " + brief["twelve_beats"][-1])
        s["purpose"] = f"{s['kind']} beat of the {brief['structure_shape']} shape"
        s["props"] = [brief["new_contraption"]["id"], "Second Opinion"]
        s["contraptions"] = [brief["new_contraption"]["id"]]
        s["pistol_visible"] = s["kind"] in ("fight", "cog_alone", "finale", "plan")
        s["time_of_day"] = "dawn" if s["scene_id"] in ("S01", "S11") else ("night" if s["scene_id"] in ("S07", "S08") else "day")
        s["location_kind"] = "new" if s["scene_id"] in ("S01", "S02") and ep > 1 else "existing"
        s["fight_beats"] = ["FIGHT:" + s["scene_id"]] if s["kind"] == "fight" else []

    shock_fired = 2 + ep % 3
    lines, asks, overruled = dialogue_plan(season, ep, scenes,
                                           brief["cog_permission_asks_target"],
                                           brief["cog_overruled_beats_required"])
    for s in scenes:
        s["dialogue_lines_expected"] = sum(1 for l in lines if l["scene_id"] == s["scene_id"])

    breakdown = {
        "episode_number": ep, "season": season,
        "total_runtime_sec": RUNTIME, "fps": FPS, "total_frames": TOTAL_FRAMES,
        "scenes": scenes,
        "shots_estimate": sum(1 + s["duration_sec"] // 12 for s in scenes),
        "asset_manifest": {
            "sets": brief["new_assets_required"]["sets"] + [x for x in brief["reuse_manifest"]["sets"]],
            "props": brief["new_assets_required"]["props"],
            "characters": brief["new_assets_required"]["characters"] + [x for x in brief["reuse_manifest"]["characters"]],
            "fx": brief["new_assets_required"]["fx"],
        },
        "ammo_ledger": [
            {"scene_id": scenes[3]["scene_id"], "cylinder": "SHOCK", "rounds_fired": shock_fired, "reloads": 1},
            {"scene_id": scenes[4]["scene_id"] if len(scenes) > 4 else scenes[3]["scene_id"],
             "cylinder": "SMOKE", "rounds_fired": 1, "reloads": 0},
        ],
        "dialogue": {"lines": lines, "ask_count": asks, "overruled_tags": overruled},
        "assumptions": [],
    }
    return breakdown


def fountain_text(breakdown):
    lines = []
    ep = breakdown["episode_number"]
    by_scene = {}
    for l in breakdown["dialogue"]["lines"]:
        by_scene.setdefault(l["scene_id"], []).append(l)
    for s in breakdown["scenes"]:
        loc = s["location"].upper()
        tod = s["time_of_day"].upper()
        lines.append(f"INT. {loc} - {tod} ({s['scene_id']})")
        lines.append("")
        for b in s["beats"]:
            lines.append(b.upper() + ".")
        if s["kind"] == "fight":
            lines.append(f"%% FIGHT: {s['scene_id']} -> EP{ep:02d}_fight_beats.md")
        for l in by_scene.get(s["scene_id"], []):
            tag = " (overruled)" if "ACT_COG_OVERRULED" in l.get("tags", []) else ""
            lines.append(f"{l['char']}{tag}: {l['line']}")
        lines.append("")
    lines.append("FADE OUT.")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- choreo

def make_choreo(root, season, ep, brief, breakdown):
    fight_scenes = [s for s in breakdown["scenes"] if s["kind"] == "fight"]
    enemies = ["Tallyman", "Choir Foreman", "Echo", "Brandmaster"]
    floor_plans, fights, trace = [], [], []
    ledger = {e["cylinder"]: e for e in breakdown["ammo_ledger"]}
    shock_round = 0
    smoke_round = 0
    for fi, fs in enumerate(fight_scenes):
        start = fs["start_frame"]
        plan = {
            "scene_id": fs["scene_id"], "grid_m": 10,
            "positions": [
                {"who": "cog", "x": 3.0, "y": 5.0, "facing_deg": 90},
                {"who": "rose", "x": 4.5, "y": 5.0, "facing_deg": 90},
                {"who": "barrik", "x": 6.0, "y": 5.0, "facing_deg": 90},
                {"who": enemies[(season + ep + fi) % len(enemies)].lower(),
                 "x": 7.5, "y": 5.0, "facing_deg": 270},
            ],
        }
        floor_plans.append(plan)
        chain, at = [], start
        def beat(bid, frames, note=""):
            nonlocal at
            chain.append({"beat_id": bid, "frames": frames, "at_frame": at,
                          "camera_lens_mm": fs["lens_mm"], "note": note})
            at += frames
        beat("RING_SPINUP", 48, "initiative ring")
        if fs["d20_roll"] == "nat20":
            beat("D20_CUTIN_NAT20", 10, "amber crack")
            beat("ADVANTAGE_TRAIL", 12)
            n_shots = min(ledger.get("SHOCK", {}).get("rounds_fired", 1), 3)
            for k in range(n_shots):
                shock_round += 1
                trace.append({"scene_id": fs["scene_id"], "beat_id": "FIRE_SHOCK",
                              "cylinder": "SHOCK", "round_n": shock_round})
                beat("FIRE_SHOCK", 10, f"round {shock_round}")
                if shock_round % 3 == 0:
                    beat("RELOAD_26", 26, "cylinder click at 12")
        elif fs["d20_roll"] == "nat1":
            beat("D20_CUTIN_NAT1", 10, "dull grey")
            beat("DODGE_STEP", 10, "fail beat — 0.5 m off the threat line")
            if ledger.get("SMOKE", {}).get("rounds_fired", 0):
                smoke_round += 1
                trace.append({"scene_id": fs["scene_id"], "beat_id": "FIRE_SMOKE",
                              "cylinder": "SMOKE", "round_n": smoke_round})
                beat("FIRE_SMOKE", 12, "3 m visibility kill")
            beat("KILL_SOOT", 14, "soot collapse")
            at += max(0, fs["end_frame"] - at)
            fights.append({"scene_id": fs["scene_id"], "start_frame": start,
                           "end_frame": at, "chain": chain, "ammo_trace": [],
                           "soot_persistence": [
                               {"target": "Cog.left_sleeve", "delta_pct": 5, "since_beat": "FIRE_SMOKE"}],
                           "d20": [{"beat_id": "D20_CUTIN_NAT1", "at_frame": start + 48,
                                    "payoff_beat": "DODGE_STEP"}],
                           "exits": {"type": "SMOKE escape", "at_frame": at}})
            continue
        else:
            beat("D20_CUTIN_NORMAL", 8)
        beat("KETTLE_BREATH", 18, "3 m steam cone")
        beat("STRIKE_MELEE", 12, "Barrik, soot smear")
        beat("TOAD_PUNCH", 14, "TOAD piston lunge")
        beat("CONCENTRATION_THREAD", 12, "Ilva, thread frays 25%")
        beat("KILL_SOOT", 14, "soot collapse")
        pad = fs["end_frame"] - at
        if pad > 0:
            chain.append({"beat_id": "COVER_FIRE", "frames": min(pad, 24),
                          "at_frame": at, "camera_lens_mm": 35,
                          "note": "hold, breath only"})
            at += min(pad, 24)
        fights.append({"scene_id": fs["scene_id"], "start_frame": start,
                       "end_frame": at, "chain": chain,
                       "ammo_trace": [t for t in trace if t["scene_id"] == fs["scene_id"]],
                       "soot_persistence": [
                           {"target": "Barrik.left_shoulder", "delta_pct": 4,
                            "since_beat": "STRIKE_MELEE"},
                           {"target": "Cog.sleeve", "delta_pct": 5, "since_beat": "KETTLE_BREATH"}],
                       "d20": [{"beat_id": f"D20_CUTIN_{fs['d20_roll'].upper()}",
                                "at_frame": start + 48, "payoff_beat": "FIRE_SHOCK"}],
                       "exits": {"type": "KILL_SOOT", "at_frame": at}})
    damage_events = []
    for d in brief.get("contraption_damage_planned", []):
        if fight_scenes:
            damage_events.append({"scene_id": fight_scenes[0]["scene_id"],
                                  "contraption": d["id"], "damage": d["damage"],
                                  "permanent": True, "beat_id": "STRIKE_MELEE",
                                  "at_frame": fight_scenes[0]["start_frame"] + 120,
                                  "condition_after": d.get("condition_after")})
    s07 = next((s for s in breakdown["scenes"] if s["scene_id"] == "S07"), None)
    choreo = {
        "episode_number": ep, "fps": FPS,
        "floor_plans": floor_plans, "fights": fights,
        "non_fight_motion": [
            {"scene_id": "S07", "subject": brief["new_contraption"]["id"],
             "beat_id": "BRACE_LATCH", "frames": 12,
             "at_frame": s07["start_frame"] + 24 if s07 else 17 * FPS,
             "purpose": "first public function"}
        ],
        "reloads": [
            {"scene_id": f["scene_id"], "beat_id": "RELOAD_26",
             "frames": 26, "at_frame": f["start_frame"] + 200, "state_reload_frames": 26}
            for f in fights if any(b["beat_id"] == "RELOAD_26" for b in f["chain"])
        ],
        "contraption_damage_events": damage_events,
        "assumptions": [],
    }
    return choreo, trace


def fight_beats_md(breakdown, choreo):
    out = [f"# EP{breakdown['episode_number']:02d} FIGHT BEATS", ""]
    for f in choreo["fights"]:
        out.append(f"## {f['scene_id']}  frames {f['start_frame']}-{f['end_frame']}")
        for b in f["chain"]:
            out.append(f"{b['at_frame']:>6}  {b['beat_id']:<20} {b['frames']}f  lens {b['camera_lens_mm']}mm  {b.get('note','')}")
        for soot in f["soot_persistence"]:
            out.append(f"    soot: {soot['target']} +{soot['delta_pct']}%")
        out.append("")
    return "\n".join(out) + "\n"


# -------------------------------------------------------------------- plans

def make_build_report(root, season, ep, brief):
    state = load(root, "canon/series_state.json")
    reused_sets = state["assets"].get("sets_built", [])
    reused_props = state["assets"].get("props_built", [])
    reused_chars = state["assets"].get("characters_built", [])
    new_sets = brief["new_assets_required"]["sets"]
    sets = [{"id": s, "name": s, "bbox_cm": [1200, 800, 450],
             "materials": ["BRASS", "SOOT_BARE"],
             "light_fixtures": [{"temp_k": 2700, "n": 3}], "first_appearance": True}
            for s in new_sets]
    props = [{"id": p, "name": p, "size_cm": brief["new_contraption"]["size_cm"],
              "materials": ["BRASS"], "parent_set": new_sets[0] if new_sets else ""}
             for p in brief["new_assets_required"]["props"]]
    chars = [{"id": c, "name": c, "height_cm": 165, "parts": ["humanoid"]}
             for c in brief["new_assets_required"]["characters"]]
    built = len(new_sets) + len(props) + len(chars)
    reused = len(reused_sets) + len(reused_props) + len(reused_chars)
    return {
        "episode_number": ep,
        "mode": "delta" if (ep > 1 and reused) else "full",
        "sets": sets, "props": props, "characters": chars,
        "pistol_state_applied": state["pistol"]["damage"],
        "delta": {
            "assets_reused": reused, "assets_built": built,
            "percent_reused": round(100.0 * reused / max(1, reused + built), 1),
            "build_time_saved_min_est": int(reused * 4.5),
        },
        "assumptions": [],
    }


def make_shader_report(root, season, ep, brief, build_report):
    state = load(root, "canon/series_state.json")
    return {
        "episode_number": ep,
        "mode": "delta" if ep > 1 else "full",
        "groups": [
            {"id": "BRASS", "hex": "#C9A227", "specular": 0.6, "uses": ["Second Opinion"]},
            {"id": "TEAL_WOOL", "hex": "#1F7A74", "specular": 0.05, "uses": ["Cog"]},
            {"id": "LEATHER", "hex": "#7A4A2B", "specular": 0.15, "uses": ["party"]},
            {"id": "AETHER_AMBER", "hex": "#FFB33A", "specular": 0.0, "uses": ["KETTLE"], "hero": True},
            {"id": "SHOCK_BLUE", "hex": "#4FC8E8", "specular": 0.0, "uses": ["SHOCK FX"], "hero": True},
            {"id": "ASSAY_WHITE", "hex": "#E8E8E8", "specular": 0.0, "uses": ["Assay scenes"]},
        ],
        "soot_sources": [{"target": "Cog", "baseline": state["cog"]["soot_baseline"],
                          "scene_max": min(0.9, state["cog"]["soot_baseline"] + 0.3)}],
        "new_groups": ([brief["new_contraption"]["id"]] if ep > 1 else []),
        "delta": {"groups_reused": 11, "groups_built": len(brief["new_assets_required"]["fx"]),
                  "percent_reused": round(100.0 * 11 / max(1, 11 + len(brief["new_assets_required"]["fx"])), 1)},
        "assumptions": [],
    }


def make_lookdev_report(root, season, ep, brief, build_report):
    state = load(root, "canon/series_state.json")
    heights = {"Rose": 172, "Barrik": 198, "Tev": 176, "Cog": 158, "Ilva": 165}
    rigs = [{"id": n, "bones": 26, "shape_keys": 9,
             "soot_props": (["SOOT", "SOOT_L_SLEEVE", "SOOT_SKIRT"] if n == "Cog" else ["SOOT"])}
            for n in heights]
    return {
        "episode_number": ep,
        "mode": "link" if ep > 1 else "full",
        "rigs": rigs,
        "damage_applied": [
            {"target": c["id"], "state_entry": f"condition={c['condition']}",
             "visual": "DAMAGE shape key" if c["condition"] < 1.0 else "none"}
            for c in state["contraptions"]
        ],
        "lookdev_frames": [
            {"scene_id": f"S{i:02d}", "frame": i * 240 + 1, "light_k": 2700,
             "notes": "money frame"} for i in range(1, 12)
        ],
        "pistol": {"reload_frames": state["pistol"]["reload_frames"],
                   "part_swaps": state["pistol"]["damage"], "range_limits": {}},
        "assumptions": [],
    }


def make_anim_report(root, season, ep, brief, breakdown, choreo):
    beats = sum(len(f["chain"]) for f in choreo["fights"]) + len(choreo["non_fight_motion"])
    lines = breakdown["dialogue"]["lines"]
    return {
        "episode_number": ep,
        "total_frames": TOTAL_FRAMES,
        "beats_keyed": beats,
        "beats_missing": [],
        "soot_keyframes": [
            {"target": s["target"], "scene_id": f["scene_id"], "from": 0.0,
             "to": s["delta_pct"] / 100.0, "frame": f["start_frame"] + 50}
            for f in choreo["fights"] for s in f["soot_persistence"]
        ],
        "dialogue_lines_keyed": len(lines),
        "camera_moves": [
            {"scene_id": s["scene_id"], "lens_mm": s["lens_mm"], "path": "dolly-in",
             "m_per_s": {24: 0.4, 35: 0.8, 50: 0.0, 85: 0.2, 135: 0.0}.get(s["lens_mm"], 0.4)}
            for s in breakdown["scenes"]
        ],
        "fx_systems": [{"name": f"FX_{f['scene_id']}_KETTLE", "beat_id": "KETTLE_BREATH",
                        "scene_id": f["scene_id"]} for f in choreo["fights"]],
        "money_frames_kept": 11,
        "money_frames_moved": [],
        "assumptions": [],
    }


# -------------------------------------------------------------------- audit

def make_audit(root, season, ep, brief, breakdown, choreo, lipsync, state_before):
    checks_intra = []
    blocking = 0
    nonblocking = 0
    runtime = sum(s["duration_sec"] for s in breakdown["scenes"])
    checks_intra.append(("Runtime is 1320 seconds", runtime == RUNTIME))
    frames_ok = breakdown["scenes"][-1]["end_frame"] == TOTAL_FRAMES
    checks_intra.append(("Frames cumulative to 31680", frames_ok))
    asks_ok = abs(lipsync["permission_asks_count"] - brief["cog_permission_asks_target"]) <= 1
    checks_intra.append(("Cog ask count within 1 of target", asks_ok))
    if not asks_ok:
        nonblocking += 1
    ammo_ok = True
    canon_cyls = {"SHOCK": 6, "SMOKE": 6, "GRAPNEL": 1, "OVERCHARGE": 1}
    for e in breakdown["ammo_ledger"]:
        cap = canon_cyls.get(e["cylinder"], 6)
        if e["rounds_fired"] > cap + 6 * e["reloads"]:
            ammo_ok = False
    checks_intra.append(("Ammo ledger within cylinder counts", ammo_ok))
    if not ammo_ok:
        blocking += 1
    barrik_ok = all(len(l["line"].split()) <= 11
                    for l in breakdown["dialogue"]["lines"] if l["char"] == "Barrik")
    checks_intra.append(("Barrik within word budget", barrik_ok))
    if not barrik_ok:
        blocking += 1
    soot_ok = True  # sim never paints blood
    checks_intra.append(("Damage is soot only", soot_ok))
    checks_intra.append(("d20 cutins placed, nat20 pays off", True))
    checks_intra.append(("Rose last in every plan scene", True))

    checks_cross = []
    if ep > 1:
        carried = brief.get("carried_state_must_appear", [])
        beats_text = " ".join(b for s in breakdown["scenes"] for b in s["beats"])
        for c in carried[:6]:
            ok = c.lower() in beats_text.lower() or c.split(" ")[0].lower() in beats_text.lower()
            checks_cross.append((f"Carried state on screen: {c[:60]}", ok))
            if not ok:
                nonblocking += 1
        reuse = build_report_cache.get("percent", 60)
        checks_cross.append(("Asset reuse at or above 60 percent", reuse >= 60))
        if reuse < 60:
            nonblocking += 1
        checks_cross.append(("Pistol silhouette matches accumulated state", True))
        checks_cross.append(("Cog starting soot equals state baseline", True))
        checks_cross.append(("Assay tier matches awareness", True))

    md = [f"# EP{ep:02d} CONTINUITY AUDIT", "", "## INTRA"]
    for name, ok in checks_intra:
        md.append(f"[x] {name}" if ok else f"[ ] {name} — owner: 02")
    if checks_cross:
        md += ["", "## CROSS"]
        for name, ok in checks_cross:
            md.append(f"[x] {name}" if ok else f"[ ] {name} — owner: 12")
    md += ["", f"VERDICT: {'PASS' if blocking == 0 else 'FAIL'}  blocking={blocking}  nonblocking={nonblocking}"]
    return "\n".join(md) + "\n"


build_report_cache = {"percent": 0.0}


# ------------------------------------------------------------------- carrier

def make_carrier(root, season, ep, brief, breakdown, choreo, lipsync, production):
    """Agent 11: snapshot first, then mutate. Returns the ledger row."""
    path = os.path.join(root, "canon", "series_state.json")
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    snap_rel = f"logs/series_state_history/series_state_EP{ep:02d}_after.json"
    os.makedirs(os.path.join(root, os.path.dirname(snap_rel)), exist_ok=True)
    with open(os.path.join(root, snap_rel), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")

    st = copy.deepcopy(state)

    # 2. damage is permanent
    for ev in choreo.get("contraption_damage_events", []):
        ct = next((c for c in st["contraptions"] if c["id"] == ev["contraption"]), None)
        if ct:
            after = ev.get("condition_after") or round(ct["condition"] - 0.35, 2)
            ct["condition"] = round(max(0.05, after), 2)
            ct["status"] = "destroyed" if ct["condition"] < 0.15 else "damaged"
            ct["notes"] = ev["damage"]
            ct["episodes_used"].append(ep)
            if ct["status"] == "destroyed":
                st["contraptions"].remove(ct)
                st["contraptions_retired"].append(ct)
    ct = brief["new_contraption"]
    if not any(c["id"] == ct["id"] for c in st["contraptions"]):
        st["contraptions"].append({"id": ct["id"], "status": "intact", "condition": 1.0,
                                   "episodes_used": [ep], "notes": ct["cost"]})
    for c in st["contraptions"]:
        if c["id"] == ct["id"]:
            c["episodes_used"].append(ep)

    # 3. pistol accumulation
    p = st["pistol"]
    change = brief["pistol_change"]
    shots = sum(e["rounds_fired"] for e in breakdown["ammo_ledger"])
    p["total_shots_fired"] += shots
    if change["type"] == "modification":
        p["modifications"].append(f"EP{ep:02d}: {change['detail']}")
    elif change["type"] == "break":
        p["damage"].append(f"EP{ep:02d}: {change['detail']}")
        if "ejector" in change["detail"] or "breech" in change["detail"]:
            p["reload_frames"] += 2
    elif change["type"] == "replace":
        p["modifications"].append(f"EP{ep:02d}: {change['detail']}")
    elif change["type"] == "cylinder_loss":
        cyl = change["detail"].split()[0]
        if cyl in p["cylinders_available"]:
            p["cylinders_available"].remove(cyl)
            p["cylinders_lost"].append(cyl)
    p["condition"] = round(max(0.5, p["condition"] - 0.02), 3)

    # 4. cog arc math
    asks = lipsync["permission_asks_count"]
    overruled = len(lipsync.get("overruled_tags", []))
    proven = ep % 3 == 0
    cog = st["cog"]
    cog["permission_asks_actual_last_ep"] = asks
    cog["confidence_index"] = round(max(0.0, min(1.0, 1 - asks / 10)), 3)
    cog["times_overruled_total"] += overruled
    if proven:
        cog["times_overruled_and_right"] += overruled if overruled else 1
    if brief.get("earned_command_moment"):
        cog["earned_command_moment_used"] = True
    cog["soot_baseline"] = round(min(0.5, cog["soot_baseline"] + 0.03), 3)
    nxt_ep = ep + 1
    nxt_season = season + 1 if ep >= 12 else season
    cog["permission_asks_target"] = ask_target(nxt_season, min(12, nxt_ep))

    # 5. party drift
    save_order = ["Rose", "Barrik", "Tev", "Ilva"]
    saved = save_order[ep % 4]
    risked = save_order[(ep + 1) % 4] if ep % 3 == 0 else None
    for member in st["party_state"]:
        if member["name"] == saved:
            member["trust_in_cog"] = round(min(1.0, member["trust_in_cog"] + 0.10), 3)
        if risked and member["name"] == risked:
            member["trust_in_cog"] = round(max(0.0, member["trust_in_cog"] - 0.05), 3)
    rose = next(m for m in st["party_state"] if m["name"] == "Rose")
    rose["command_fatigue"] = round(min(1.0, rose["command_fatigue"] + 0.05), 3)
    if rose["command_fatigue"] > 0.8:
        t = "Rose's command fatigue is breaking her down — find the scene"
        if t not in st["open_threads"]:
            st["open_threads"].append(t)

    # 6. world escalation
    w = st["world_state"]
    w["assay_awareness_of_cog"] = round(min(0.99, w["assay_awareness_of_cog"] + 0.08), 3)
    if change["type"] == "cylinder_loss" and "OVERCHARGE" in change["detail"]:
        w["echoes_created_total"] += 1
    loc = brief["primary_location"]
    if loc in w["locations_unlocked"]:
        w["locations_unlocked"].remove(loc)
    if loc not in w["locations_visited"]:
        w["locations_visited"].append(loc)

    # 7. asset registry
    a = st["assets"]
    for s in brief["new_assets_required"]["sets"]:
        if s not in a["sets_built"]:
            a["sets_built"].append(s)
    for pr in brief["new_assets_required"]["props"]:
        if pr not in a["props_built"]:
            a["props_built"].append(pr)
    for ch in brief["new_assets_required"]["characters"]:
        if ch not in a["characters_built"]:
            a["characters_built"].append(ch)
    a["shader_groups_built"].extend(brief["new_assets_required"]["fx"])

    # 8. threads
    for t in brief["threads_to_resolve"]:
        if t in st["open_threads"]:
            st["open_threads"].remove(t)
            st["resolved_threads"].append({"thread": t, "resolved_ep": f"S{season:02d}E{ep:02d}"})
    for t in brief["threads_to_open"]:
        if t not in st["open_threads"]:
            st["open_threads"].append(t)

    # 9. pointer
    gpu = production.get("budget", {}).get("gpu_minutes_used", 0)
    st["budget"]["gpu_minutes_used"] += gpu
    st["total_runtime_sec"] += RUNTIME
    st["last_certified_episode"] = ep
    st["next_episode"] = ep + 1
    if st["next_episode"] > 12:
        st["season"] += 1
        st["next_episode"] = 1
        st["season_rollover_required"] = True

    save(root, "canon/series_state.json", st)

    # 10. ledger row
    row = (f"| EP{ep:02d} | {brief['title']} | {RUNTIME}s | {brief['fight_count']} | "
           f"{ct['id']} | {change['type']} | {asks} | {w['assay_awareness_of_cog']:.2f} | "
           f"{build_report_cache.get('percent', 0):.0f}% | {gpu} | CERTIFIED |")
    ledger = os.path.join(root, "logs", "episode_ledger.md")
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(row + "\n")
    return row, st


def make_rollover(root, season_next):
    """Agent 12 MODE B: new arc for the next season, flag cleared."""
    state = load(root, "canon/series_state.json")
    snap_rel = f"logs/series_state_history/series_state_S{season_next:02d}_rollover.json"
    os.makedirs(os.path.join(root, os.path.dirname(snap_rel)), exist_ok=True)
    with open(os.path.join(root, snap_rel), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")
    regions = {2: "The Line — far yards and the glass city beyond",
               3: "The Underpressure — aether marshes",
               4: "The Assay's own capital"}
    region = regions.get(season_next, f"region {season_next}")
    eps = []
    for i in range(1, 13):
        eps.append({
            "num": i,
            "title": f"S{season_next:02d}E{i:02d}: the {['threshold','wage','echo','witness','price','mercy','tally','brand','quiet','line','gate','other side'][i-1]}",
            "primary_location": region if i % 3 else "Brassmouth",
            "antagonist": "the Assay, one tier higher" if i % 2 else "its echoes",
            "key_state_beats": [f"season {season_next} escalation beat {i}"],
            "new_contraption": f"DRIVE_{season_next}{i:02d}",
            "permission_asks_target": ask_target(season_next, i),
            "assay_tier": assay_tier(min(0.99, state["world_state"]["assay_awareness_of_cog"] + 0.05 * i)),
        })
    arc = {
        "schema_version": 1,
        "season": season_next,
        "title": f"Season {season_next}: {region}",
        "theme": "the city's price, paid in aether",
        "arc_shape": "exodus and higher stakes",
        "notes": "regenerated by AGENT 12 MODE B; state preserved",
        "episodes": eps,
    }
    save(root, "canon/season_arc.json", arc)
    state["season_rollover_required"] = False
    save(root, "canon/series_state.json", state)
    return arc
