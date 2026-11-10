# Team structure

The CTO coordinates eight specialists. Implementation belongs to the specialist named on the task. QA and security review that work. The CTO records completion in `.cursor/management/tasks.json` only after the verification commands have been run.

| Agent | Owns | Does not own |
| --- | --- | --- |
| CTO | Registry, assignment, approval | Feature implementation |
| Backend architect | Module boundaries | Task status changes |
| Database engineer | `app/models` and the engine | Alembic revision files |
| Data migration engineer | `migrations`, seeds, importers | Model design that has no revision |
| API engineer | Schemas, services, repositories, routes | Table definitions |
| QA engineer | `tests` and command output | Marking a task completed |
| Security engineer | A written review under `docs/engineering/reviews` | Application edits |
| DevOps engineer | Compose and operations docs | `.env` and live downgrades |

Agent prompts are `.cursor/agents/*.md`. Cursor loads those as project subagents. Skills are `.cursor/skills/*/SKILL.md`. Rules are `.cursor/rules/*.mdc`.

`team.json` is the identity list. `tasks.json` is the work list. A conversation does not override either file.

Only the CTO edits the two JSON registries. Specialists recommend changes in their task report.
