"""Speaks to pipeline/series_runner.py in its JSON dialect.

The runner is imported and executed IN-PROCESS: its main(argv) prints the
JSON and we capture stdout. Why not subprocess? When the launcher is frozen
into an exe, sys.executable is the app itself — spawning it "to run the
runner" just opens another copy of the GUI (the windows that kept
multiplying). In-process works identically from source and from the exe,
and skips a process spawn on every call.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import threading
import traceback

_MODULE_CACHE = {}
# redirect_stdout swaps the process-global sys.stdout, so concurrent calls
# (main-thread refresh + engine QThread) must not interleave: they would
# swallow or cross each other's JSON.
_CALL_LOCK = threading.Lock()


class RunnerError(RuntimeError):
    pass


def _load_module(root):
    key = os.path.join(root, "pipeline", "series_runner.py")
    if key in _MODULE_CACHE:
        return _MODULE_CACHE[key]
    spec = importlib.util.spec_from_file_location("brass_series_runner", key)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MODULE_CACHE[key] = mod
    return mod


def _extract_json(out):
    for line in reversed((out or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


class RunnerCLI:
    def __init__(self, root, python=None):
        self.root = os.path.abspath(root)
        self.python = python  # kept for API compatibility; subprocess fallback only

    # ------------------------------------------------------------ in-process
    def _call_json(self, *args):
        with _CALL_LOCK:
            out = ""
            try:
                mod = _load_module(self.root)
            except Exception:
                mod = None
            if mod is not None:
                buf = io.StringIO()
                err = None
                try:
                    with contextlib.redirect_stdout(buf):
                        mod.main(list(args))
                except SystemExit:
                    pass  # argparse errors and friends exit the call, not the app
                except Exception:
                    err = traceback.format_exc(limit=8)
                out = buf.getvalue()
                data = _extract_json(out)
                if data is not None:
                    return data
                tail = (out or "").strip()[-800:]
                if err:
                    return {"ok": False,
                            "errors": ["runner raised in-process: "
                                       + err.splitlines()[-1], tail]}
                return {"ok": False, "errors": ["runner produced no JSON", tail]}

            # ----------------------------------------------- subprocess fallback
            py = self.python or (sys.executable if not getattr(sys, "frozen", False)
                                 else None)
            if py is None:
                return {"ok": False, "errors": [
                    "cannot reach the runner: import failed and no python available"]}
            try:
                proc = subprocess.run([py, "pipeline/series_runner.py", *args, "--json"],
                                      cwd=self.root, capture_output=True, text=True,
                                      timeout=180)
            except (subprocess.TimeoutExpired, OSError) as exc:
                return {"ok": False, "errors": [f"runner failed: {exc}"]}
            data = _extract_json(proc.stdout)
            if data is None:
                data = {"ok": False,
                        "errors": ["runner produced no JSON",
                                   ((proc.stderr or proc.stdout) or "")[-800:]]}
            return data

    # ------------------------------------------------------------- public API
    def status(self):
        data = self._call_json("status", "--json")
        if not data.get("ok") or "steps" not in data:
            raise RunnerError(f"status failed: {data.get('errors') or 'wrong payload'}")
        return data

    def next(self):
        data = self._call_json("next", "--json")
        if not data.get("ok") and "step" not in data:
            raise RunnerError(f"next failed: {data.get('errors')}")
        if "steps" in data:  # a status payload is not a next payload
            raise RunnerError("next failed: runner returned the wrong payload")
        return data

    def done(self, step):
        data = self._call_json("done", "--step", step, "--json")
        if "steps" in data or "tag" in data and "step" not in data:
            data = {"ok": False,
                    "errors": ["done failed: runner returned the wrong payload"]}
        return data

    def ledger_rows(self):
        path = os.path.join(self.root, "logs", "episode_ledger.md")
        rows = []
        if not os.path.exists(path):
            return rows
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("|") or line.startswith("|---"):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                # data rows look like: | EP01 | Title | ... | CERTIFIED |
                if cells and len(cells[0]) == 4 and cells[0][:2] == "EP" \
                        and cells[0][2:].isdigit():
                    rows.append(cells)
        return rows
