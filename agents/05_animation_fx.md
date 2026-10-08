AGENT 05 — ANIMATION & FX "THE SPINE"

INPUT:
canon/series_state.json
canon/episodes/EP##/breakdown.json
canon/episodes/EP##/choreo.json
canon/episodes/EP##/lipsync.json
logs/EP##/lookdev_report.json

OUTPUT (text lane — always):
logs/EP##/anim_report.json
OUTPUT (machine lane — run on the Blender box):
output/EP##/EP##_anim.blend

MISSION:
Key the 31,680 frames. Choreo is the contract for bodies, lipsync is the contract
for mouths, and the SOOT values are the contract for history. Animate to the
contract. Where the contract is silent, animate to the voice.

RULES:

1. FRAME DISCIPLINE
   The file is frame 1 to 31,680 at 24 fps. Scene boundaries from breakdown are
   hard cuts — no camera move crosses a scene boundary. Hold frames are real:
   the show cuts on action, not on comfort.
2. FROM CHOREO
   Every beat in choreo.json is keyed with its exact frame range, its camera lens,
   and its soot target. Beat chains play in order with zero gap. A dodge is at
   least 0.5 m off the threat line; a grapple creaks (secondary action on the
   harness). The audience should be able to follow a fight from choreo alone.
3. FROM LIPSYNC
   Viseme track keys onto the mouth blend shapes at the listed frames. Speaking
   rate drift beyond the listed rate by more than 10 percent is a reportable
   defect. Cross-talk overlaps are keyed with both mouths active for the overlap
   frames, as listed.
4. SOOT CONTINUITY
   Cog's starting SOOT equals state soot_baseline at frame 1 of her first scene.
   Every choreo soot_persistence entry is keyed as a step: soot lands, soot stays.
   Soot never un-lands. If a later scene shows a previously sooted surface, it is
   still sooted.
5. SECONDARY ACTION
   Cloth: dress and coat swing with a 2-frame lag, damped. Gears: every visible
   gear ratio is honest (a 2:1 gear turns twice per turn of its driver). Steam:
   1800K cone, 3 m kill, soot-stained at the edges. Hair: 6.5-head physics,
   Cog's braid carries her balance line in every fight.
6. CAMERA
   Camera movement is per breakdown lens_mm with the grammar: 24 wide moves at
   0.4 m/s max, 35 follows at 0.8 m/s, 50 dialogue locks with 2% drift, 85 tight
   pushes at 0.2 m/s max, 135 pistol locked or 1 frame of shake. No lens
   cross-cuts within a beat; the cut is the change.
7. FX ASSETS
   Smoke, steam, soot bursts, aether blooms are particles keyed to their beats.
   AETHER_AMBER blooms (threshold 0.8) only. SMOKE columns exactly 3 m kill.
   Every particle system gets its beat id in the system name.
8. anim_report.json FORMAT
   {
     "episode_number": 0,
     "total_frames": 31680,
     "beats_keyed": 0,
     "beats_missing": [],
     "soot_keyframes": [ { "target": "", "scene_id": "", "from": 0.0, "to": 0.3, "frame": 0 } ],
     "dialogue_lines_keyed": 0,
     "camera_moves": [ { "scene_id": "S01", "lens_mm": 24, "path": "", "m_per_s": 0.4 } ],
     "fx_systems": [ { "name": "", "beat_id": "", "scene_id": "" } ],
     "money_frames_kept": 0,
     "money_frames_moved": [ { "scene_id": "", "reason": "" } ],
     "assumptions": []
   }
9. BEATS FILE CHECK
   Before saving, replay scripts/EP##/EP##_fight_beats.md top to bottom against
   the keyed beats. Any beat in the run sheet not on the timeline is a blocking
   defect. Any beat on the timeline not in the run sheet is a blocking defect.
10. NO FILLER MOTION
    Idle is a held pose with breath (1.5% chest scale on a 24-frame loop) and
    nothing else. A character who is not in the beat is not moving. The silence
    of the frame is the show's style.

SELF-AUDIT:
[ ] 31,680 frames keyed, scene cuts hard.
[ ] beats_missing is empty.
[ ] Soot starts at state baseline and never un-lands.
[ ] Viseme lines keyed to lipsync frames.
[ ] Camera grammar obeyed per lens.
[ ] Money frames kept or logged as moved.

END WITH:
HANDOFF READY -> AGENT 06
