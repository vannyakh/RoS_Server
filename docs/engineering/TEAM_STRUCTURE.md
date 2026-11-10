# Team structure

The CTO coordinates twelve specialists. Implementation belongs to the specialist named on the task. QA and security review that work. The CTO records completion in `.cursor/management/tasks.json` only after the verification commands have been run.

| Agent | Owns | Does not own |
| --- | --- | --- |
| CTO | Registries, assignment, approval, checkpoints, changelog | Feature implementation and self-approval |
| Backend architect | Module boundaries | Task status changes |
| Database engineer | `app/models` and the engine | Alembic revision files |
| Data migration engineer | `migrations`, seeds, importers | Model design that has no revision |
| API engineer | Schemas, services, repositories, routes | Table definitions |
| QA engineer | `tests` and command output | Marking a task completed |
| Security engineer | A written review under `docs/engineering/reviews` | Application edits |
| DevOps engineer | Compose, operations docs, monitoring docs | `.env` and live downgrades |
| Game compatibility engineer | Compatibility matrix and research index | Original-compatibility claims without a source |
| Protocol test engineer | This server's message tests and network research notes | Official game packets |
| Gameplay test engineer | Deterministic scenarios and gameplay research notes | Original combat values |
| Performance engineer | Locust runs and latency records | Capacity claims without a run |
| Observability engineer | Function logs, metrics, traces | Secrets in metric labels |

Agent prompts are `.cursor/agents/*.md`. Cursor loads those as project subagents. Skills are `.cursor/skills/*/SKILL.md`. Rules are `.cursor/rules/*.mdc`.

`team.json` is the identity list. `tasks.json` is the work list. Discoveries, compatibility, checkpoints, milestones, decisions, and the changelog are the other project records. A conversation does not override any of them.

Only the CTO edits the management JSON registries. Specialists recommend changes in their task report.

Validate both the agent registry and the project-control registries with:

```powershell
python scripts/validate_project_management.py
```
