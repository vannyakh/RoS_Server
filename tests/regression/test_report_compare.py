from tools.report_generator import compare_reports


def test_regression_report_classifies_failures():
    previous = {"tests": [{"nodeid": "tests/compatibility/a.py::test_old", "outcome": "failed"}]}
    current = {
        "tests": [
            {"nodeid": "tests/compatibility/a.py::test_old", "outcome": "passed"},
            {"nodeid": "tests/compatibility/a.py::test_new", "outcome": "failed"},
            {"nodeid": "tests/unit/test_same.py::test_same", "outcome": "failed"},
        ]
    }
    # unchanged needs the previous failure to still fail. Adjust previous.
    previous["tests"].append({"nodeid": "tests/unit/test_same.py::test_same", "outcome": "failed"})
    report = compare_reports(previous, current)
    assert report["fixed_failures"] == ["tests/compatibility/a.py::test_old"]
    assert report["new_failures"] == ["tests/compatibility/a.py::test_new"]
    assert report["unchanged_failures"] == ["tests/unit/test_same.py::test_same"]
    assert report["compatibility_regressions"] == ["tests/compatibility/a.py::test_new"]
