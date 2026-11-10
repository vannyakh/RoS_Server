# Regression guide

`tools.report_generator.compare_reports` compares two runner JSON files.

| Field | Meaning |
| --- | --- |
| new_failures | Failed now, and not failed in the previous report |
| previously_failing | Failed in the previous report |
| fixed_failures | Failed before and passed now |
| unchanged_failures | Failed in both reports |
| performance_regressions | Names copied from the current report's `performance_regressions` list |
| compatibility_regressions | New failures whose node id contains `compatibility` or `protocol` |

`tests/regression/test_report_compare.py` checks that classification. `tests/regression/test_runner.py` checks the production-database guard and a real `--feature player` run.

The CTO does not mark a feature complete when its regression command exits non-zero. There is no saved history of a previously failing suite in this checkout, so this document does not list fixed or unchanged product failures.
