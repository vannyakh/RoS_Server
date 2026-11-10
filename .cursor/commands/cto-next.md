# CTO next

Read `.cursor/management/tasks.json` and `.cursor/management/workflow.json`.

Select tasks whose dependencies are all `completed` and whose status is `ready`. Reject any candidate whose `files_allowed` overlaps an `assigned` or `in_progress` task.

Print the chosen id, assignee, allowed files, and acceptance criteria from the file. If none are eligible, say which dependency is still open. Do not start the work unless the user asks.
