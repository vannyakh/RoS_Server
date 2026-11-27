# Master roadmap

The phase record is `.cursor/management/milestones.json`. Task status is `.cursor/management/tasks.json`. This page is the map. It does not close a task.

**Current major game goal (Phase 09):** Solo Battle Royale first playable on the original Android APK + `bigworld_gateway/` (LDPlayer): Solo Start → see 9 bots → aircraft → parachute → land. Status checklist: [docs/SOLO_GAMEPLAY_STATUS.md](../SOLO_GAMEPLAY_STATUS.md). Proposed match params (map, warmup, 9→119 bots) are **unverified**. Bot AI is FSM/BT — not LLMs. Map work onto existing `bigworld_gateway/` + `app/`; do not invent a parallel module tree or opcodes.

| Phase | Name | Status | What the registry says |
| --- | --- | --- | --- |
| 00 | Project discovery | in progress | RO-012 and RO-055 completed. RO-035 stays in review. |
| 01 | Original game research | in progress | RO-013–015 recorded. No authorized original protocol checked in. |
| 02 | Architecture | completed | RO-002 and ADR-0001 through ADR-0004. |
| 03 | Database foundation | in progress | RO-009 completed. RO-011 remains in review (not silently closed). |
| 04 | Core game services | in progress | Core routes recorded. RO-018/019 wait on RO-011. |
| 05 | Gameplay engine | in progress | Local simulator recorded. RO-031 match-results evidence in review. |
| 06 | Networking and client compatibility | in progress | 43 features tracked. **0** original-compatible. |
| 07 | Quality and performance | in progress | Locust sample and monitors recorded. RO-037 backlog. |
| 08 | Release and deployment | in progress | RO-045 blocked (Postgres). RO-034 waits on RO-011. |
| 09 | Original-client Solo BR match | in progress | Unit path through static 9 bots done (RO-056–063/068/069/107/108/110; many AC4 live open). Assigned: RO-113 LDPlayer accept + RO-111 bot AI design. Ready next: RO-064 loot research, RO-074, RO-112 scale. |

## Rules that apply to every phase

1. Research is not implementation.
2. Implementation is not original compatibility.
3. A test result counts only when the command output is stored.
4. Changelog rows are permanent history.
5. A checkpoint is the recovery point for the next session.

## Research limits

Use authorized documentation, public sources, user-owned materials, and permitted client analysis. Record the source. Do not bypass authentication, certificate pinning, access controls, or protected services. Do not extract credentials, keys, or tokens. Do not invent undocumented server behavior.
