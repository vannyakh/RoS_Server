# RoS Server agents

Engineering work is coordinated from `.cursor/management/tasks.json`. The CTO agent is the only role that changes task assignment or status.

- Team: `docs/engineering/TEAM_STRUCTURE.md`
- Workflow: `docs/engineering/TASK_WORKFLOW.md`
- Assignment: `docs/engineering/AGENT_ASSIGNMENT_GUIDE.md`
- Decisions: `docs/engineering/ARCHITECTURE_DECISIONS.md`
- Roadmap: `docs/project/MASTER_ROADMAP.md`
- Research: `docs/reverse-engineering/RESEARCH_INDEX.md`

Specialists are `.cursor/agents/*.md`. The compatibility team is `game-compatibility-engineer`, `protocol-test-engineer`, `gameplay-test-engineer`, `performance-engineer`, and `observability-engineer`. Ask for one by name, for example `Use the security-engineer subagent for RO-009`. If that delegation does not start, run the same prompt in a separate Agent chat and say that it was manual.

Validate the registries with:

```powershell
python scripts/validate_agent_registry.py
python scripts/validate_project_management.py
python -m tools.project_tracker.project_status
```

Do not treat a chat summary as completion. Completed tasks need command output in `completion_report`. A passing local test does not mark a feature compatible with original RoS.
