# CTO audit

Run `python scripts/validate_agent_registry.py`.

Then read `.cursor/management/tasks.json` and `.cursor/management/team.json`. Report invalid agents, missing dependencies, cycles, overlapping active files, completed tasks without evidence, and blocked tasks without a resolution plan.

Use the validator output as the result. Do not describe the registry as valid when the command fails.
