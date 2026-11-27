# RoS Server agents

This file is the shared instruction for Cursor, Claude, GitHub coding agents, and custom agents. Tool-specific files may point here. They do not replace it.

## Read order

1. Read this file.
2. Read `docs/ARCHITECTURE.md` and the architecture page for the module you will change.
3. Inspect the existing code and tests before editing.
4. Plan one module. Implement that module.
5. Run the tests and static checks named by the task.
6. Write an implementation report with command output.
7. Leave merge to a human review.

A chat summary is not completion. A passing local test does not make a feature compatible with original Rules of Survival.

## What this repository is

The running server is one Python FastAPI process. HTTP and WebSocket routes are the control plane. The match loop in `app/game` is the current in-process simulation. The wire format is this project's versioned JSON, documented in `docs/API_CONTRACT.md`.

Original client research stays in `docs/reverse-engineering/`. Research notes are evidence. They are not a server protocol, a packet layout, or an opcode list. Numeric opcodes are unpublished until a reviewed design names and tests them.

## Boundaries

- Implement routes, fields, and message types that already exist in code or in an accepted architecture decision. Add a new contract only in the same change that adds the code and the tests.
- Keep original-client protection work out of this repository. Do not bypass authentication, encryption, certificate pinning, or access controls on an original game client.
- Keep proprietary game binaries, artwork, sounds, and other publisher assets out of this repository. A future MIT license would cover original project code only.
- Write repository-relative paths in rules, skills, and agent files. Leave machine paths and LAN addresses out of those files.
- Do not print secrets, password hashes, raw tokens, or session hashes.
- Do not rewrite an applied Alembic revision, downgrade the live database, or delete player-owned rows.

## Original client gateway

`bigworld_gateway/` was imported from RosGG-Server-v2 by owner decision. It holds the BigWorld Mercury gateway for the original client, its DNS/HTTPS targets, the client APK patch and host-rewrite tools, and Frida inspection scripts. The boundary above about original-client protection work does not apply inside `bigworld_gateway/`. Everything else in this file still does, including no secrets (keys and certificates stay git-ignored) and no proprietary binaries such as the APK. Code in `app/` must not import from `bigworld_gateway/`. The gateway reaches the database only through `/api/v1/gateway` (see `docs/API_CONTRACT.md`), never by opening the SQLite file.

### Sync with RosGG-Server-v2

Another team develops `bigworld_gateway/` in RosGG-Server-v2, and both copies change. Every gateway change moves both ways with `scripts/sync_rosgg_gateway.py`:

- Before editing `bigworld_gateway/`, pull RosGG changes (`status`, then `pull --fetch --ref origin/main`).
- After editing it and passing the gateway tests, `push` the files into the RosGG working tree. A human commits and pushes there. Then `pull` again so `bigworld_gateway/UPSTREAM_SYNC.json` records the new base.
- A file changed on both sides is a conflict. Merge it by hand. Keys, `.env`, captures, logs, `saved_accounts.json` and APKs never cross.
- Only one gateway can serve LDPlayer at a time. Take `tools/ldplayer_lock.ps1` in both copies, and do not stop the other copy's gateway yourself.

The full rule is `.cursor/rules/15-rosgg-sync.mdc`.

## Task registry

Engineering work is coordinated from `.cursor/management/tasks.json`. The CTO agent is the only role that changes task assignment or status.

- Team: `docs/engineering/TEAM_STRUCTURE.md`
- Workflow: `docs/engineering/TASK_WORKFLOW.md`
- Assignment: `docs/engineering/AGENT_ASSIGNMENT_GUIDE.md`
- Decisions: `docs/engineering/ARCHITECTURE_DECISIONS.md`
- Roadmap: `docs/project/MASTER_ROADMAP.md`
- Research: `docs/reverse-engineering/RESEARCH_INDEX.md`
- System shape: `docs/ARCHITECTURE.md`

Specialists are `.cursor/agents/*.md`. Each row in `.cursor/management/team.json` names that specialist's skills and rule. Task status stays in `.cursor/management/tasks.json`. The compatibility team is `game-compatibility-engineer`, `protocol-test-engineer`, `gameplay-test-engineer`, `performance-engineer`, and `observability-engineer`. Ask for one by name, for example `Use the security-engineer subagent for RO-009`. If that delegation does not start, run the same prompt in a separate Agent chat and say that it was manual.

Validate the registries with:

```powershell
python scripts/validate_agent_registry.py
python scripts/validate_project_management.py
python -m tools.project_tracker.project_status
```

Completed tasks need command output in `completion_report`.
