# Task workflow

Statuses move only along the edges in `.cursor/management/workflow.json`.

```text
backlog -> ready -> assigned -> in_progress -> review -> testing -> completed
```

`blocked` can be entered from `ready`, `assigned`, `in_progress`, `review`, or `testing`. A blocked task needs `block_reason` and `resolution_plan`. `cancelled` is terminal.

A task in `ready` or any later active state requires every dependency to be `completed`. The validator rejects a cycle.

## Evidence

A `completed` task carries `completion_report` with the command that was run and the output summary. A specialist report is not enough. Skipped tests stay in `remaining_issues`.

The report body is the `report_template` field in `workflow.json`:

```text
TASK ID:
AGENT:
STATUS:

OBJECTIVE:
IMPLEMENTATION SUMMARY:
FILES CREATED:
FILES MODIFIED:
TESTS EXECUTED:
TEST RESULTS:
SECURITY CONSIDERATIONS:
KNOWN ISSUES:
DEPENDENCIES:
RECOMMENDATION:
```

## File ownership

Before two tasks are `assigned` or `in_progress`, compare `files_allowed`. Overlapping patterns stop the second assignment. `.cursor/management/*.json` stays with the CTO. `migrations/**` stays with the data-migration engineer. `app/models/**` stays with the database engineer.

## History

Every status or assignee change appends `history`: `at`, `actor`, `from_status`, `to_status`, `from_agent`, `to_agent`, and `note`. The first row starts at `from_status: null`.

## Current gate

RO-009 is `ready`. RO-011 is `blocked` until that security review is completed and the suite is run again.
