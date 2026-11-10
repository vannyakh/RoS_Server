# CTO plan

Read `.cursor/management/tasks.json`, `.cursor/management/team.json`, and `.cursor/management/workflow.json`.

Inspect the repository only where the registry is silent. Propose new tasks with unique `RO-` ids, dependencies, `files_allowed`, and acceptance criteria. Do not invent status for tasks already in the file.

Do not implement game features. Leave the registry unchanged unless the user asked to add the proposed tasks. Run `python scripts/validate_agent_registry.py` after any edit.
