---
name: testing-and-validation
description: Runs and extends pytest coverage for models, migrations, imports, and API regression. Use when verifying a task or adding tests under tests/.
---

# Testing and validation

## When

A task reaches testing, or a change needs a regression test.

## Input

The task's `verification_commands` and the files it changed.

## Workflow

1. Run the full suite unless the task names a narrower command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --tb=line
```

2. For a migration change, run `tests/migrations` against a temporary database. Do not point it at `ros_server.db`.
3. For registry edits, run `python scripts/validate_agent_registry.py`.
4. Record passed, failed, and skipped counts. Name the skipped test and the missing condition.
5. PostgreSQL counts as executed only when `POSTGRES_TEST_URL` is set and the test does not skip.

## Checklist

- Command and exit code recorded
- Skip reason recorded
- New constraint has a failing-then-passing test
- Production database file was not used

## Output

The task report fields `TESTS EXECUTED` and `TEST RESULTS`, copied from the command output.

## Failure

On failure, leave status at `testing` or return it to `in_progress` through the CTO. Do not edit production code inside a QA-only task.
