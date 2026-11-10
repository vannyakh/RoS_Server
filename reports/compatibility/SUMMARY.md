# Compatibility summary

Compatibility report
Inspection of this repository on 2026-11-10. Not an official Rules of Survival dataset.

Implementation is not compatibility. A passing local test does not prove original RoS behavior.

Features: 43
Implementation: implemented 29, partial 7, not_implemented 7
Local tests: passing 31, failing 0, not_run 12
Original compatibility: unknown 43

Not implemented:
- AUTH-005 Logout: No logout route revokes AccountSession.
- GP-007 Equipment: Equipment definitions can be stored. The match loop does not equip them.
- GP-008 Vehicles: No vehicle simulation is implemented.
- GP-009 Team state: The live match is free-for-all. Lobby teams are not match teams.
- RS-004 Experience rewards: No experience is granted at match end.
- RS-005 Currency rewards: Currency tables exist. Match completion does not pay them.
- RS-006 Player progression: Progression rows are not written from match results.

Compatible with authorized original behavior:
- none
