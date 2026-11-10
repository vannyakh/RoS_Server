# Game functions

Local functions are tracked in `testdata/reference/compatibility_matrix.json` and `.cursor/management/compatibility.json`. Read those files for the current counts. Do not reuse an older 26/10/7 summary.

OBSERVED FACT: On-foot speed is 5 in `app/game/rules.py`. Pistol damage is 22 and rifle damage is 16 in `app/game/items.py`. The development buggy speed is 12 in the same items file and applies only while boarded. ADR-0009 records that split.

OBSERVED FACT: Match results in memory store player id, kills, win, and placement. They do not store experience or currency. Source: `app/game/state.py`.

INTERPRETATION: Those are local contracts. A passing scenario test shows this server followed its own rule.

HYPOTHESIS: Original weapon, map, zone, vehicle, and reward values differ. No authorized source for them is in the repository.

IMPLEMENTATION IMPACT: Equipment stays unimplemented. The local buggy is not an original vehicle table. Do not invent original reward values.
