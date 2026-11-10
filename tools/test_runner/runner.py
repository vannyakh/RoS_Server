"""Discover and run pytest categories without touching the development database."""

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FEATURES = {
    "authentication": "tests/compatibility/authentication",
    "player": "tests/compatibility/player",
    "lobby": "tests/compatibility/lobby",
    "matchmaking": "tests/compatibility/matchmaking",
    "gameplay": "tests/compatibility/gameplay",
    "inventory": "tests/compatibility/inventory",
    "weapons": "tests/compatibility/weapons",
    "match_results": "tests/compatibility/match_results",
}
CATEGORIES = {
    "compatibility": "tests/compatibility",
    "regression": "tests/regression",
    "performance": "tests/performance",
    "unit": "tests/unit",
    "integration": "tests/integration",
    "security": "tests/security",
}


class ResultCollector:
    def __init__(self) -> None:
        self.tests: dict[str, dict] = {}

    def pytest_runtest_logreport(self, report) -> None:
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            self.tests[report.nodeid] = {
                "nodeid": report.nodeid,
                "outcome": report.outcome,
                "duration_s": round(getattr(report, "duration", 0.0), 4),
            }


def refuse_production_database() -> str | None:
    url = os.environ.get("DATABASE_URL", "")
    normalized = url.replace("\\", "/")
    if "ros_server.db" in normalized:
        return "DATABASE_URL points at ros_server.db. Use a disposable database."
    return None


def render_html(payload: dict) -> str:
    rows = []
    for item in payload["tests"]:
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(item["nodeid"]),
                html.escape(item["outcome"]),
                item["duration_s"],
            )
        )
    body = "\n".join(rows) or "<tr><td colspan='3'>No tests</td></tr>"
    return (
        "<!DOCTYPE html><html><head><title>Test report</title></head><body>"
        f"<h1>{html.escape(payload['label'])}</h1>"
        f"<p>passed {payload['passed']}, failed {payload['failed']}, skipped {payload['skipped']}</p>"
        f"<table><thead><tr><th>Test</th><th>Outcome</th><th>Seconds</th></tr></thead><tbody>{body}</tbody></table>"
        "</body></html>"
    )


def write_reports(label: str, payload: dict) -> Path:
    directory = ROOT / "reports" / label
    directory.mkdir(parents=True, exist_ok=True)
    latest = directory / "latest.json"
    if latest.exists():
        (directory / "previous.json").write_bytes(latest.read_bytes())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    serialized = json.dumps(payload, indent=2)
    (directory / f"{stamp}.json").write_text(serialized, encoding="utf-8")
    latest.write_text(serialized, encoding="utf-8")
    page = render_html(payload)
    (directory / f"{stamp}.html").write_text(page, encoding="utf-8")
    (directory / "latest.html").write_text(page, encoding="utf-8")
    return latest


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.test_runner")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--category")
    selector.add_argument("--feature")
    selector.add_argument("--id")
    selector.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    problem = refuse_production_database()
    if problem:
        print(problem, file=sys.stderr)
        return 2
    if args.all:
        target, label = "tests", "all"
    elif args.category:
        if args.category not in CATEGORIES:
            print(f"Unknown category {args.category}", file=sys.stderr)
            return 2
        target, label = CATEGORIES[args.category], args.category
    elif args.feature:
        if args.feature not in FEATURES:
            print(f"Unknown feature {args.feature}", file=sys.stderr)
            return 2
        target, label = FEATURES[args.feature], args.feature
    else:
        target, label = args.id, "id"
    collector = ResultCollector()
    exit_code = int(pytest.main([target, "-q", "--tb=line"], plugins=[collector]))
    tests = list(collector.tests.values())
    payload = {
        "label": label,
        "target": target,
        "exit_code": exit_code,
        "passed": sum(item["outcome"] == "passed" for item in tests),
        "failed": sum(item["outcome"] == "failed" for item in tests),
        "skipped": sum(item["outcome"] == "skipped" for item in tests),
        "tests": tests,
    }
    write_reports(label, payload)
    return exit_code


def main() -> None:
    sys.exit(run())
