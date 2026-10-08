"""The autopilot. A QThread that drives the series loop end to end.

For every step the runner reports:
  text    -> SIM mode: simwriter generates the step.
            LLM mode: an OpenAI-compatible chat call writes the step.
  machine -> SIM mode: deterministic artifacts are laid down.
            LLM mode: `bash pipeline/run_series.sh M##` runs locally if a
            Blender binary is configured; otherwise the engine pauses and the
            UI offers "MACHINE DONE" (or "SKIP WITH SIM" per the failure guard).

Failure handling follows the autonomy contract: max 3 repair loops per step;
audit failures write unresolved.md and still run the carrier. The loop never
permanently stops on a bad episode unless the user hits STOP.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import zlib
import struct

from PySide6.QtCore import QThread, Signal

from . import simwriter
from .llm import LLMError, build_user_prompt, chat, extract_files, STEP_SYSTEM
from .runner_cli import RunnerCLI, RunnerError

MACHINE_STAGES = {
    "M01_sets": "M01", "M02_shaders": "M02", "M03_lookdev": "M03",
    "M04_anim": "M04", "M05_render_comp_qa": "M05",
}


class Engine(QThread):
    log = Signal(str, str)            # message, level(info|ok|warn|err)
    line = Signal(str)                # canonical status line
    state_changed = Signal(dict)      # fresh status json
    step_update = Signal(dict)        # {"step": id, "phase": str}
    awaiting_machine = Signal(dict)   # {"tag": ..., "stage": ...}
    machine_resumed = Signal()
    blocked = Signal(str)
    episode_certified = Signal(str, str)  # tag, certified line
    season_complete = Signal(str)
    stopped = Signal(str)             # final message

    def __init__(self, root, settings, parent=None):
        super().__init__(parent)
        self.root = os.path.abspath(root)
        self.settings = settings
        self.cli = RunnerCLI(self.root)
        self._stop = False
        self._pause = False
        self._one = False
        self._machine_wait = False
        self._machine_resume = False

    # ------------------------------------------------------------- controls
    def request_stop(self):
        self._stop = True
        self._machine_resume = True
        self.wake()

    def request_step_once(self):
        self._one = True

    def set_pause(self, paused):
        self._pause = paused
        if not paused:
            self.wake()

    def machine_done_clicked(self):
        self._machine_resume = True
        self.wake()

    def wake(self):
        # QThread has no wake; the loop polls flags on a short sleep
        pass

    def _wait_while(self, cond, poll=0.2):
        while cond() and not self._stop:
            time.sleep(poll)

    def _paused(self):
        return self._pause and not self._stop

    # ------------------------------------------------------------- step work
    def _read_inputs(self, step):
        inputs = []
        for rel in step.get("read", []):
            path = os.path.join(self.root, rel)
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    inputs.append((rel, fh.read()))
            except OSError:
                continue
        # always give the model the voice bible and canon even if the step
        # forgot to list them — they are the law
        for rel in ("canon/voice_bible.md", "canon/series_canon.json"):
            if rel not in [n for n, _ in inputs]:
                path = os.path.join(self.root, rel)
                if os.path.exists(path):
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        inputs.append((rel, fh.read()))
        return inputs

    def _agent_prompt(self, step):
        path = os.path.join(self.root, step.get("agent_file", ""))
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""

    def _write_files(self, files):
        written = []
        for f in files:
            rel = f["path"].replace("\\", "/").lstrip("/")
            if ".." in rel.split("/"):
                raise ValueError(f"unsafe path {f['path']}")
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path) or self.root, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f["content"])
            written.append(rel)
        return written

    def _run_llm_step(self, tag, step, retry_ctx=""):
        s = self.settings
        inputs = self._read_inputs(step)
        task = {
            "tag": tag,
            "step": step["id"],
            "lane": step["lane"],
            "agent": step["agent_label"],
            "read": step.get("read", []),
            "write": step.get("write", []),
            "notes": step.get("notes", ""),
        }
        user = build_user_prompt(task, self._agent_prompt(step), inputs,
                                 max_input_chars=int(s.get("context_chars", 120000)))
        if retry_ctx:
            user += ("\n\nPREVIOUS ATTEMPT FAILED VALIDATION. Errors:\n" + retry_ctx +
                     "\nFix them and emit the full file set again.")
        self.log.emit(f"LLM {tag} {step['id']}: drafting via {s.get('model', '?')} …", "info")
        reply = chat(s.get("base_url", ""), s.get("api_key", ""),
                     s.get("model", "gpt-4o-mini"), STEP_SYSTEM, user,
                     timeout=int(s.get("timeout", 900)))
        files, err = extract_files(reply)
        if err:
            raise LLMError(f"could not extract file set from reply: {err}")
        self._write_files(files)
        return [f["path"] for f in files]

    # --------------------------------------------------------- sim machine
    def _png(self, path, w, h, rows_fn):
        raw = b""
        for y in range(h):
            raw += b"\x00" + bytes(rows_fn(y))
        def chunk(tag, payload):
            c = struct.pack(">I", len(payload)) + tag + payload
            return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        with open(path, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
            fh.write(chunk(b"IHDR", ihdr))
            fh.write(chunk(b"IDAT", zlib.compress(raw, 9)))
            fh.write(chunk(b"IEND", b""))

    def _sim_frame(self, path, season, ep, seed):
        """A 120x68 'cel' frame: sky band, gear, floor. Deterministic per seed."""
        w, h = 120, 68
        brass = (201, 162, 39)
        teal = (31, 122, 116)
        soot = (26, 23, 20)
        amber = (255, 179, 58)
        cx, cy = 60 + (seed % 7) * 6 - 21, 30

        def row(y):
            out = bytearray()
            for x in range(w):
                if y < 26:  # sky
                    t = y / 26.0
                    c = (int(soot[0] + (teal[0] - soot[0]) * (1 - t) * 0.55),
                         int(soot[1] + (teal[1] - soot[1]) * (1 - t) * 0.55),
                         int(soot[2] + (teal[2] - soot[2]) * (1 - t) * 0.6))
                elif y < 30:  # horizon glow
                    c = amber if (x + y * 13 + seed) % 97 < 6 else (122, 99, 40)
                else:  # floor
                    c = (int(soot[0] * 1.15), int(soot[1] * 1.15), int(soot[2] * 1.2)) if (x + y) % 8 else soot
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if 14 <= d <= 20:  # gear ring
                    if (int(d) + (x % 9)) % 3 == 0:
                        c = brass
                elif d < 6:
                    c = amber if d < 3 else (138, 107, 31)
                out += bytes(c)
            return bytes(out)
        self._png(path, w, h, row)

    def _sim_machine_artifacts(self, season, ep, step_id):
        e = f"EP{ep:02d}"
        out_dir = os.path.join(self.root, "output", e)
        os.makedirs(os.path.join(out_dir, "frames"), exist_ok=True)
        os.makedirs(os.path.join(out_dir, "comp_frames"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "logs", e), exist_ok=True)
        note = "SIMBLEND v1 — generated by the launcher simulation autopilot"
        if step_id == "M01_sets":
            with open(os.path.join(out_dir, f"{e}_sets.blend"), "w") as fh:
                fh.write(note)
        if step_id == "M03_lookdev":
            with open(os.path.join(out_dir, f"{e}_lookdev.blend"), "w") as fh:
                fh.write(note)
        if step_id == "M04_anim":
            with open(os.path.join(out_dir, f"{e}_anim.blend"), "w") as fh:
                fh.write(note)
        if step_id == "M05_render_comp_qa":
            for i in (1, 15840, 31680):
                self._sim_frame(os.path.join(out_dir, "frames", f"frame_{i:05d}.png"),
                                season, ep, i)
            # contact sheet: 3 tiles of 120x68
            tw, h = 120, 68
            w = tw * 3
            def sheet_row(y):
                out = bytearray()
                for tile in range(3):
                    seed = [1, 15840, 31680][tile]
                    cx = 60 + (seed % 7) * 6 - 21
                    cy = 30
                    for x in range(tw):
                        if y < 26:
                            c = (18, 40, 44)
                        elif y < 30:
                            c = (255, 179, 58) if (x + y * 13 + seed) % 97 < 6 else (122, 99, 40)
                        else:
                            c = (30, 27, 24) if (x + y) % 8 else (26, 23, 20)
                        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                        if 14 <= d <= 20 and (int(d) + (x % 9)) % 3 == 0:
                            c = (201, 162, 39)
                        elif d < 6:
                            c = (255, 179, 58) if d < 3 else (138, 107, 31)
                        out += bytes(c)
                return bytes(out)
            self._png(os.path.join(out_dir, f"{e}_contact_sheet.png"), w, h, sheet_row)
            for base in (f"{e}_master.mov", f"{e}_proxy_720p.mp4"):
                with open(os.path.join(out_dir, base), "w") as fh:
                    fh.write("SIM video stand-in (simulation autopilot)\n")
            gpu = 300 + ep * 22 + season * 40
            prod = {
                "episode_number": ep,
                "render": {"engine_primary": "EEVEE Next", "engine_hero": "Cycles",
                           "frames": 31680, "gpu_minutes": gpu, "degrade_rungs": []},
                "comp": {"layers": ["L1", "L2", "L3", "L4", "L5", "L6"], "audio_pending": True},
                "qa": {"frames_checked": 2000, "black_frames": [], "palette_drift_frames": [],
                       "soot_violations": [], "ammo_violations": [], "defects": []},
                "budget": {"gpu_minutes_used": gpu, "cap": self.settings.get("gpu_cap", 900)},
                "status": "CERTIFIED",
                "assumptions": ["simulation autopilot: stand-in artifacts"],
            }
            with open(os.path.join(self.root, "logs", e, "production_report.json"), "w") as fh:
                json.dump(prod, fh, indent=2)
                fh.write("\n")
            timing = {"frames": 31680, "fps": 24, "est_gpu_minutes": gpu,
                      "actual_gpu_minutes": gpu, "cap": 900, "degrade_rungs": []}
            with open(os.path.join(self.root, "logs", e, "render_timing.json"), "w") as fh:
                json.dump(timing, fh, indent=2)
        # machine_done marker
        marker = os.path.join(self.root, "logs", e, "machine_done.json")
        done = []
        if os.path.exists(marker):
            try:
                done = json.load(open(marker))
            except (OSError, json.JSONDecodeError):
                done = []
        if step_id not in done:
            done.append(step_id)
            with open(marker, "w") as fh:
                json.dump(done, fh, indent=2)
                fh.write("\n")

    def _run_machine_step(self, tag, step, sim):
        stage = MACHINE_STAGES[step["id"]]
        if sim:
            self._sim_machine_artifacts(int(tag[1:3]), int(tag[4:6]), step["id"])
            return True
        blender = self.settings.get("blender_path") or shutil.which("blender")
        if not blender:
            self.awaiting_machine.emit({"tag": tag, "stage": stage,
                                        "reason": "no blender configured — set it in Settings or skip"})
            self._machine_wait = True
            self._machine_resume = False
            self._wait_while(lambda: (not self._machine_resume) and self._machine_wait)
            self._machine_wait = False
            if self._stop:
                return False
            if not self._machine_resume:
                return False
            # user clicked skip: lay down sim artifacts instead
            self.log.emit(f"{tag} M{stage}: skipped on user command — sim artifacts", "warn")
            self._sim_machine_artifacts(int(tag[1:3]), int(tag[4:6]), step["id"])
            return True
        cmd = ["bash", "pipeline/run_series.sh", stage]
        self.log.emit(f"{tag} M{stage}: running {' '.join(cmd)} …", "info")
        t0 = time.time()
        proc = subprocess.Popen(cmd, cwd=self.root, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        for line_ in proc.stdout:
            line_ = line_.rstrip()
            if line_:
                self.log.emit(f"  box> {line_}", "info")
        proc.wait()
        self.log.emit(f"{tag} M{stage}: rc={proc.returncode} in {time.time() - t0:.0f}s",
                 "ok" if proc.returncode == 0 else "err")
        return proc.returncode == 0

    # --------------------------------------------------------------- main loop
    def run(self):
        self.log.emit("autopilot engaged", "ok")
        try:
            while not self._stop:
                self._wait_while(self._paused)
                if self._stop:
                    break
                try:
                    status = self.cli.status()
                except RunnerError as exc:
                    self.log.emit(f"runner error: {exc}", "err")
                    self.blocked.emit(f"runner error: {exc}")
                    break
                self.state_changed.emit(status)
                if not status.get("next"):
                    self.log.emit("no pending steps — series at a rest point", "warn")
                    self.stopped.emit("no pending steps")
                    break
                # pin the runner to this episode (essential for 11_carrier:
                # by the time `done` runs, series_state has already advanced)
                try:
                    self.cli.next()
                except RunnerError:
                    pass  # status already told us the next step
                nxt = status["next"]
                step = nxt["step"]
                tag = nxt["tag"]
                season, ep = status["season"], status["episode"]
                sim = self.settings.get("mode", "sim") == "sim"
                self.log.emit(f"{tag} → {step['agent_label']} ({step['lane']})", "info")
                self.step_update.emit({"step": step["id"], "phase": "start", "tag": tag})

                # attempt loop: max 3 per autonomy contract
                ok = False
                last_err = ""
                for attempt in range(1, 4):
                    if self._stop:
                        break
                    try:
                        if step["lane"] == "text":
                            if sim:
                                files = self._sim_text_step(season, ep, step["id"])
                            else:
                                files = self._run_llm_step(tag, step, last_err)
                            self.log.emit(f"{tag} {step['id']}: wrote {', '.join(files)}", "ok")
                        else:
                            ok = self._run_machine_step(tag, step, sim)
                            if ok:
                                res = self.cli.done(step["id"])
                                if res.get("ok"):
                                    break
                                last_err = "; ".join(res.get("errors", []))
                            continue
                        res = self.cli.done(step["id"])
                        if res.get("ok"):
                            ok = True
                            break
                        last_err = "; ".join(res.get("errors", []))
                        self.log.emit(f"{tag} {step['id']}: validation failed (attempt {attempt}): {last_err}",
                                 "warn")
                        # audit failure path (contract: best cut, series does not halt)
                        if step["id"] == "07_continuity_auditor" and attempt >= 2:
                            self._force_fail_verdict(season, ep, last_err)
                            self._write_unresolved(season, ep, last_err)
                            self.log.emit(f"{tag}: audit failed — unresolved.md written, "
                                     f"delivering best cut, running carrier anyway", "warn")
                            res = self.cli.done(step["id"])
                            if res.get("ok"):
                                ok = True
                            break
                    except (LLMError, RunnerError, ValueError, OSError) as exc:
                        last_err = str(exc)
                        self.log.emit(f"{tag} {step['id']}: attempt {attempt} failed: {last_err}", "err")
                if self._stop:
                    break
                if not ok:
                    self._write_unresolved(season, ep, last_err)
                    self.log.emit(f"{tag} {step['id']}: 3 loops exhausted — blocked", "err")
                    self.blocked.emit(f"{tag} {step['id']}: {last_err[:300]}")
                    break
                if res.get("certified_line"):
                    self.line.emit(res["certified_line"])
                    self.episode_certified.emit(tag, res["certified_line"])
                if res.get("rollover_line"):
                    self.season_complete.emit(res["rollover_line"])
                    self.line.emit(res["rollover_line"])
                if res.get("next"):
                    nl = res.get("line")
                    if nl:
                        self.line.emit(nl)
                if self._one:
                    self._one = False
                    self.log.emit("step complete — stepping stopped (request AUTO for the full loop)", "ok")
                    self._stop = True
        finally:
            self.stopped.emit("autopilot disengaged")

    def _sim_text_step(self, season, ep, step_id):
        """Generate the step's files with the deterministic autopilot."""
        root = self.root
        e = f"EP{ep:02d}"
        epdir = os.path.join(root, "canon", "episodes", e)
        os.makedirs(epdir, exist_ok=True)
        state = json.load(open(os.path.join(root, "canon", "series_state.json")))
        if step_id in ("01_showrunner", "12_season_architect"):
            brief = simwriter.make_brief(root, season, ep)
            simwriter.save(root, f"canon/episodes/{e}/brief.json", brief)
            return [f"canon/episodes/{e}/brief.json"]
        if step_id == "12_rollover":
            arc = simwriter.make_rollover(root, state["season"])
            return ["canon/season_arc.json"]
        brief = json.load(open(os.path.join(root, f"canon/episodes/{e}/brief.json")))
        if step_id == "02_screenwriter":
            bd = simwriter.make_breakdown(root, season, ep, brief)
            simwriter.save(root, f"canon/episodes/{e}/breakdown.json", bd)
            os.makedirs(os.path.join(root, "scripts", e), exist_ok=True)
            with open(os.path.join(root, "scripts", e, f"{e}.fountain"), "w", encoding="utf-8") as fh:
                fh.write(simwriter.fountain_text(bd))
            return [f"canon/episodes/{e}/breakdown.json", f"scripts/{e}/{e}.fountain"]
        bd = json.load(open(os.path.join(root, f"canon/episodes/{e}/breakdown.json")))
        if step_id == "09_dialogue_director":
            lines = bd["dialogue"]["lines"]
            asks = sum(1 for l in lines if simwriter.is_ask(l["line"], l["char"]))
            overruled = sorted({l["scene_id"] for l in lines if "ACT_COG_OVERRULED" in l.get("tags", [])})
            lipsync = {"episode_number": ep, "fps": 24,
                       "permission_asks_count": asks,
                       "overruled_tags": overruled, "lines": []}
            for sc in bd["scenes"]:
                slines = [l for l in lines if l["scene_id"] == sc["scene_id"]]
                span = (sc["end_frame"] - sc["start_frame"])
                for i, l in enumerate(slines):
                    words = len(l["line"].split())
                    length = max(8, (int(words * 5.7) + 1) // 2 * 2)
                    start = sc["start_frame"] + int(span * 0.15 + span * 0.6 * i / max(1, len(slines)))
                    lipsync["lines"].append({
                        "scene_id": sc["scene_id"], "char": l["char"], "line": l["line"],
                        "start_frame": start, "end_frame": start + length,
                        "length_frames": length,
                        "speaking_rate": f"{len(l['line'].split()) / max(1, length / 16):.2f} words/16f",
                        "viseme_track": "oeciao" * ((length // 2) // 6 + 1),
                        "beat": "", "tags": l.get("tags", []),
                    })
            simwriter.save(root, f"canon/episodes/{e}/lipsync.json", lipsync)
            pass_lines = []
            for sc in bd["scenes"]:
                pass_lines.append(f"INT. {sc['location'].upper()} - {sc['time_of_day'].upper()} ({sc['scene_id']})")
                for l in [x for x in lines if x["scene_id"] == sc["scene_id"]]:
                    tag = " [ACT_COG_OVERRULED]" if "ACT_COG_OVERRULED" in l.get("tags", []) else ""
                    pass_lines.append(f"{l['char']}{tag}: {l['line']}")
                pass_lines.append("")
            os.makedirs(os.path.join(root, "scripts", e), exist_ok=True)
            with open(os.path.join(root, "scripts", e, f"{e}_dialogue_pass.fountain"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(pass_lines) + "\n")
            return [f"scripts/{e}/{e}_dialogue_pass.fountain", f"canon/episodes/{e}/lipsync.json"]
        if step_id == "08_fight_choreographer":
            choreo, _trace = simwriter.make_choreo(root, season, ep, brief, bd)
            simwriter.save(root, f"canon/episodes/{e}/choreo.json", choreo)
            with open(os.path.join(root, "scripts", e, f"{e}_fight_beats.md"), "w", encoding="utf-8") as fh:
                fh.write(simwriter.fight_beats_md(bd, choreo))
            return [f"canon/episodes/{e}/choreo.json", f"scripts/{e}/{e}_fight_beats.md"]
        if step_id == "03_plan":
            rep = simwriter.make_build_report(root, season, ep, brief)
            simwriter.build_report_cache["percent"] = rep["delta"]["percent_reused"]
            simwriter.save(root, f"logs/{e}/build_report.json", rep)
            return [f"logs/{e}/build_report.json"]
        if step_id == "10_plan":
            rep = simwriter.make_shader_report(root, season, ep, brief,
                                               json.load(open(os.path.join(root, f"logs/{e}/build_report.json"))))
            simwriter.save(root, f"logs/{e}/shader_report.json", rep)
            return [f"logs/{e}/shader_report.json"]
        if step_id == "04_plan":
            rep = simwriter.make_lookdev_report(root, season, ep, brief,
                                                json.load(open(os.path.join(root, f"logs/{e}/build_report.json"))))
            simwriter.save(root, f"logs/{e}/lookdev_report.json", rep)
            return [f"logs/{e}/lookdev_report.json"]
        if step_id == "05_plan":
            bd2 = bd
            choreo = json.load(open(os.path.join(root, f"canon/episodes/{e}/choreo.json")))
            rep = simwriter.make_anim_report(root, season, ep, brief, bd2, choreo)
            simwriter.save(root, f"logs/{e}/anim_report.json", rep)
            return [f"logs/{e}/anim_report.json"]
        if step_id == "07_continuity_auditor":
            lipsync = json.load(open(os.path.join(root, f"canon/episodes/{e}/lipsync.json")))
            choreo = json.load(open(os.path.join(root, f"canon/episodes/{e}/choreo.json")))
            state_before = json.load(open(os.path.join(root, "canon", "series_state.json")))
            md = simwriter.make_audit(root, season, ep, brief, bd, choreo, lipsync, state_before)
            with open(os.path.join(root, f"logs/{e}/continuity_report.md"), "w", encoding="utf-8") as fh:
                fh.write(md)
            return [f"logs/{e}/continuity_report.md"]
        if step_id == "11_carrier":
            prod_path = os.path.join(root, f"logs/{e}/production_report.json")
            prod = json.load(open(prod_path)) if os.path.exists(prod_path) else {"budget": {"gpu_minutes_used": 0}}
            lipsync = json.load(open(os.path.join(root, f"canon/episodes/{e}/lipsync.json")))
            choreo = json.load(open(os.path.join(root, f"canon/episodes/{e}/choreo.json")))
            row, new_state = simwriter.make_carrier(root, season, ep, brief, bd, choreo, lipsync, prod)
            self.log.emit(f"carrier: {row.strip('|').strip()[:100]}…", "ok")
            return ["canon/series_state.json"]
        raise ValueError(f"sim autopilot has no writer for step {step_id}")

    def _force_fail_verdict(self, season, ep, err):
        """Rewrite continuity_report.md so it ends with a valid FAIL VERDICT line.
        The audit step must be 'complete' (file parses + verdict present) even
        when the episode ships with defects — that is the contract."""
        path = os.path.join(self.root, "logs", f"EP{ep:02d}", "continuity_report.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        existing = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                existing = fh.read()
        if "VERDICT: FAIL" not in existing:
            existing = (existing.split("VERDICT:")[0].rstrip()
                        if "VERDICT:" in existing else existing)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(existing + "\n\n## FORCED FAIL (autopilot best-cut path)\n")
                fh.write(err + "\n")
                fh.write("\nVERDICT: FAIL  blocking=1  nonblocking=0\n")
        else:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"\n(autopilot note: {err[:300]})\n")

    def _write_unresolved(self, season, ep, err):
        path = os.path.join(self.root, "logs", f"EP{ep:02d}", "unresolved.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"## S{season:02d}E{ep:02d} unresolved\n\n{err}\n\n"
                     f"Best cut delivered per contract; state advanced with the defect logged.\n\n")
