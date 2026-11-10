# Master roadmap

The phase record is `.cursor/management/milestones.json`. Task status is `.cursor/management/tasks.json`. This page is the map. It does not close a task.

| Phase | Name | Status | What the registry says |
| --- | --- | --- | --- |
| 00 | Project discovery | in progress | RO-001 is complete. RO-012, the project-control tracker, is in review. |
| 01 | Original game research | in progress | No authorized original specification is checked in. RO-013 is ready. |
| 02 | Architecture | completed | RO-002 and ADR-0001 through ADR-0004. |
| 03 | Database foundation | in progress | Models, revision `93510e8bf194`, imports, and database QA are recorded. RO-009 is ready. RO-011 is blocked. |
| 04 | Core game services | in progress | Schemas and services exist. Logout, rewards, and lobby gaps wait on RO-011. |
| 05 | Gameplay engine | in progress | The local simulator is recorded. Original combat values are unknown. |
| 06 | Networking and client compatibility | in progress | 43 features are tracked. 0 are compatible with original RoS. |
| 07 | Quality and performance | completed | Runner, function tracker, Locust sample, monitoring docs, and regression reports are recorded. |
| 08 | Release and deployment | in progress | Operations are documented. Release readiness waits on RO-011. |

## Rules that apply to every phase

1. Research is not implementation.
2. Implementation is not original compatibility.
3. A test result counts only when the command output is stored.
4. Changelog rows are permanent history.
5. A checkpoint is the recovery point for the next session.

## Research limits

Use authorized documentation, public sources, user-owned materials, and permitted client analysis. Record the source. Do not bypass authentication, certificate pinning, access controls, or protected services. Do not extract credentials, keys, or tokens. Do not invent undocumented server behavior.
