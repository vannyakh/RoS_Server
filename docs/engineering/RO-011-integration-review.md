# RO-011 CTO integration review

Task: RO-011  
Reviewer: CTO  
Phase: 03, Database foundation  
Review status: submitted for QA review

## Scope and findings

The database security review exists at `docs/engineering/reviews/RO-009-security.md`. It recommends approval and identifies three medium follow-ups: missing-user login skips password verification, operator login has no failure limit, and token failures for an inactive account use a different 401 detail. The report also notes legacy password hashes were not re-checked against live rows and that downgrading the initial schema drops the new player-owned tables.

The full suite was rerun after that review. It found a failure in `tests/integration/test_operator_refresh.py::test_refresh_refuses_player_revoked_and_missing_tokens`: operator login raised `sqlite3.OperationalError: attempt to write a readonly database` while updating `operators.last_login_at`. This needs investigation before database integration can be considered clean. The run also skipped one PostgreSQL test because `POSTGRES_TEST_URL` is unset; PostgreSQL behavior remains unverified.

## Verification

- `.\\.venv\\Scripts\\python.exe -m pytest tests -q --tb=line` — **failed**: 1 failed, 224 passed, 1 skipped, 6 warnings in 271.40s. Failure: read-only SQLite database during operator login in the test above.
- `python scripts/validate_agent_registry.py` — **passed**: `OK: 13 agents, 86 tasks`.
- `python scripts/validate_project_management.py` — **passed**: `OK: 86 tasks, 12 discoveries, 43 compatibility features`.

## Next step

Have QA review this result and investigate why the operator refresh integration test's SQLite database is read-only. After resolving the test environment or defect, rerun the full suite. Keep the PostgreSQL check explicitly open until a disposable `POSTGRES_TEST_URL` run is available. Phase 03 remains open; original-game research in Phase 01 is a separate milestone.

## Change scope

No application code, tests, migrations, or database rows were changed for this review. No original-client compatibility claim is made.
