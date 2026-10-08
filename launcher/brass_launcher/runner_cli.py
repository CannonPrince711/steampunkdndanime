"""Thin wrapper around pipeline/series_runner.py --json. The runner on disk is
the single source of truth for loop position; this just speaks its JSON dialect."""
import json
import os
import subprocess
import sys


class RunnerError(RuntimeError):
    pass


class RunnerCLI:
    def __init__(self, root, python=None):
        self.root = os.path.abspath(root)
        self.python = python or sys.executable

    def _call(self, *args):
        cmd = [self.python, "pipeline/series_runner.py", *args]
        try:
            proc = subprocess.run(cmd, cwd=self.root, capture_output=True,
                                  text=True, timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise RunnerError(f"runner timed out: {' '.join(cmd)}") from exc
        return proc

    def _json(self, *args):
        proc = self._call(*args, "--json")
        out = (proc.stdout or "").strip()
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line), proc
                except json.JSONDecodeError:
                    continue
        return {"ok": False, "errors": ["runner produced no JSON",
                                        (proc.stderr or proc.stdout)[-800:]]}, proc

    def status(self):
        data, proc = self._json("status")
        if not data.get("ok"):
            raise RunnerError(f"status failed: {data.get('errors')}")
        return data

    def next(self):
        data, proc = self._json("next")
        if not data.get("ok") and "step" not in data:
            raise RunnerError(f"next failed: {data.get('errors')}")
        return data

    def done(self, step):
        data, proc = self._json("done", "--step", step)
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
