# Discovery index

Source of truth: `.cursor/management/discoveries.json`.
A hypothesis stays a hypothesis until a new evidence path is recorded.

## DIS-0001 — No authorized original specification is in the repository

- Category: research
- Confidence: confirmed
- Status: verified
- Source: repository_inspection — testdata/reference/provenance.json
- Evidence: testdata/reference/provenance.json

OBSERVED FACT: testdata/reference/provenance.json says the compatibility matrix was written from inspection of this repository and is not an official Rules of Survival reference.

INTERPRETATION: Local implementation and local tests cannot be promoted to original-game compatibility.

HYPOTHESIS: An authorized specification may exist outside this repository. None is checked in here.

IMPLEMENTATION IMPACT: Every feature stays compatibility_status unknown until a new source and a comparison are recorded.

## DIS-0002 — Development uses SQLite and production settings expect PostgreSQL

- Category: database
- Confidence: confirmed
- Status: verified
- Source: project_documentation — README.md
- Evidence: docs/DATABASE_OPERATIONS.md

OBSERVED FACT: README.md says development uses SQLite. docker-compose.yml defines PostgreSQL and Redis. RO-008 and RO-028 record that test_postgres_account_roundtrip was skipped because POSTGRES_TEST_URL was unset.

INTERPRETATION: Schema portability is intended. A skipped PostgreSQL test is not evidence that production PostgreSQL was executed.

HYPOTHESIS: The same Alembic revision will run on PostgreSQL. That still needs a run with POSTGRES_TEST_URL set.

IMPLEMENTATION IMPACT: Do not claim a PostgreSQL verification. Do not downgrade a database that must be kept.

## DIS-0003 — The wire protocol is this server's JSON protocol

- Category: networking
- Confidence: confirmed
- Status: verified
- Source: project_documentation — README.md
- Evidence: docs/engineering/ARCHITECTURE_DECISIONS.md

OBSERVED FACT: README.md documents version 1 messages auth, lobby.join, player.action, player.input, and state on ws://<host>:8000/api/v1/ws. The architecture record says this is not an official Rules of Survival client protocol.

INTERPRETATION: Protocol tests prove this server's contract. They do not prove that an original game client can connect.

HYPOTHESIS: The original client uses a different interface. That interface is not in this repository.

IMPLEMENTATION IMPACT: Networking work must keep rejecting unknown versions and must not be described as official-client compatibility.

## DIS-0004 — Migration 93510e8bf194 preserves legacy_players

- Category: database
- Confidence: confirmed
- Status: verified
- Source: project_documentation — docs/engineering/ARCHITECTURE_DECISIONS.md
- Evidence: migrations/versions/93510e8bf194_initial_database_schema.py

OBSERVED FACT: docs/engineering/ARCHITECTURE_DECISIONS.md states that revision 93510e8bf194 renames players to legacy_players, copies rows, and does not drop the legacy table on upgrade.

INTERPRETATION: Upgrade is the path for an existing development database. Downgrade is documented for a disposable database.

HYPOTHESIS: None. The preservation rule is already an accepted decision. RO-009 still has to cite the migration file in a security review.

IMPLEMENTATION IMPACT: Do not rewrite revision 93510e8bf194. Do not delete legacy_players or player-owned rows.

## DIS-0005 — Original combat, equipment, and vehicle behavior is unknown

- Category: gameplay
- Confidence: unknown
- Status: investigating
- Source: repository_inspection — testdata/reference/compatibility_matrix.json
- Evidence: testdata/reference/provenance.json

OBSERVED FACT: The compatibility matrix marks GP-002, GP-004, and GP-005 as implemented local behavior with compatibility unknown. GP-007 and GP-008 are not implemented. Provenance says the solo scenario expects pistol damage 22 and speed 5 from this server's own files.

INTERPRETATION: Those numbers are a local contract. They are not an original weapon table.

HYPOTHESIS: The commercial game has different weapon, vehicle, and equipment behavior. No authorized source for those values is in this repository.

IMPLEMENTATION IMPACT: Do not fill equipment or vehicles with guessed original stats. Tests must cite app/game/items.py and app/game/rules.py when they assert local numbers.

## DIS-0006 — No authorized client build is stored in the repository

- Category: client
- Confidence: confirmed
- Status: verified
- Source: repository_inspection — README.md
- Evidence: README.md

OBSERVED FACT: The workspace contains no .apk, .ipa, .pcap, or .so file. README.md describes a browser client at /play for this server.

INTERPRETATION: There is a browser play page for this server. There is no checked-in original mobile client to compare against.

HYPOTHESIS: A user-owned authorized client may be analyzed later under the research rules. That analysis has not started.

IMPLEMENTATION IMPACT: Do not claim the original client can connect. Do not bypass pinning or authentication to obtain a client interface.
