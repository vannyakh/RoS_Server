# Task checkpoints

This file is a reading list. It does not assign work and it does not mark work complete.

The server registry is `.cursor/management/tasks.json`. The CTO agent is the only role that changes assignment or status there. A specialist does not edit that file. Completion needs command output in the registry, not a summary in chat.

The client registry is `management/client_tasks.json` in the sibling client repository.

## Rebuild checkpoints

| Order | Checkpoint | State to record |
| --- | --- | --- |
| 1 | Research inventory | Client `research/reports/PHASE-01-REPORT.md` |
| 2 | Independent gameplay rules | This repository's `docs/GAMEPLAY_SYSTEMS.md` plus tests for any new number |
| 3 | Authoritative simulation | Existing `app/game` loop. A separate runtime process needs a new architecture decision. |
| 4 | Gameplay implementation | One system per change, with tests |
| 5 | Two independent clients | Two `com.ros.client` sessions in one match. The original package is not the test client. |
| 6 | Admin and community | Not started. This checkpoint does not create an admin application. |

## Do not start from this file

- A new workspace root
- Empty Python modules that stand in for unfinished systems
- A client patch script or an update-feed config
- Original protocol opcodes
