# Unknown behavior

The following original behaviors have no authorized source in this repository. They stay unknown.

- Original account, session, and logout behavior.
- Original profile, level, experience, and progression formulas.
- Original lobby, team, and matchmaking rules.
- Original maps, zones, and match duration.
- Original weapon, damage, equipment, and vehicle values.
- Original reward and currency rules.
- Original client packet formats.

Local behavior that exists here is still not original behavior:

- Logout revokes one stored session. Original logout is unknown.
- A development buggy uses speed 12. Original vehicles are unknown.
- Equipment is not equipped by the match loop.
- Live team state is not copied from the durable lobby into the match.
- Experience, currency, and progression rows are not written at match end.

Add a discovery before treating any original line as known. A local test does not raise that confidence.
