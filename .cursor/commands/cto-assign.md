# CTO assign

Read `.cursor/management/tasks.json` and `.cursor/management/team.json`. The task id is the argument after this command.

Confirm the id exists, its dependencies are `completed`, and its files do not overlap another `assigned` or `in_progress` task. Delegate to the `assigned_agent` subagent with that task's `files_allowed` and acceptance criteria.

If delegation cannot be started, print a self-contained prompt for a separate Agent chat and do not claim the agent ran. Append a history row only after the assignment actually changes, then run `python scripts/validate_agent_registry.py`.
