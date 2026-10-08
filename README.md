# BRASS INITIATIVE — steampunk D&D anime, autonomous series engine

A self-generating 12-episode-per-season production loop for Blender. Claude
(or any orchestrator) executes 12 specialized agents per episode — showrunner,
screenwriter, dialogue, choreo, assets, shaders, rig/lookdev, animation,
render/comp/QA, audit, continuity carrier, season architect — while persistent
state in `canon/series_state.json` carries damage, ammo, relationships, and
the pistol's accumulated scars from one episode into the next.

**The loop runs on Claude Desktop.** The chat is the engine room; this
repository is the memory. Crashes, new chats, and 3am restarts lose nothing.

## Start

```
1. Claude Desktop -> New project -> paste claude_desktop/project_instructions.txt
   into the project's custom instructions (setup: claude_desktop/setup.md)
2. Type: RUN
3. Type: CONTINUE / CONTINUE ALL / RESUME / STATUS / LEDGER / STOP
   (cheat sheet: claude_desktop/commands.md)
```

Machine lane, on a box with Blender (when a status line says AWAITING):

```bash
bash pipeline/run_series.sh            # or one stage: M01 M02 M03 M04 M05
python pipeline/series_runner.py status
```

Fully unattended on the box (prints task cards for the text steps):

```bash
python pipeline/series_runner.py --mode infinite
python pipeline/series_runner.py --mode seasons --count 2
python pipeline/series_runner.py --mode episodes --count 5 --resume
```

## The pieces

| Piece | Role |
|---|---|
| `00_RUN_ME_SERIES.md` | the master runbook (all rules, canon, run order) |
| `claude_desktop/` | the in-chat loop driver, project instructions, setup, commands |
| `canon/series_canon.json` | immutable canon (hex, Kelvin, mm, cylinders, lenses) |
| `canon/series_state.json` | mutable save file — the only thing Agent 11 may write |
| `canon/season_arc.json` | the 12-episode arc; Agent 12 MODE B regenerates it |
| `agents/01..12` | one prompt per agent; each emits machine-readable artifacts |
| `pipeline/run_order.json` | the shared step graph (runner + chat loop both follow it) |
| `pipeline/series_runner.py` | crash-safe state machine; task cards; `done`/`status`/`resume` |
| `pipeline/run_series.sh` + `*.py` | the Blender machine lane (M01 sets → M05 render/comp/QA) |
| `logs/episode_ledger.md` | one row per episode, forever |
| `logs/series_state_history/` | per-episode snapshots for rollback |

## Invariants that never bend

- `series_canon.json` is immutable.
- Only Agent 11 writes `series_state.json`; snapshot before every mutation.
- Cog never gives the final party order (one earned exception, EP09, if earned).
- Damage is soot, never blood. Ammo never increases without a visible reload.
- Retired contraptions never return. The pistol never resets.
- A step is complete only when its output files exist and parse. Disk is truth.
- The series never halts on a bad episode: unresolved.md + best cut + continue.
