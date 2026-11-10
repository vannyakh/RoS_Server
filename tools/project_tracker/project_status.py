"""Project dashboard for the CTO session review."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date

from tools.project_tracker.store import ROOT, load_json, management_path, now_iso
from tools.project_tracker.task_tracker import PRIORITY_ORDER, eligible_tasks

STATUS_DOC = ROOT / "docs" / "project" / "PROJECT_STATUS.md"
WEEKLY_DIR = ROOT / "reports" / "weekly"


def _count(rows: list[dict], field: str) -> Counter:
    return Counter(row.get(field, "missing") for row in rows)


def build_status() -> str:
    tasks = load_json(management_path("tasks.json"))["tasks"]
    milestones = load_json(management_path("milestones.json"))
    discoveries = load_json(management_path("discoveries.json"))["discoveries"]
    features = load_json(management_path("compatibility.json"))["features"]
    checkpoints = load_json(management_path("checkpoints.json"))["checkpoints"]
    changelog = load_json(management_path("changelog.json"))["entries"]
    phase = next(item for item in milestones["phases"] if item["phase"] == milestones["current_phase"])
    by_status = _count(tasks, "status")
    by_priority = _count(tasks, "priority")
    workload = Counter(task["assigned_agent"] for task in tasks if task["status"] in {"assigned", "in_progress", "ready", "research", "review", "blocked"})
    completed = by_status.get("completed", 0)
    implementation = _count(features, "implementation_status")
    compatibility = _count(features, "compatibility_status")
    tests = _count(features, "test_status")
    investigating = [row for row in discoveries if row["status"] in {"new", "investigating"}]
    latest_checkpoint = checkpoints[-1] if checkpoints else None
    latest_change = changelog[-1] if changelog else None
    eligible = eligible_tasks(tasks)
    open_phases = [item for item in milestones["phases"] if item["status"] not in {"completed", "not_started"}]
    lines = [
        "RoS Server project status",
        f"Generated: {now_iso()}",
        "Source of truth: .cursor/management JSON registries",
        "",
        f"Current phase: {phase['phase']} {phase['name']} ({phase['status']})",
        "Open phases: " + ", ".join(f"{item['phase']} {item['name']}" for item in open_phases),
        f"Task progress: {completed} completed of {len(tasks)}",
        "",
        "Tasks by status:",
    ]
    for status, count in sorted(by_status.items()):
        lines.append(f"  {status}: {count}")
    lines.append("")
    lines.append("Tasks by priority:")
    for priority in sorted(by_priority, key=lambda name: PRIORITY_ORDER.get(name, 9)):
        lines.append(f"  {priority}: {by_priority[priority]}")
    lines.append("")
    lines.append("Agent workload (ready, research, assigned, in_progress, review, blocked):")
    for agent, count in sorted(workload.items()):
        lines.append(f"  {agent}: {count}")
    lines.extend(
        [
            "",
            f"Locally implemented features: {implementation.get('implemented', 0)}",
            f"Partial features: {implementation.get('partial', 0)}",
            f"Features still under investigation: {len(investigating)} discoveries",
            f"Original compatibility: {compatibility.get('compatible', 0)} compatible, {compatibility.get('unknown', 0)} unknown",
            f"Failed local tests recorded: {tests.get('failing', 0)}",
            f"Open blockers: {by_status.get('blocked', 0)}",
            "",
            "Latest checkpoint: "
            + (
                f"{latest_checkpoint['checkpoint_id']} {latest_checkpoint['timestamp']}"
                if latest_checkpoint
                else "none"
            ),
            "Latest changelog: "
            + (f"{latest_change['change_id']} {latest_change['title']}" if latest_change else "none"),
            "",
            "Next recommended tasks (dependencies completed):",
        ]
    )
    if not eligible:
        lines.append("  none")
    for task in eligible[:5]:
        lines.append(f"  {task['id']} [{task['priority']}] {task['assigned_agent']}: {task['title']}")
    lines.append("")
    lines.append("Research is not implementation. Implementation is not original compatibility. Testing needs a saved result.")
    return "\n".join(lines)


def weekly_markdown() -> str:
    tasks = load_json(management_path("tasks.json"))["tasks"]
    discoveries = load_json(management_path("discoveries.json"))["discoveries"]
    features = load_json(management_path("compatibility.json"))["features"]
    completed = [task for task in tasks if task["status"] == "completed"]
    blocked = [task for task in tasks if task["status"] == "blocked"]
    lines = [
        f"# Weekly CTO review — {date.today().isoformat()}",
        "",
        "This report is generated from the registries. It does not change task status.",
        "",
        "## Completed tasks",
        "",
    ]
    lines.extend(f"- {task['id']} {task['title']}" for task in completed)
    lines.extend(["", "## Discoveries still open", ""])
    open_rows = [row for row in discoveries if row["status"] in {"new", "investigating"}]
    lines.extend(f"- {row['discovery_id']} {row['title']} ({row['confidence']})" for row in open_rows)
    lines.extend(["", "## Compatibility", ""])
    unknown = sum(1 for feature in features if feature["compatibility_status"] == "unknown")
    lines.append(f"- {unknown} of {len(features)} tracked features remain unknown against original RoS.")
    lines.append("- No feature is marked compatible.")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {task['id']} {task['title']}: {task.get('block_reason')}" for task in blocked)
    lines.extend(["", "## Next priorities", ""])
    for index, task in enumerate(eligible_tasks(tasks)[:5], start=1):
        lines.append(f"{index}. {task['id']} {task['title']} — {task['assigned_agent']}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the RoS project dashboard.")
    parser.add_argument("--write", action="store_true", help="Write docs/project/PROJECT_STATUS.md")
    parser.add_argument("--weekly", action="store_true", help="Write reports/weekly/<date>.md")
    args = parser.parse_args(argv)
    report = build_status()
    print(report)
    if args.write:
        STATUS_DOC.parent.mkdir(parents=True, exist_ok=True)
        STATUS_DOC.write_text("# Project status\n\n```text\n" + report + "\n```\n", encoding="utf-8")
        print(f"Wrote {STATUS_DOC.relative_to(ROOT)}")
    if args.weekly:
        WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
        path = WEEKLY_DIR / f"{date.today().isoformat()}.md"
        path.write_text(weekly_markdown(), encoding="utf-8")
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
