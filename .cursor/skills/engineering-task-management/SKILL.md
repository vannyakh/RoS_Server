---
name: engineering-task-management
description: Operates the RoS_Server task registry. Use when assigning, blocking, reviewing, or approving tasks in .cursor/management/tasks.json.
---

# Engineering task management

## When

The user invokes a CTO command or asks to assign, block, or close a task.

## Input

`.cursor/management/team.json`, `tasks.json`, and `workflow.json`.

## Workflow

1. Run `python scripts/validate_agent_registry.py`.
2. Select tasks whose dependencies are all `completed`.
3. Reject a start when `files_allowed` overlaps another `assigned` or `in_progress` task.
4. Delegate to the `assigned_agent`. If delegation cannot be started, output the assignment prompt and do not claim it ran.
5. After the report, run the verification commands yourself.
6. Append history: `at`, `actor`, `from_status`, `to_status`, `from_agent`, `to_agent`, `note`.
7. Set `completed` only with a `completion_report` that includes the command output.
8. A `blocked` task needs `block_reason` and `resolution_plan`.

## Checklist

- Registry validates
- Dependencies are completed
- File ownership does not clash
- Evidence is from a command you ran
- History entry appended

## Output

The updated task status and the specialist report.

## Failure

If validation fails, fix the registry before assignment. If a specialist reports success without command output, leave the task in `review`.
