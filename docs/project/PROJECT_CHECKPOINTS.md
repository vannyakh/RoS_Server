# Project checkpoints

Checkpoints are append-only records in `.cursor/management/checkpoints.json`. A readable copy is written to `reports/checkpoints/`.

Create one with:

```powershell
python -m tools.project_tracker.checkpoint --create
```

Create a checkpoint:

1. After a milestone is completed.
2. Before a major architecture change.
3. Before a database migration change.
4. Before a release.
5. When the user requests one.
6. After an unexpected failure, as a recovery record.

Never overwrite an old checkpoint. The CLI rejects a duplicate checkpoint id.

A checkpoint is not approval of a task. Task completion still requires the verification commands and a `completion_report`.

The latest checkpoint is the recovery point for a new CTO session. Read it before assigning work.
