# RO-028 compatibility review

Reviewed on 2026-11-10 from `testdata/reference/compatibility_matrix.json` and the pytest run.

- 43 functions are tracked.
- 26 are implemented, 10 are partial, and 7 are not implemented.
- 30 have a passing test cited. 13 have no test run.
- 0 are marked `compatible`. 43 are `unknown`.

No authorized original Rules of Survival specification is in the repository. Local scenario, protocol, and HTTP tests are evidence for this server's rules only.

`audit()` from `tools.compatibility_checker` reports no false compatible claims. The full suite was `54 passed, 1 skipped`. The skip is `test_postgres_account_roundtrip` because `POSTGRES_TEST_URL` is unset.

RO-009, the account and migration security review, is still `ready`. This review does not close it.

Load evidence is the 2-user Locust sample in `docs/performance/PERFORMANCE_BASELINE.md`. It is not a capacity claim.
