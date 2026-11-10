"""Compare two machine-readable test reports."""


def compare_reports(previous: dict, current: dict) -> dict:
    before = {item["nodeid"]: item["outcome"] for item in previous.get("tests", [])}
    after = {item["nodeid"]: item["outcome"] for item in current.get("tests", [])}
    new_failures = sorted(node for node, outcome in after.items() if outcome == "failed" and before.get(node) != "failed")
    fixed = sorted(node for node, outcome in before.items() if outcome == "failed" and after.get(node) == "passed")
    unchanged = sorted(node for node, outcome in after.items() if outcome == "failed" and before.get(node) == "failed")
    return {
        "new_failures": new_failures,
        "previously_failing": sorted(node for node, outcome in before.items() if outcome == "failed"),
        "fixed_failures": fixed,
        "unchanged_failures": unchanged,
        "performance_regressions": list(current.get("performance_regressions", [])),
        "compatibility_regressions": [
            node for node in new_failures if "compatibility" in node or "protocol" in node
        ],
    }
