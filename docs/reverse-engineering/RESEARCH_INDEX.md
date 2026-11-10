# Research index

Source of truth for discoveries: `.cursor/management/discoveries.json`.

No authorized original Rules of Survival specification, client build, or packet capture is in this repository. That is DIS-0001 and DIS-0006.

| Discovery | Confidence | Status | What is known |
| --- | --- | --- | --- |
| DIS-0001 | confirmed | verified | The compatibility matrix is a repository inspection, not an official dataset. Source: `testdata/reference/compatibility_matrix.json`. |
| DIS-0002 | confirmed | verified | Development uses SQLite. PostgreSQL is the intended production target and was not executed. Source: `docs/DATABASE_OPERATIONS.md`. |
| DIS-0003 | confirmed | verified | The WebSocket messages in the README are this server's JSON protocol. Source: `README.md` and `app/networking/protocol.py`. |
| DIS-0004 | confirmed | verified | Revision `93510e8bf194` preserves `legacy_players`. Source: `docs/architecture/decisions/ADR-0004-legacy-players.md`. |
| DIS-0005 | unknown | investigating | Original combat, equipment, and vehicle behavior is not sourced. Local numbers live in `app/game/rules.py` and `app/game/items.py`. |
| DIS-0006 | confirmed | verified | No APK, IPA, packet capture, or native library is stored here. Source: repository file listing recorded in the Phase 00 baseline. |
| DIS-0007 | confirmed | verified | The Phase 00 Locust run timed out after 4 HTTP requests and 0 HTTP failures. Source: `reports/project-audit/BASELINE_REPORT.md`. |
| DIS-0008 | high | investigating | A public Steam operations notice describes a June 27, 2022 shutdown. It is not a protocol. Source: `https://steamcommunity.com/app/788260/allnews/`. |
| DIS-0009 | high | verified | The Locust timeout cleared after server output was written to a file. The auth timeout stayed 3 seconds. Source: `reports/phase-01/PHASE-01_REPORT.md`. |
| DIS-0010 | confirmed | verified | Two logins in one second shared a session hash until each token included `jti`. Source: `tests/integration/test_auth_session.py`. |
| DIS-0011 | high | verified | A public search on 2026-11-10 did not return an authorized client protocol. Shutdown notices and one unofficial forum page were not used as packet sources. |

## How to add a finding

1. Record the source path and version.
2. Write the observed fact separately from the interpretation and the hypothesis.
3. Leave confidence at `unknown` until the evidence supports a higher level.
4. Ask the CTO to append the discovery. Do not edit `discoveries.json` from a specialist task.

Confirmed facts and hypotheses stay in separate sentences. Missing original behavior stays unknown.
