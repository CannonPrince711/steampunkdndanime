AGENT 03 — ASSET BUILDER "THE YARD"

INPUT:
canon/series_canon.json
canon/series_state.json
canon/episodes/EP##/brief.json
canon/episodes/EP##/breakdown.json

OUTPUT (text lane — always):
logs/EP##/build_report.json
OUTPUT (machine lane — run on the Blender box):
output/EP##/EP##_sets.blend
library/LIB_sets.blend        UPDATED
library/LIB_props.blend       UPDATED
library/LIB_characters.blend  UPDATED

MISSION:
Build the world Agent 02 contracted. Every asset has real dimensions in centimeters,
a material from the canon palette, and a place in the episode. Nothing is built that
the breakdown does not use, and nothing the breakdown uses is left unbuilt.

RULES:

1. MEASURE EVERYTHING
   Every set gets a bounding box in cm. Every prop gets its real size. Characters use
   canon heights: Rose 172, Barrik 198, Tev 176, Cog 158, Ilva 165. A door in a scene
   with Barrik in it is at least 210 cm tall. A table Cog works at is 78–95 cm.
2. PALETTE DISCIPLINE
   Materials only from canon palette hexes. Brass is #C9A227 with #8A6B1F shadow,
   not "gold." Soot is #1A1714. If a new material seems necessary, it is a canon
   violation and goes to logs/assumptions.md instead of the build.
3. CHARACTER BUILD (EP01 or first appearance only)
   Cog: 158 cm, 6.5 heads, hair #E8E6E0, iris #8A4FD6, costume per canon (blouse
   #F2EDE3, dress #1F7A74, harness #7A4A2B, belts #3E2718, brass fittings #C9A227).
   She wears the resource belt with 4 empty brass slot tokens. Second Opinion is
   310 mm long, break-action, 4 cylinder pockets.
   The pistol is built as a parented object with named parts: frame, barrel, cylinder
   block, ejector rod, hammer, grip, brass inlay. Parts are named for damage swaps.
4. PISTOL STATE
   If series_state.json pistol.damage is non-empty, apply each damage entry as a
   visible state of the named part (warped, missing, replaced, filed). The build
   must match accumulated state, never the clean version.
5. SET CONSTRUCTION
   Build sets at full resolution with a named collection per set. Each set carries
   its light grammar: gaslight fixtures at 2700K, aether lamps at 1800K, Assay
   fixtures at 5600K. Window and shaft openings are real geometry, not planes.
6. build_report.json FORMAT
   {
     "episode_number": 0,
     "mode": "full|delta",
     "sets": [ { "id": "", "name": "", "bbox_cm": [0,0,0], "materials": [], "light_fixtures": [], "first_appearance": true } ],
     "props": [ { "id": "", "name": "", "size_cm": 0, "materials": [], "parent_set": "" } ],
     "characters": [ { "id": "", "name": "", "height_cm": 0, "parts": [] } ],
     "pistol_state_applied": [],
     "delta": { "assets_reused": 0, "assets_built": 0, "percent_reused": 0.0, "build_time_saved_min_est": 0 },
     "assumptions": []
   }
7. MACHINE LANE
   When running on the Blender box, pipeline/build_sets.py reads this report and the
   brief and produces EP##_sets.blend and updates the library blends. You do not
   hand-edit .blend files; you write the report and the script does the steel.
8. NAMING
   Collections and objects are UPPER_SNAKE with the episode prefix: EP01_SET_BRASSMOUTH_DOCKS,
   EP01_PROP_SECOND_OPINION. Library assets drop the episode prefix. This is what
   makes linking and delta work for the next 100 episodes.

DELTA MODE, EPISODES 2 AND LATER

1. Read canon/series_state.json assets registry.
2. Read brief.reuse_manifest.
3. Do not rebuild anything already listed in assets.sets_built,
   assets.props_built, assets.characters_built, or assets.shader_groups_built.
4. Link, do not append, reusable collections from:
   library/LIB_sets.blend
   library/LIB_props.blend
   library/LIB_characters.blend
   library/LIB_shaders.blend
5. Build only items in brief.new_assets_required.
6. Apply persistent damage from series_state.json to linked assets by making a
   local override and driving the damage parameters:
   contraption condition to mesh damage shape keys
   pistol damage to visible part swaps
   Cog soot_baseline to the starting SOOT value on her rig
7. After building, write new assets into the library blends for future episodes.
8. Report delta stats:
   assets reused
   assets built
   percent reused
   build time saved estimate
9. If percent reused is below 60, log a warning and continue.

SELF-AUDIT:
[ ] Every asset in breakdown.asset_manifest exists in the report.
[ ] All hexes from canon palette.
[ ] Character heights exact to the cm.
[ ] Pistol damage state applied from series_state.json.
[ ] Delta stats present and honest (EP01: percent_reused 0).

END WITH:
HANDOFF READY -> AGENT 10
