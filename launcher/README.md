# BRASS INITIATIVE — Launcher (desktop autopilot)

The desktop control room for the series engine. **Make it automatic**: click
**AUTO RUN** and the loop runs itself — text steps are written by the autopilot
(SIM mode: deterministic, offline, no API key; LLM mode: any OpenAI-compatible
API), machine steps run through local Blender, and the series state, ledger,
and pipeline all update live on screen.

## Run it (any OS, no build needed)

```bash
pip install -r requirements.txt
python brass_launcher.py
```

It auto-detects the repo root (the folder containing `canon/`). Override with
`BRASS_ROOT=/path/to/steampunkdndanime` or in Settings.

## Build the .exe

**Windows** (produces `dist\Brass Initiative.exe`):

```bat
cd launcher
build_exe.bat
```

Double-click `build_exe.bat` if you prefer. Python 3.10+ and internet access
for `pip install` are the only prerequisites.

**Linux / macOS**:

```bash
cd launcher
./build_exe.sh
# -> dist/brass_initiative
```

> PyInstaller builds for the OS it runs on — build on Windows for the Windows
> exe. The exe is self-contained; drop it next to the repo (or set BRASS_ROOT).

## What the buttons do

| Button | Effect |
|---|---|
| ▶ AUTO RUN | Run the loop until STOP/PAUSE/blocked. The full series, forever. |
| ⏭ STEP | Exactly one pipeline step, then stop. |
| ⏸ PAUSE / ▶ RESUME | Hold the loop mid-episode. State is safe on disk. |
| ■ STOP | Disengage. Resume anytime — disk is truth. |
| ✔ MACHINE DONE | Shown when the loop is waiting on a real Blender render: confirm the box finished, the loop continues. |
| SKIP → SIM | Failure guard: replace a failed machine stage with sim artifacts and continue (defect logged). |
| ⚙ SETTINGS | Mode (SIM/LLM), API base URL / key / model, Blender + ffmpeg paths, GPU cap, repo root. |

## Modes

- **SIM** (default): the deterministic autopilot generates every text-lane
  output per the agent contracts and lays down stand-in machine artifacts.
  The whole loop — brief → script → dialogue → choreo → plans → audit →
  carrier → ledger → next episode → season rollover — runs offline. This is
  how you demo, test, and dogfood the pipeline with zero cost.
- **LLM**: each text step is one chat call to your OpenAI-compatible endpoint
  (OpenAI, Ollama at `http://localhost:11434/v1`, LM Studio, vLLM…). The
  model receives the agent prompt + the step's read list + the task card, and
  must reply with the exact file set. Validation runs through
  `pipeline/series_runner.py done --step`; failures get up to 3 repair loops
  with the error fed back, per the autonomy contract.

## LLM settings for real endpoints

| Provider | Base URL | Model |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` or better |
| Ollama | `http://localhost:11434/v1` | `qwen2.5:32b` or bigger |
| LM Studio | `http://localhost:1234/v1` | loaded model |
| vLLM | `http://host:8000/v1` | served model |

Big steps (screenwriter, dialogue) are long — if your endpoint truncates,
raise the model's max output tokens or use a bigger context model.

## How automation maps to the engine

```
AUTO RUN
  │
  ├─ runner: status --json            (where is the loop?)
  │
  ├─ text step → autopilot writes the step's file set
  │     SIM: simwriter.py (deterministic, seeded by season+episode)
  │     LLM: chat completion → {"files":[{path,content}]}
  │   runner: done --step X           (validate; 3 repair loops max)
  │
  ├─ machine step M01–M05
  │     SIM: stand-in artifacts + machine_done marker
  │     LLM mode: bash pipeline/run_series.sh M## (real Blender)
  │     no blender → AWAITING MACHINE (use MACHINE DONE / SKIP → SIM)
  │
  ├─ audit FAIL → unresolved.md + best cut + carrier runs anyway
  │
  └─ episode certified → ledger row → state advances → next episode → …
```

Everything the UI shows comes from `canon/series_state.json` and
`logs/episode_ledger.md` via `pipeline/series_runner.py --json` — the same
single source of truth the Claude Desktop loop uses. Run the UI and the chat
loop side by side; they agree because they read the same disk.
