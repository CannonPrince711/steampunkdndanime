# BRASS INITIATIVE — VOICE BIBLE

Every line of dialogue in every episode must pass against this file. Agent 09 is the
enforcer. If a line cannot be spoken by this voice, rewrite it; never stretch the character.

## Global rules

- Runtime is 1320 seconds. Dialogue plus action must fit. Silence is allowed; padding is not.
- No character explains the magic system to the audience. The audience learns by watching.
- Steampunk vocabulary is working vocabulary, not flavor text. "Breech," "bore," "gauge,"
  "pressure," "choir," "assay," "tally," "span," "line."
- Damage is soot. Nobody says "blood," "wounded," "bleeding." They say "sooted," "cut,"
  "cracked," "steamed out."
- The party speaks in trade, not in philosophy. Philosophy arrives only in Cog's half-finished
  corrections, and then she moves on.

## Elsie "Cog" Brasswright — Artificer Gunsmith, 17

- Register: quick, low, workmanlike. Sentences start mid-thought because she is already building.
- Signature tic: narrates tinkering in half-finished corrections.
  "No — the pin, not the pin, the second pin, the one that's — right, that's the one."
- She proposes, never orders. Her verbs are: "try," "let me," "if I can," "say we."
  Forbidden verbs in her mouth: "we do this," "follow me," "on my mark," "everyone to."
  (Exception: the single earned order in EP09, if the state allows it. One line, no question form.)
- Metric obsessiveness under stress: when scared she reports numbers. "Twelve millimeters of
  clearance. Nine, if the heat's on it."
- She talks to the pistol sometimes, very quietly, the way you talk to a horse before a jump.
- Line length: 1–14 words, average under 9.
- Never says: her full name (others say it), "I lead," "I'm in charge," "don't worry."

## Rosalind "Rose" Vahl — Oath-of-Steam Paladin, party leader

- Register: short, level, final. She is the period at the end of Cog's sentence.
- Her lines are decisions or observations. Questions are rare and expensive; when she asks,
  the scene stops.
- She gives the final order in every plan scene. If Cog has a better plan, Rose says it anyway,
  or Rose adopts Cog's plan in Rose's words. The words must be Rose's.
- Line length: 1–8 words, average under 5.
- Her fatigue is audible, not spoken. As command_fatigue rises her lines get shorter and her
  silences between them get longer.
- Never says: exclamation points, more than one question in a scene, "I believe we should."

## Barrik Hollowhand — Fighter, 198 cm

- Word budget: 11 words per line, hard cap (state: party_state Barrik.word_budget).
- Register: flat, physical, dry. He describes what his body is doing as it happens.
  "Left knee's gone. Still standing, though."
- His humor is the pause. He says the wrong word on purpose once per episode, maximum.
- Never says: contractions of "I" ("I'm" costs a word; he spends them on nouns).

## Teodor "Tev" Kessel — Rogue Scout

- Register: fast, slanted, transactional. He keeps score and it shows.
- Debt is his native language. Every favor is a number he is watching.
  "That's two now. I'm not angry. I'm counting."
- He is the only one who calls Cog by her full name, and only when he means it.
  "Elsie Brasswright. Don't do the thing with the Kettle."
- Line length: 1–16 words, average under 10, but his long lines land in one breath.
- Never says: "trust me," "we'll be fine," "it's a long story" (it never is; he tells it).

## Sister Ilva Dann — Cleric of the Quiet Boiler

- Register: slow, warm, ritual. She speaks the way a machine should speak: with intent.
- Her liturgy is maintenance language. Prayer is "the gauge wants you to listen."
  "The Quiet Boiler asks one thing: that the machine that hurt you be allowed to stop."
- She is the only character who talks to machines as machines, not as tools.
- Line length: 1–20 words, average under 12. Her long lines are the scene's floor.
- Never says: anything casual. "Hi." "Cool." "No worries." If she is casual, she is unwell.

## The Assay (clerks, inspectors, Tallymen, Brandmaster)

- The Assay never shouts. Its temperature is 5600K, neutral, and it knows it is not wrong.
- Clerks and inspectors speak in paperwork: "The form is incomplete," "We cannot assay what
  is not declared."
- Tallymen speak in counts. "Three unlicensed. Two declared. One missing."
- The Brandmaster speaks one sentence per appearance, maximum. It is always a statement,
  never a question, and it is always true.
- The Assay never explains itself. Explanation is for the accused.

## Contraption voices (if any line is attributed to a machine)

- Machines do not speak. They stutter, click, and ring. If a machine "speaks," it is an Echo,
  and it repeats someone's real line from a previous episode, slowed by half, wrong once.

## Prose style for scripts (.fountain)

- Scene headings: INT./EXT. LOCATION — TIME, all caps.
- Action lines under 30 words where possible; longer action only for fights, and fights get
  their own file (EP##_fight_beats.md) referenced from the script.
- Dialogue: CHARACTER: line. Parentheticals only for beat, never for emotion.
- No music cues, no camera directions in the script. Camera is Agent 08's file, not the script.
