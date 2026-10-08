# BRASS INITIATIVE — CLAUDE DESKTOP COMMAND CHEAT SHEET

Type one of these in the project chat:

| Command | Effect |
|---|---|
| `RUN` | Start/enter the loop. One step this turn. |
| `CONTINUE` | Next step only. Ends with a status line. |
| `CONTINUE ALL` | Burn through text-lane steps until a machine step, a certification, or context handoff. |
| `RESUME` | Crash recovery / new chat. Re-derives position from disk, continues. |
| `STATUS` | Where the series is: season, episode, step table, next step, assay, pistol, threads. |
| `LEDGER` | Last rows of the episode ledger. |
| `ROLLBACK EP02` | Restore pre-EP02 state from the history snapshot. Told which folders to delete. |
| `STOP` | Park the loop. |

Anything else is treated as a production note (logged in `logs/runner_state.json`
-> `notes`) and the loop continues.

Status lines you will see:

```
[S01E01] AGENT 02 SCREENWRITER  ok  -> NEXT: AGENT 09 DIALOGUE  (say CONTINUE)
[S01E01] AGENT 07 AUDITOR  ok  verdict PASS blocking=0 nonblocking=1  -> NEXT: AGENT 11 CARRIER
[S01E01] MACHINE M01 SETS  AWAITING  -> run on the Blender box: bash pipeline/run_series.sh M01
[S01E01] EPISODE CERTIFIED  -> BEGINNING S01E02  (say CONTINUE)
[S01E12] SEASON COMPLETE  -> BEGINNING SEASON 2  (new chat: say RESUME)
[S01E03] CONTEXT HANDOFF  -> state saved, new chat: say RESUME
```

Reading a status line: tag = season/episode, then the agent that just finished,
then what happens next. If it says AWAITING with a command, run the command on
the Blender box and say `CONTINUE`.

Machine-lane commands (Blender box, from the repo root):

```bash
bash pipeline/run_series.sh          # whole machine pass for the current episode
bash pipeline/run_series.sh M01      # sets only
bash pipeline/run_series.sh M02      # shaders only
bash pipeline/run_series.sh M03      # rig + lookdev only
bash pipeline/run_series.sh M04      # animation only
bash pipeline/run_series.sh M05      # render + comp + QA only

python pipeline/series_runner.py status    # where the loop is (matches the chat)
python pipeline/series_runner.py ledger    # the ledger
python pipeline/series_runner.py rollback --ep EP02   # same as ROLLBACK EP02
```
