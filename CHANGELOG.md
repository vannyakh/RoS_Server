# Changelog

The source of truth is `.cursor/management/changelog.json`.
Released sections are historical records. Rendering this file does not delete them.

## [Unreleased]

### Added

- CH-0005 Add durable lobby leave, ready, and database readiness. Members can leave a durable lobby and set ready or unready. GET /health stays {status: ok}. GET /ready checks the database. Original lobby behavior stays unknown. Task: RO-043.
- CH-0006 Add durable inventory, team leave, and stored match lifecycle. Authenticated players can change stored stacks and currency, leave a team without leaving the lobby, and create, cancel, or finalize a stored match. Live matches stay on /matches. No original reward values were added. Task: RO-048.

### Documentation

- CH-0001 Add project-control registries. Checkpoints, discoveries, compatibility, milestones, decisions, and changelog records were added beside the existing task registry. RO-001 through RO-028 were kept. No feature was marked compatible with original RoS. Task: RO-012.
- CH-0002 Record the Phase 00 baseline. Specialist audits and the baseline report were added. Pytest returned 1 failed, 64 passed, 1 skipped. No server module was changed and no feature was marked compatible. Task: RO-035.
- CH-0008 Record the client research boundary. Research pages now separate this server's JSON contract from original behavior. A public search found no authorized protocol. The parser is tested against the documented message and action names. Task: RO-014.

### Fixed

- CH-0004 Stop the Locust run from blocking on unread server output. The load test writes the server log to a file and the client reports auth success, rejection, or the existing 3 second timeout. The rerun passed. Task: RO-041.

### Gameplay

- CH-0007 Add a local buggy without changing on-foot combat. A player can board a development buggy and move at speed 12. Shooting is rejected until exit. On-foot speed stays 5. Results still record placement and kills only. Task: RO-050.

### Performance

- CH-0009 Refresh the short load sample and the release status. The Locust profile passed again with 77 requests and 0 failures. The baseline now cites that row. Release remains blocked: Docker returned an engine error and PostgreSQL was not executed. Task: RO-053.

### Security

- CH-0003 Enforce stored sessions on HTTP and WebSocket. Logout revokes the presented session hash. Both entry points reject a missing, revoked, or expired row. New tokens include a unique jti. Argon2 and JWT expiration checks are unchanged. Task: RO-039.
