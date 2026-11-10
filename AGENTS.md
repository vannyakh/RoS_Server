# RoS Server agents

Engineering work is coordinated from `.cursor/management/tasks.json`. The CTO agent is the only role that changes task assignment or status.

- Team: `docs/engineering/TEAM_STRUCTURE.md`
- Workflow: `docs/engineering/TASK_WORKFLOW.md`
- Assignment: `docs/engineering/AGENT_ASSIGNMENT_GUIDE.md`
- Decisions: `docs/engineering/ARCHITECTURE_DECISIONS.md`

Specialists are `.cursor/agents/*.md`. The compatibility team is `game-compatibility-engineer`, `protocol-test-engineer`, `gameplay-test-engineer`, `performance-engineer`, and `observability-engineer`. Ask for one by name, for example `Use the security-engineer subagent for RO-009`. If that delegation does not start, run the same prompt in a separate Agent chat and say that it was manual.

Validate the registry with:

```powershell
python scripts/validate_agent_registry.py
```

Do not treat a chat summary as completion. Completed tasks need command output in `completion_report`.
