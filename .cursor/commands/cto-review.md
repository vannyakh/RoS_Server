# CTO review

Read `.cursor/management/tasks.json`. The task id is the argument after this command.

Open the files listed for that task and run its `verification_commands`. Compare the output with `completion_report` or the specialist report. A skipped test is not a pass.

Leave status unchanged when the commands were not run. The implementing agent does not approve the task. Record findings in the registry only as the CTO, then run `python scripts/validate_agent_registry.py`.
