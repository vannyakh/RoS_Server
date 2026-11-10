---
name: security-audit
description: Reviews authentication, token storage, schema exposure, importer safety, and migration data loss for RoS_Server. Use before approving account, session, import, or migration work.
---

# Security audit

## When

The task's `review_agents` includes `security-engineer`, or the change touches accounts, sessions, imports, or migrations.

## Input

The changed files. Read them. Do not rely on a summary.

## Workflow

1. Check `app/models/account.py` for hash columns and status values.
2. Check response schemas for `password_hash` and `token_hash`.
3. Check `app/core/security.py` for Argon2 passwords and SHA-256 token hashes.
4. Check the importer skips existing accounts and does not write plaintext passwords.
5. Check the migration upgrade does not drop `legacy_players`.
6. Write findings as `critical`, `high`, or `medium`, each with a file path.
7. Write only the review report path named by the task.

## Checklist

- Hashes are not in API responses
- Secrets are not in the report
- Legacy copy is non-destructive
- Each finding cites a file

## Output

A review report and the task report. Recommendation is `approve` or `return`.

## Failure

If a file cannot be read, say so. Do not fill the gap with an assumption. Do not patch the code in this skill.
