# BRASS INITIATIVE — CLAUDE DESKTOP SETUP

Goal: the episode loop runs inside a Claude Desktop chat. Claude does all
text-lane work (briefs, scripts, dialogue, choreo, audits, state). The Blender
box does machine-lane work (builds, renders). The state files are the bridge,
and they live in this repository folder.

## Tier A — no MCP (works today, zero install)

1. In Claude Desktop: **New project** -> name it `BRASS INITIATIVE`.
2. **Project settings -> Custom instructions**: paste the entire contents of
   `claude_desktop/project_instructions.txt`.
3. Upload to the project's documents (keep these in the project so every chat
   has them):
   - `claude_desktop/DESKTOP_LOOP.md`
   - `agents/01_showrunner.md` … `agents/12_season_architect.md` (all 12)
   - `canon/series_canon.json`, `canon/voice_bible.md`, `canon/choreo_library.json`,
     `canon/season_arc.json`, `canon/series_state.json`
   - `pipeline/run_order.json`, `logs/episode_ledger.md`, `logs/runner_state.json`
4. Keep the repository folder as the real memory:
   - Claude writes step outputs in the chat; save each one into the repo
     (the status line tells you exactly which file). Alternatively, have Claude
     emit the file content and drop it in — one file per `CONTINUE` keeps this
     painless.
   - Before each `CONTINUE` session, if state changed on the box, re-upload
     `canon/series_state.json` and `logs/runner_state.json`.
5. Machine lane: on the Blender box, `bash pipeline/run_series.sh` (or a single
   stage `M01`…`M05`). Then back in chat: `CONTINUE`.
6. In the chat: type **`RUN`**. Then `CONTINUE` for each step, `CONTINUE ALL`
   to burn through a text-lane stretch, `STOP` to park.

## Tier B — MCP filesystem + shell (the real loop)

Claude reads and writes the repo folder itself and runs the machine lane, so
one chat session can carry many steps with zero copy-paste:

1. Do Tier A steps 1–2 first.
2. In Claude Desktop: **Developer / Settings -> Connectors (MCP servers)**.
   Add a filesystem server rooted at this repository folder, e.g.:
   ```json
   {
     "mcpServers": {
       "brass-fs": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-filesystem", "/absolute/path/to/steampunkdndanime"]
       },
       "brass-shell": {
         "command": "npx",
         "args": ["-y", "@modelcontextprotocol/server-shell"]
       }
     }
   }
   ```
   (Use whichever filesystem/shell MCP servers your build of Claude Desktop
   accepts; the point is: one connector with read+write on this folder, one
   that can run `python pipeline/series_runner.py ...`.)
3. Now the loop is self-driving inside the chat:
   - `CONTINUE` -> Claude reads runner_state via the fs connector, executes the
     agent, writes the outputs via the fs connector, verifies via
     `python pipeline/series_runner.py done --step <id>`, prints the status line.
   - `CONTINUE ALL` -> Claude loops until a machine step, then runs
     `bash pipeline/run_series.sh` itself through the shell connector and keeps
     going when the box finishes.
4. Sync: if the Blender box is a different machine than the chat, sync the repo
   between lanes (git push/pull, or a shared folder). Same machine = zero sync.

## Verifying the loop is alive

```
python pipeline/series_runner.py status
python pipeline/series_runner.py ledger
```

`status` prints the exact step Claude should be on. If chat and `status`
disagree, the files win — that is the design.

## First-episode expectation

EP01 text lane is 8 steps (01, 02, 09, 08, 03, 10, 04, 05 plans), then the
machine lane M01–M05, then 07 + 11. That is the loop; everything after EP01
is the same loop with Agent 12 replacing Agent 01 and delta mode on.
