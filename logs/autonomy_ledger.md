# BRASS INITIATIVE — AUTONOMY LEDGER

Every autonomous decision, repair, or deviation from the run order, in the form:

`S##E## — <agent> — DECISION: [what was decided] — REASON: [why] — OUTPUT: [files touched]`

Entries are append-only. A repair loop that exceeds 3 agent attempts becomes an
entry here AND a row in `logs/unresolved.md`.

(Empty until EP01 runs.)
