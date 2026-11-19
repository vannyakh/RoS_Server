# Task workflow

Statuses move only along the edges in `.cursor/management/workflow.json`.

```text
backlog -> research -> ready -> assigned -> in_progress -> review -> testing -> completed
backlog -> ready -> assigned -> in_progress -> review -> testing -> completed
```

`research` is for investigation before a task is ready to implement. It still requires completed dependencies. `blocked` can be entered from `ready`, `assigned`, `in_progress`, `review`, or `testing`, and from `research`. A blocked task needs `block_reason` and `resolution_plan`. `cancelled` is terminal.

A task in `research`, `ready`, or any later active state requires every dependency to be `completed`. The validator rejects a cycle.

## Evidence

A `completed` task carries `completion_report` with the command that was run and the output summary. A specialist report is not enough. Skipped tests stay in `remaining_issues`.

The report body is the `report_template` field in `workflow.json`. It asks for the phase, discoveries, database changes, API changes, game-function changes, and compatibility evidence in addition to the files and test results. The stored `completion_report` still uses `summary`, `files_changed`, `tests_executed`, `test_results`, `migration_results`, `review_findings`, and `remaining_issues`.

## File ownership

Before two tasks are `assigned` or `in_progress`, compare `files_allowed`. Overlapping patterns stop the second assignment. `.cursor/management/*.json` stays with the CTO. `migrations/**` stays with the data-migration engineer. `app/models/**` stays with the database engineer.

## History

Every status or assignee change appends `history`: `at`, `actor`, `from_status`, `to_status`, `from_agent`, `to_agent`, and `note`. The first row starts at `from_status: null`.

## Current gate

The live list is `tasks.json`. RO-009, RO-012, RO-016, RO-029, RO-032, RO-033, and RO-055 are completed. RO-030 is in review. RO-011 is ready for the integration review. RO-035 stays in review. RO-045 is blocked on an isolated PostgreSQL run. Backlog tasks stay backlog until every dependency is completed.
