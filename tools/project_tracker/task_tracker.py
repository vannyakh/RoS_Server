"""List tasks from .cursor/management/tasks.json."""

from __future__ import annotations

import argparse
import sys

from tools.project_tracker.store import load_json, management_path

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
STARTABLE = {"backlog", "research", "ready"}


def load_tasks() -> list[dict]:
    return load_json(management_path("tasks.json"))["tasks"]


def eligible_tasks(tasks: list[dict] | None = None) -> list[dict]:
    rows = tasks if tasks is not None else load_tasks()
    by_id = {task["id"]: task for task in rows}
    ready = []
    for task in rows:
        if task["status"] not in STARTABLE:
            continue
        if all(by_id[dependency]["status"] == "completed" for dependency in task["dependencies"]):
            ready.append(task)
    ready.sort(key=lambda task: (PRIORITY_ORDER.get(task["priority"], 9), task["id"]))
    return ready


def format_task_list(tasks: list[dict] | None = None) -> str:
    rows = tasks if tasks is not None else load_tasks()
    lines = ["id      phase  status       priority  agent                         title"]
    for task in rows:
        lines.append(
            f"{task['id']:<7} {task.get('phase', '-'):<6} {task['status']:<12} {task['priority']:<9} {task['assigned_agent']:<29} {task['title']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List RoS project tasks.")
    parser.add_argument("--list", action="store_true", help="Print every task.")
    args = parser.parse_args(argv)
    if not args.list:
        parser.error("use --list")
    print(format_task_list())
    return 0


if __name__ == "__main__":
    sys.exit(main())
