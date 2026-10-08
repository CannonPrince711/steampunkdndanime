#!/usr/bin/env python3
"""BRASS INITIATIVE — series runner.

The crash-safe loop driver. Disk is truth: a step is done exactly when its
outputs exist and parse. runner_state.json is a cache and a task card, not
the source of state.

Two lanes:
  text    — executed by Claude in the chat (Claude Desktop or otherwise).
            The runner prints the task card; Claude writes the files; Claude
            (or the user) calls `done --step <id>` to mark it verified.
  machine — executed on the Blender box via bash pipeline/run_series.sh.

CLI:
  python pipeline/series_runner.py init
  python pipeline/series_runner.py status
  python pipeline/series_runner.py next
  python pipeline/series_runner.py done --step <step_id>
  python pipeline/series_runner.py machine [--wait]
  python pipeline/series_runner.py ep
  python pipeline/series_runner.py ledger
  python pipeline/series_runner.py rollback --ep EP02
  python pipeline/series_runner.py --mode infinite
  python pipeline/series_runner.py --mode seasons --count 2
  python pipeline/series_runner.py --mode episodes --count 5
  python pipeline/series_runner.py --mode episodes --count 5 --resume
  python pipeline/series_runner.py --mode episodes --count 5 --dry-run

Exit codes: 0 = ran to a stop, 3 = waiting on Claude (text step pending),
1 = error.
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ORDER = os.path.join(ROOT, "pipeline", "run_order.json")
STATE = os.path.join(ROOT, "canon", "series_state.json")
RUNNER_STATE = os.path.join(ROOT, "logs", "runner_state.json")
LEDGER = os.path.join(ROOT, "logs", "episode_ledger.md")

EXIT_WAITING_CLAUDE = 3


def now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def p(*parts: str) -> str:
    return os.path.join(ROOT, *parts)


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def load_state() -> dict:
    return read_json(STATE)


def load_run_order() -> dict:
    return read_json(RUN_ORDER)


def load_runner_state() -> dict:
    if os.path.exists(RUNNER_STATE):
        return read_json(RUNNER_STATE)
    return {}


def save_runner_state(rs: dict) -> None:
    rs["updated_at"] = now()
    write_json(RUNNER_STATE, rs)


def ep_dir(ep: int) -> str:
    return f"EP{ep:02d}"


def expand(path: str, ep: int) -> str:
    return path.replace("EP##", ep_dir(ep))


def status_line(tag: str, label: str, status: str, extra: str = "") -> str:
    line = f"[{tag}] {label:<32} {status}"
    if extra:
        line += f"  {extra}"
    return line


def episode_steps(order: dict, season: int, ep: int) -> list:
    steps = copy.deepcopy(order["steps_ep01"])
    if not (season == 1 and ep == 1):
        repl = order["steps_ep02plus"]["replaces"]
        for i, st in enumerate(steps):
            if st["id"] in repl:
                steps[i] = repl[st["id"]]
    return steps


# ---------------------------------------------------------------- completion

def _file_ok(path: str) -> bool:
    if not os.path.exists(path):
        return False
    if path.endswith(".json"):
        try:
            read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False
    return True


def _machine_done(ep: int) -> set:
    marker = p("logs", ep_dir(ep), "machine_done.json")
    if not os.path.exists(marker):
        return set()
    try:
        return set(read_json(marker))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return set()


def verdict_of(ep: int):
    report = p("logs", ep_dir(ep), "continuity_report.md")
    if not os.path.exists(report):
        return None
    with open(report, "r", encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"VERDICT:\s*(PASS|FAIL)\s+blocking=(\d+)\s+nonblocking=(\d+)", text)
    if not m:
        return None
    return {"verdict": m.group(1), "blocking": int(m.group(2)), "nonblocking": int(m.group(3))}


def step_complete(step: dict, season: int, ep: int) -> bool:
    sid = step["id"]
    for rel in step.get("write", []):
        if not _file_ok(p(expand(rel, ep))):
            return False
    if step["lane"] == "machine":
        if sid not in _machine_done(ep):
            return False
        # key artifacts of the render step
        if sid == "M05_render_comp_qa":
            for rel in ("output/EP##/EP##_master.mov", "output/EP##/EP##_proxy_720p.mp4",
                        "output/EP##/EP##_contact_sheet.png", "logs/EP##/production_report.json"):
                if not _file_ok(p(expand(rel, ep))):
                    return False
    if sid == "07_continuity_auditor":
        if verdict_of(ep) is None:
            return False
    if sid == "11_carrier":
        snap = p("logs", "series_state_history", f"series_state_EP{ep:02d}_after.json")
        if not _file_ok(snap):
            return False
        if not os.path.exists(LEDGER):
            return False
        with open(LEDGER, "r", encoding="utf-8") as fh:
            if f"| EP{ep:02d} |" not in fh.read():
                return False
        st = load_state()
        if st.get("last_certified_episode") != ep:
            return False
    if sid == "12_rollover":
        st = load_state()
        try:
            arc = read_json(p("canon", "season_arc.json"))
        except (OSError, json.JSONDecodeError):
            return False
        return arc.get("season") == st.get("season") and not st.get("season_rollover_required", False)
    return True


def first_incomplete(order: dict, season: int, ep: int):
    for st in episode_steps(order, season, ep):
        if not step_complete(st, season, ep):
            return st
    return None


def rollover_pending(state: dict) -> bool:
    return bool(state.get("season_rollover_required", False))


def position(order: dict) -> dict:
    """Where is the loop right now? Derived from disk only."""
    state = load_state()
    season, ep = state.get("season", 1), state.get("next_episode", 1)
    if rollover_pending(state) and state.get("last_certified_episode") == 12:
        return {"season": season - 1 if season > 1 else 1, "episode": 12,
                "pending_rollover": True, "next_step": order["rollover_step"],
                "state": state}
    step = first_incomplete(order, season, ep)
    return {"season": season, "episode": ep, "pending_rollover": False,
            "next_step": step, "state": state}


# ---------------------------------------------------------------- task cards

def task_card(pos: dict) -> str:
    order = load_run_order()
    st = pos["next_step"]
    season, ep = pos["season"], pos["episode"]
    tag = f"S{season:02d}E{ep:02d}"
    lines = [
        f"TASK CARD — {tag} — {st['agent_label']}",
        f"LANE: {st['lane']}",
    ]
    if st["lane"] == "machine":
        lines.append(f"COMMAND (run on the Blender box, then say CONTINUE):")
        lines.append(f"  {st['machine_cmd']}")
    else:
        lines.append(f"AGENT PROMPT: {st['agent_file']}")
    lines.append("READ (only these files):")
    for rel in st.get("read", []):
        lines.append(f"  {expand(rel, ep)}")
    lines.append("WRITE (step completes when all exist and parse):")
    for rel in st.get("write", []):
        lines.append(f"  {expand(rel, ep)}")
    if st["lane"] == "machine":
        artifacts = {
            "M01_sets": [f"output/EP{ep:02d}/EP{ep:02d}_sets.blend"],
            "M03_lookdev": [f"output/EP{ep:02d}/EP{ep:02d}_lookdev.blend"],
            "M04_anim": [f"output/EP{ep:02d}/EP{ep:02d}_anim.blend"],
            "M05_render_comp_qa": [
                f"output/EP{ep:02d}/EP{ep:02d}_master.mov",
                f"output/EP{ep:02d}/EP{ep:02d}_proxy_720p.mp4",
                f"output/EP{ep:02d}/EP{ep:02d}_contact_sheet.png",
                f"logs/EP{ep:02d}/production_report.json",
            ],
        }.get(st["id"], [])
        if artifacts:
            lines.append("ARTIFACTS: " + ", ".join(os.path.basename(a) for a in artifacts))
        lines.append(f"MARKER: {expand(order['machine_done_file'], ep)} gains '{st['id']}' on success")
    if st.get("notes"):
        lines.append(f"NOTES: {st['notes']}")
    lines.append(f"THEN: python pipeline/series_runner.py done --step {st['id']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- commands

def cmd_init(_args) -> int:
    tree = [
        "canon/episodes", "agents", "scripts", "pipeline", "library",
        "output", "logs/series_state_history",
    ]
    for t in tree:
        os.makedirs(p(t), exist_ok=True)
    if not os.path.exists(STATE):
        print(f"ERROR: {STATE} missing — restore from repository. Refusing to invent canon state.")
        return 1
    state = load_state()
    baseline = p("logs", "series_state_history", "series_state_EP00_baseline.json")
    if not os.path.exists(baseline):
        write_json(baseline, state)
        print(f"baseline snapshot -> {os.path.relpath(baseline, ROOT)}")
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w", encoding="utf-8") as fh:
            fh.write(
                "# BRASS INITIATIVE — EPISODE LEDGER\n\n"
                "| EP | Title | Runtime | Fights | New Contraption | Pistol Change | Cog Asks | Assay | Reuse | GPU min | Status |\n"
                "|----|-------|---------|--------|-----------------|---------------|----------|-------|-------|---------|--------|\n"
            )
        print(f"ledger header -> {os.path.relpath(LEDGER, ROOT)}")
    print("init complete. Run: python pipeline/series_runner.py next")
    return 0


def cmd_status(_args) -> int:
    order = load_run_order()
    pos = position(order)
    state = pos["state"]
    season, ep = pos["season"], pos["episode"]
    tag = f"S{season:02d}E{ep:02d}"
    print(f"SEASON {season:02d}  EPISODE {ep:02d}  ({tag})")
    print(f"last_certified: {state.get('last_certified_episode', 0)}   "
          f"total_runtime_sec: {state.get('total_runtime_sec', 0)}")
    print(f"assay_awareness: {state['world_state']['assay_awareness_of_cog']:.2f}   "
          f"pistol_condition: {state['pistol']['condition']:.2f}   "
          f"pistol_shots: {state['pistol']['total_shots_fired']}")
    print(f"open_threads: {len(state['open_threads'])}   "
          f"retired_contraptions: {len(state['contraptions_retired'])}")
    steps = episode_steps(order, season, ep) if not pos["pending_rollover"] else []
    if steps:
        for st in steps:
            mark = "done" if step_complete(st, season, ep) else "PENDING"
            print(f"  {st['id']:<22} {st['lane']:<8} {mark}")
    if pos["pending_rollover"]:
        print("  ROLLOVER PENDING -> AGENT 12 MODE B")
    print()
    if pos["next_step"] is None:
        print("episode complete — nothing pending")
    else:
        print("NEXT:")
        print(task_card(pos))
    return 0


def cmd_next_json(args) -> int:
    order = load_run_order()
    pos = position(order)
    if pos["next_step"] is None:
        print(json.dumps({"ok": True, "step": None, "position": pos["season"],
                          "episode": pos["episode"], "pending_rollover": pos["pending_rollover"],
                          "line": f"episode S{pos['season']:02d}E{pos['episode']:02d} complete"}))
        return 0
    rs = load_runner_state()
    rs.update({
        "current_season": pos["season"],
        "current_episode": pos["episode"],
        "current_step": pos["next_step"]["id"],
        "awaiting": pos["next_step"]["lane"],
        "started_at": rs.get("started_at", now()),
    })
    save_runner_state(rs)
    print(json.dumps({"ok": True, "step": pos["next_step"],
                      "season": pos["season"], "episode": pos["episode"],
                      "tag": f"S{pos['season']:02d}E{pos['episode']:02d}",
                      "pending_rollover": pos["pending_rollover"]}))
    return EXIT_WAITING_CLAUDE if pos["next_step"]["lane"] == "text" else 0


def cmd_done_json(args) -> int:
    order = load_run_order()
    pos = _done_position(order, args.step)
    sid = args.step
    steps = ([order["rollover_step"]] if pos["pending_rollover"]
             else episode_steps(order, pos["season"], pos["episode"]))
    match = [s for s in steps if s["id"] == sid]
    if not match:
        print(json.dumps({"ok": False, "errors": [
            f"step {sid} is not part of S{pos['season']:02d}E{pos['episode']:02d}"],
            "valid": [s["id"] for s in steps]}))
        return 1
    st = match[0]
    if not step_complete(st, pos["season"], pos["episode"]):
        missing = [expand(r, pos["episode"]) for r in st.get("write", [])
                   if not _file_ok(p(expand(r, pos["episode"])))]
        if st["lane"] == "machine" and sid not in _machine_done(pos["episode"]):
            missing.append(f"{expand(order['machine_done_file'], pos['episode'])} missing '{sid}'")
        if sid == "07_continuity_auditor" and verdict_of(pos["episode"]) is None:
            missing.append("continuity_report.md lacks the VERDICT line")
        if sid == "11_carrier":
            snap = p("logs", "series_state_history", f"series_state_EP{pos['episode']:02d}_after.json")
            if not _file_ok(snap):
                missing.append(f"snapshot {os.path.relpath(snap, ROOT)} missing")
            if load_state().get("last_certified_episode") != pos["episode"]:
                missing.append("series_state.json last_certified_episode not advanced")
        print(json.dumps({"ok": False, "errors": missing or ["checks failed"]}))
        return 1
    tag = f"S{pos['season']:02d}E{pos['episode']:02d}"
    extra = ""
    verdict = None
    if sid == "07_continuity_auditor":
        verdict = verdict_of(pos["episode"])
        extra = f"verdict {verdict['verdict']} blocking={verdict['blocking']} nonblocking={verdict['nonblocking']}"
    rs = load_runner_state()
    done = rs.get("done_steps", {})
    done.setdefault(f"{pos['season']:02d}:{pos['episode']:02d}", []).append(sid)
    rs["done_steps"] = done
    rs["current_step"] = None
    rs["awaiting"] = None
    save_runner_state(rs)
    episode_complete = first_incomplete(order, pos["season"], pos["episode"]) is None
    st2 = load_state()
    certified_line = None
    rollover_line = None
    if episode_complete:
        certified_line = status_line(tag, "EPISODE", "CERTIFIED",
                                     _ep_summary(order, pos["season"], pos["episode"]))
        if rollover_pending(st2) and st2.get("last_certified_episode") == 12:
            rollover_line = (f"SEASON {pos['season']:02d} COMPLETE -> BEGINNING SEASON "
                             f"{st2.get('season', pos['season'] + 1):02d} (AGENT 12 MODE B FIRST)")
    nxt = position(order)
    print(json.dumps({
        "ok": True, "step": sid, "tag": tag, "episode_complete": episode_complete,
        "certified_line": certified_line, "rollover_line": rollover_line,
        "verdict": verdict,
        "next": ({"step": nxt["next_step"], "season": nxt["season"], "episode": nxt["episode"],
                  "tag": f"S{nxt['season']:02d}E{nxt['episode']:02d}"} if nxt["next_step"] else None),
        "line": status_line(tag, st["agent_label"], "ok", extra),
    }))
    return EXIT_WAITING_CLAUDE if (nxt["next_step"] and nxt["next_step"]["lane"] == "text") else 0


def cmd_status_json(_args) -> int:
    order = load_run_order()
    pos = position(order)
    state = pos["state"]
    season, ep = pos["season"], pos["episode"]
    steps = episode_steps(order, season, ep) if not pos["pending_rollover"] else []
    print(json.dumps({
        "ok": True,
        "tag": f"S{season:02d}E{ep:02d}",
        "season": season, "episode": ep,
        "pending_rollover": pos["pending_rollover"],
        "last_certified": state.get("last_certified_episode", 0),
        "total_runtime_sec": state.get("total_runtime_sec", 0),
        "state_summary": {
            "assay_awareness": state["world_state"]["assay_awareness_of_cog"],
            "pistol_condition": state["pistol"]["condition"],
            "pistol_shots": state["pistol"]["total_shots_fired"],
            "pistol_cylinders": state["pistol"]["cylinders_available"],
            "cog_asks_target": state["cog"]["permission_asks_target"],
            "cog_asks_last": state["cog"].get("permission_asks_actual_last_ep"),
            "cog_confidence": state["cog"]["confidence_index"],
            "cog_soot": state["cog"]["soot_baseline"],
            "open_threads": state["open_threads"],
            "retired_contraptions": len(state["contraptions_retired"]),
            "contraptions": [{ "id": c["id"], "condition": c["condition"], "status": c["status"]}
                             for c in state.get("contraptions", [])],
            "gpu_used": state["budget"]["gpu_minutes_used"],
            "gpu_cap": state["budget"]["gpu_minutes_cap_per_episode"],
        },
        "steps": [{"id": s["id"], "label": s["agent_label"], "lane": s["lane"],
                   "done": step_complete(s, season, ep)} for s in steps]
                  + ([{"id": "12_rollover", "label": "AGENT 12 ARCHITECT (MODE B)",
                       "lane": "text",
                       "done": step_complete(order["rollover_step"], state.get("season", 1), 12)}]
                     if pos["pending_rollover"] else []),
        "next": ({"step": pos["next_step"], "tag": f"S{season:02d}E{ep:02d}"}
                 if pos["next_step"] else None),
    }, default=str))
    return 0


def cmd_next(args) -> int:
    order = load_run_order()
    pos = position(order)
    if pos["next_step"] is None:
        print(f"episode S{pos['season']:02d}E{pos['episode']:02d} complete")
        return 0
    tag = f"S{pos['season']:02d}E{pos['episode']:02d}"
    rs = load_runner_state()
    rs.update({
        "current_season": pos["season"],
        "current_episode": pos["episode"],
        "current_step": pos["next_step"]["id"],
        "awaiting": pos["next_step"]["lane"],
        "started_at": rs.get("started_at", now()),
    })
    save_runner_state(rs)
    print(task_card(pos))
    return EXIT_WAITING_CLAUDE if pos["next_step"]["lane"] == "text" else 0


def _done_position(order: dict, sid: str) -> dict:
    """Episode context for a `done` call. runner_state wins when the requested
    step belongs to that episode — essential for 11_carrier (state has already
    advanced to the next episode) and for 12_rollover (the rollover work itself
    clears season_rollover_required, so the flag can no longer identify it)."""
    rs = load_runner_state()
    state = load_state()
    rollover_id = order["rollover_step"]["id"]
    pinned = (rs.get("current_season") and rs.get("current_episode"))
    if (sid == rollover_id and state.get("last_certified_episode") == 12
            and (not pinned or int(rs["current_episode"]) == 12)):
        # state.season already advanced past the finished season
        finished = (int(state.get("season", 2)) - 1
                    if int(state.get("season", 2)) > 1 else 1)
        return {"season": finished, "episode": 12, "pending_rollover": True,
                "next_step": order["rollover_step"], "state": state}
    if pinned:
        season, ep = int(rs["current_season"]), int(rs["current_episode"])
        steps = episode_steps(order, season, ep)
        if any(s["id"] == sid for s in steps):
            return {"season": season, "episode": ep, "pending_rollover": False,
                    "next_step": None, "state": state}
    return position(order)


def cmd_done(args) -> int:
    order = load_run_order()
    pos = _done_position(order, args.step)
    sid = args.step
    steps = ([order["rollover_step"]] if pos["pending_rollover"]
             else episode_steps(order, pos["season"], pos["episode"]))
    match = [s for s in steps if s["id"] == sid]
    if not match:
        print(f"ERROR: step {sid} is not part of S{pos['season']:02d}E{pos['episode']:02d}. "
              f"Valid: {', '.join(s['id'] for s in steps)}")
        return 1
    st = match[0]
    if not step_complete(st, pos["season"], pos["episode"]):
        missing = [expand(r, pos["episode"]) for r in st.get("write", [])
                   if not _file_ok(p(expand(r, pos["episode"])))]
        if st["lane"] == "machine" and sid not in _machine_done(pos["episode"]):
            missing.append(f"{expand(order['machine_done_file'], pos['episode'])} missing '{sid}'")
        if sid == "07_continuity_auditor" and verdict_of(pos["episode"]) is None:
            missing.append("continuity_report.md lacks the VERDICT line")
        if sid == "11_carrier":
            snap = p("logs", "series_state_history", f"series_state_EP{pos['episode']:02d}_after.json")
            if not _file_ok(snap):
                missing.append(f"snapshot {os.path.relpath(snap, ROOT)} missing")
            if load_state().get("last_certified_episode") != pos["episode"]:
                missing.append("series_state.json last_certified_episode not advanced")
        print(f"ERROR: {sid} not complete. Missing/invalid: {', '.join(missing) or 'checks failed'}")
        return 1
    tag = f"S{pos['season']:02d}E{pos['episode']:02d}"
    extra = ""
    if sid == "07_continuity_auditor":
        v = verdict_of(pos["episode"])
        extra = f"verdict {v['verdict']} blocking={v['blocking']} nonblocking={v['nonblocking']}"
    print(status_line(tag, st["agent_label"], "ok", extra))
    rs = load_runner_state()
    done = rs.get("done_steps", {})
    done.setdefault(f"{pos['season']:02d}:{pos['episode']:02d}", []).append(sid)
    rs["done_steps"] = done
    rs["current_step"] = None
    rs["awaiting"] = None
    save_runner_state(rs)
    if first_incomplete(order, pos["season"], pos["episode"]) is None:
        st2 = load_state()
        print(status_line(tag, "EPISODE", "CERTIFIED",
                          _ep_summary(order, pos["season"], pos["episode"])))
        if rollover_pending(st2) and st2.get("last_certified_episode") == 12:
            print(f"SEASON {pos['season']:02d} COMPLETE -> BEGINNING SEASON "
                  f"{st2.get('season', pos['season'] + 1):02d} (AGENT 12 MODE B FIRST)")
    nxt = position(order)
    if nxt["next_step"] is not None:
        print("NEXT:")
        print(task_card(nxt))
    return EXIT_WAITING_CLAUDE if (nxt["next_step"] and nxt["next_step"]["lane"] == "text") else 0


def cmd_machine(args) -> int:
    order = load_run_order()
    pos = position(order)
    if pos["pending_rollover"]:
        print("ROLLOVER PENDING — run Agent 12 MODE B in the chat first, then retry.")
        return EXIT_WAITING_CLAUDE
    season, ep = pos["season"], pos["episode"]
    steps = episode_steps(order, season, ep)
    ran_any = False
    for st in steps:
        if st["lane"] != "machine" or step_complete(st, season, ep):
            continue
        pending_text = [s for s in steps
                        if s["lane"] == "text" and steps.index(s) < steps.index(st)
                        and not step_complete(s, season, ep)]
        if pending_text:
            pos2 = {"season": season, "episode": ep, "next_step": pending_text[0]}
            print("MACHINE BLOCKED — text steps pending first:")
            print(task_card(pos2))
            return EXIT_WAITING_CLAUDE
        tag = f"S{season:02d}E{ep:02d}"
        print(status_line(tag, st["agent_label"], "start"))
        proc = subprocess.run(st["machine_cmd"].split(), cwd=ROOT)
        if proc.returncode != 0 or not step_complete(st, season, ep):
            print(status_line(tag, st["agent_label"], "FAILED",
                              f"rc={proc.returncode} — see logs/EP{ep:02d}/"))
            return 1
        print(status_line(tag, st["agent_label"], "ok"))
        ran_any = True
    if not ran_any:
        print(f"no machine steps pending for S{season:02d}E{ep:02d}")
    if args.wait:
        return cmd_next(args)
    return 0


def _ep_summary(order: dict, season: int, ep: int) -> str:
    st = load_state()
    brief_path = p("canon", "episodes", ep_dir(ep), "brief.json")
    try:
        brief = read_json(brief_path)
    except (OSError, json.JSONDecodeError):
        brief = {}
    prod_path = p("logs", ep_dir(ep), "production_report.json")
    gpu = ""
    if os.path.exists(prod_path):
        try:
            gpu = f" gpu {read_json(prod_path).get('budget', {}).get('gpu_minutes_used', '?')}m"
        except (OSError, json.JSONDecodeError):
            pass
    v = verdict_of(ep)
    verdict = v["verdict"] if v else "n/a"
    return (f"asks {st['cog'].get('permission_asks_actual_last_ep', '?')} "
            f"assay {st['world_state']['assay_awareness_of_cog']:.2f} "
            f"reuse {brief.get('reuse_manifest', {}).get('percent_declared', '?')}{gpu} "
            f"verdict {verdict}")


def cmd_ep(args) -> int:
    """Drive one episode: machine steps run here, text steps print cards."""
    order = load_run_order()
    pos = position(order)
    if pos["pending_rollover"]:
        print(task_card(pos))
        return EXIT_WAITING_CLAUDE
    season, ep = pos["season"], pos["episode"]
    print(f"=== EPISODE S{season:02d}E{ep:02d} ===")
    rc = cmd_machine(args)
    if rc == EXIT_WAITING_CLAUDE:
        return rc
    if rc != 0:
        return rc
    pos = position(order)
    if pos["next_step"] is None:
        print(status_line(f"S{season:02d}E{ep:02d}", "EPISODE", "CERTIFIED", _ep_summary(order, season, ep)))
        return 0
    print(task_card(pos))
    return EXIT_WAITING_CLAUDE


def cmd_ledger(_args) -> int:
    if not os.path.exists(LEDGER):
        print("ledger empty — no episodes certified yet")
        return 0
    with open(LEDGER, "r", encoding="utf-8") as fh:
        lines = fh.read().strip().splitlines()
    rows = [l for l in lines if l.startswith("|")]
    for l in rows[-14:]:
        print(l)
    return 0


def cmd_rollback(args) -> int:
    m = re.fullmatch(r"EP(\d+)", args.ep)
    if not m:
        print("ERROR: --ep must look like EP02")
        return 1
    ep = int(m.group(1))
    snap = p("logs", "series_state_history", f"series_state_EP{ep:02d}_after.json")
    if ep == 1:
        snap = p("logs", "series_state_history", "series_state_EP00_baseline.json")
    if not os.path.exists(snap):
        print(f"ERROR: no snapshot at {os.path.relpath(snap, ROOT)}")
        return 1
    restored = read_json(snap)
    write_json(STATE, restored)
    print(f"restored {os.path.relpath(STATE, ROOT)} from {os.path.relpath(snap, ROOT)}")
    print(f"state now: season {restored['season']} next_episode {restored['next_episode']}")
    print("the episode's outputs are still on disk — delete canon/episodes/"
          f"{ep_dir(ep)}/, scripts/{ep_dir(ep)}/, logs/{ep_dir(ep)}/, output/{ep_dir(ep)}/ "
          "to re-run it clean.")
    return 0


def cmd_driver(args) -> int:
    """--mode infinite|seasons|episodes [--count N] [--resume] [--dry-run]"""
    order = load_run_order()
    certified_now = load_state().get("last_certified_episode", 0)
    season_now = load_state().get("season", 1)
    episodes_done = 0
    seasons_done = 0
    guard = 0
    while True:
        guard += 1
        if guard > 400:
            print("guard: 400 loop iterations — stopping (state may be stuck)")
            return 1
        pos = position(order)
        if pos["next_step"] is None:
            print(f"episode S{pos['season']:02d}E{pos['episode']:02d} already complete — advancing")
            continue
        if pos["pending_rollover"]:
            print(task_card(pos))
            print("WAITING FOR CLAUDE — Agent 12 MODE B, then `done --step 12_rollover`, then --resume")
            return EXIT_WAITING_CLAUDE
        step = pos["next_step"]
        tag = f"S{pos['season']:02d}E{pos['episode']:02d}"
        if args.dry_run:
            print(f"[DRY] {tag} would run: {step['agent_label']} ({step['lane']})")
            pos2 = position(order)
            if step["lane"] == "text" and pos2["next_step"] == step:
                print("WAITING FOR CLAUDE (dry run: no state changes)")
                return EXIT_WAITING_CLAUDE
            continue
        if step["lane"] == "text":
            print(task_card(pos))
            print("WAITING FOR CLAUDE — complete the step in chat, then `done --step "
                  f"{step['id']}`, then --resume")
            return EXIT_WAITING_CLAUDE
        rc = cmd_machine(args)
        if rc == EXIT_WAITING_CLAUDE:
            return rc
        if rc != 0:
            print(f"episode {tag} machine step failed — fix and --resume "
                  f"(series does not halt; see logs/EP{pos['episode']:02d}/unresolved.md pattern)")
            return rc
        # machine pass of this episode finished; the rest is text work
        pos = position(order)
        if pos["next_step"] is None:
            st = load_state()
            tag2 = f"S{st['season']:02d}E{st['last_certified_episode']:02d}"
            print(status_line(tag2, "EPISODE", "CERTIFIED", _ep_summary(order, st["season"], st["last_certified_episode"])))
            episodes_done += 1
            if st["last_certified_episode"] == 12:
                seasons_done += 1
                print(f"SEASON {pos['season']:02d} COMPLETE -> BEGINNING SEASON {st['season']:02d}")
            if args.mode == "episodes" and episodes_done >= args.count:
                print(f"stop: {args.count} episodes certified")
                return 0
            if args.mode == "seasons" and seasons_done >= args.count:
                print(f"stop: {args.count} seasons certified")
                return 0
            continue
        print(task_card(pos))
        print("WAITING FOR CLAUDE — complete the step in chat, then `done --step "
              f"{pos['next_step']['id']}`, then --resume")
        return EXIT_WAITING_CLAUDE


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BRASS INITIATIVE series runner")
    sub = ap.add_subparsers(dest="cmd")
    sp = sub.add_parser("init")
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--json", action="store_true", dest="as_json")
    sp_next = sub.add_parser("next")
    sp_next.add_argument("--json", action="store_true", dest="as_json")
    d = sub.add_parser("done")
    d.add_argument("--step", required=True)
    d.add_argument("--json", action="store_true", dest="as_json")
    m = sub.add_parser("machine")
    m.add_argument("--wait", action="store_true")
    sub.add_parser("ep")
    sub.add_parser("ledger")
    rb = sub.add_parser("rollback")
    rb.add_argument("--ep", required=True)
    ap.add_argument("--mode", choices=["infinite", "seasons", "episodes"], default=None)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.mode:
        return cmd_driver(args)
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "status":
        return cmd_status_json(args) if args.as_json else cmd_status(args)
    if args.cmd == "next":
        return cmd_next_json(args) if args.as_json else cmd_next(args)
    if args.cmd == "done":
        return cmd_done_json(args) if args.as_json else cmd_done(args)
    if args.cmd == "machine":
        return cmd_machine(args)
    if args.cmd == "ep":
        return cmd_ep(args)
    if args.cmd == "ledger":
        return cmd_ledger(args)
    if args.cmd == "rollback":
        return cmd_rollback(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
