"""Append-only project checkpoints and their Markdown reports."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter

from tools.project_tracker.store import ROOT, append_unique, atomic_write, load_json, management_path, now_iso
from tools.project_tracker.task_tracker import eligible_tasks

REPORT_DIR = ROOT / "reports" / "checkpoints"


def load_checkpoints() -> dict:
    return load_json(management_path("checkpoints.json"))


def next_checkpoint_id(document: dict) -> str:
    numbers = []
    for row in document.get("checkpoints", []):
        numbers.append(int(str(row["checkpoint_id"]).split("-")[1]))
    return f"CP-{max(numbers, default=0) + 1:04d}"


def _git() -> tuple[str | None, list[str]]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return None, ["git status unavailable"]
    files = []
    for line in status.splitlines():
        path = line[3:].strip() if len(line) > 3 else line.strip()
        lowered = path.lower()
        if ".env" in lowered or lowered.endswith(".db"):
            files.append("[sensitive path omitted]")
            continue
        files.append(path)
    if len(files) > 80:
        files = files[:80] + [f"... {len(status.splitlines()) - 80} more paths omitted"]
    return commit or None, files


def build_checkpoint() -> dict:
    tasks = load_json(management_path("tasks.json"))["tasks"]
    milestones = load_json(management_path("milestones.json"))
    features = load_json(management_path("compatibility.json"))["features"]
    changelog = load_json(management_path("changelog.json"))["entries"]
    by_status: dict[str, list[str]] = {}
    for task in tasks:
        by_status.setdefault(task["status"], []).append(task["id"])
    phase = next(item for item in milestones["phases"] if item["phase"] == milestones["current_phase"])
    implementation = Counter(feature["implementation_status"] for feature in features)
    tests = Counter(feature["test_status"] for feature in features)
    compatibility = Counter(feature["compatibility_status"] for feature in features)
    commit, modified = _git()
    latest_change = changelog[-1]["change_id"] if changelog else None
    ro028 = next((task for task in tasks if task["id"] == "RO-028" and task.get("completion_report")), None)
    test_summary = (
        "No new suite was run for this checkpoint. Last recorded suite on RO-028: "
        + ro028["completion_report"]["test_results"]
        if ro028
        else "No suite result is recorded on RO-028."
    )
    risks = [
        "No authorized original Rules of Survival specification is in the repository.",
        "RO-009 must finish before the database foundation can be accepted.",
    ]
    seen_issues: set[str] = set()
    for task in tasks:
        for issue in (task.get("completion_report") or {}).get("remaining_issues") or []:
            if issue not in seen_issues:
                seen_issues.add(issue)
                risks.append(f"{task['id']}: {issue}")
    ro020 = next((task for task in tasks if task["id"] == "RO-020" and task.get("completion_report")), None)
    recorded = (ro020 or {}).get("completion_report", {}).get("summary", "")
    current_counts = (
        implementation.get("implemented", 0),
        implementation.get("partial", 0),
        implementation.get("not_implemented", 0),
    )
    if "26 are implemented, 10 partial, and 7 not implemented" in recorded and current_counts != (26, 10, 7):
        risks.append(
            "RO-020's stored summary says 26 implemented, 10 partial, and 7 not implemented. "
            f"The current compatibility file has {current_counts[0]} implemented, {current_counts[1]} partial, "
            f"and {current_counts[2]} not implemented. The stored task report was left unchanged."
        )
    eligible = [task["id"] for task in eligible_tasks(tasks)]
    blocked = by_status.get("blocked", [])
    gaps = [
        f"{feature['feature_id']} {feature['feature_name']} is not implemented. {feature['known_differences']}"
        for feature in features
        if feature["implementation_status"] == "not_implemented"
    ]
    return {
        "checkpoint_id": next_checkpoint_id(load_checkpoints()),
        "checkpoint_name": f"{phase['name']} snapshot",
        "timestamp": now_iso(),
        "current_phase": milestones["current_phase"],
        "overall_status": (
            f"Phase {milestones['current_phase']} {phase['name']} is {phase['status']}. "
            f"{len(by_status.get('completed', []))} tasks completed, {len(blocked)} blocked, "
            f"{compatibility.get('compatible', 0)} features compatible with authorized original behavior."
        ),
        "completed_tasks": by_status.get("completed", []),
        "in_progress_tasks": by_status.get("in_progress", []),
        "blocked_tasks": blocked,
        "next_tasks": eligible[:5],
        "completed_features": [feature["feature_id"] for feature in features if feature["implementation_status"] == "implemented"],
        "incomplete_features": [feature["feature_id"] for feature in features if feature["implementation_status"] != "implemented"],
        "compatibility_summary": (
            f"Local implementation: {implementation.get('implemented', 0)} implemented, "
            f"{implementation.get('partial', 0)} partial, {implementation.get('not_implemented', 0)} not implemented. "
            f"Local tests: {tests.get('passing', 0)} passing, {tests.get('failing', 0)} failing, {tests.get('not_run', 0)} not run. "
            f"Original compatibility: {compatibility.get('unknown', 0)} unknown, {compatibility.get('compatible', 0)} compatible. "
            "Passing local tests are not original-behavior proof."
        ),
        "test_summary": test_summary,
        "known_bugs": [
            "RO-011 is blocked because RO-009 has no security review report.",
            *gaps,
        ],
        "architecture_changes": [
            "No server architecture decision was changed.",
            f"Latest changelog row: {latest_change}.",
        ],
        "database_changes": ["No migration was added. Head remains 93510e8bf194."],
        "modified_files": modified,
        "git_commit": commit,
        "risks": risks,
        "next_actions": [
            "Run the security-engineer on RO-009 and cite the files that were read.",
            "Start RO-013 and separate confirmed repository facts from unknown original behavior.",
            "Keep RO-011 blocked until RO-009 is completed and the suite is run again.",
            "After RO-013, research client interfaces (RO-014) and game functions (RO-015) from permitted sources only.",
            "Do not mark any feature compatible from a local test.",
        ],
        "created_by": "cto",
    }


def render_markdown(checkpoint: dict) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "- none"

    return "\n".join(
        [
            "# RoS Server — Checkpoint",
            "",
            f"# {checkpoint['checkpoint_id']}",
            "",
            "Registry snapshot. Task status comes from `.cursor/management/tasks.json`.",
            "",
            f"Timestamp: {checkpoint['timestamp']}",
            f"Current phase: {checkpoint['current_phase']} — {checkpoint['checkpoint_name']}",
            "",
            checkpoint["overall_status"],
            "",
            "## Completed tasks",
            "",
            bullets(checkpoint["completed_tasks"]),
            "",
            "## In progress",
            "",
            bullets(checkpoint["in_progress_tasks"]),
            "",
            "## Blocked",
            "",
            bullets(checkpoint["blocked_tasks"]),
            "",
            "## Next actions",
            "",
            "\n".join(f"{index}. {item}" for index, item in enumerate(checkpoint["next_actions"], start=1)),
            "",
            "## Compatibility",
            "",
            checkpoint["compatibility_summary"],
            "",
            "## Tests",
            "",
            checkpoint["test_summary"],
            "",
            "## Recorded gaps",
            "",
            bullets(checkpoint["known_bugs"]),
            "",
            "## Architecture and database",
            "",
            bullets(checkpoint["architecture_changes"]),
            bullets(checkpoint["database_changes"]),
            "",
            "## Risks",
            "",
            bullets(checkpoint["risks"]),
            "",
            "## Required evidence",
            "",
            f"- Git commit: {checkpoint['git_commit'] or 'unavailable'}",
            "- Migration revision: 93510e8bf194 (unchanged by this checkpoint)",
            "- Registry validation: `python scripts/validate_project_management.py`",
            f"- Changed file list: {len(checkpoint['modified_files'])} paths recorded in the JSON checkpoint",
            "- CTO approval: this checkpoint is a recovery record, not completion of RO-012",
            "",
        ]
    )


def create_checkpoint() -> dict:
    document = load_checkpoints()
    checkpoint = build_checkpoint()
    append_unique(document, "checkpoints", checkpoint, "checkpoint_id")
    document["updated_at"] = checkpoint["timestamp"]
    atomic_write(management_path("checkpoints.json"), document)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORT_DIR / f"{checkpoint['checkpoint_id']}.md"
    report.write_text(render_markdown(checkpoint), encoding="utf-8")
    return checkpoint


def format_latest() -> str:
    rows = load_checkpoints().get("checkpoints", [])
    if not rows:
        return "No checkpoints."
    latest = rows[-1]
    return f"{latest['checkpoint_id']} {latest['timestamp']} phase {latest['current_phase']} — {latest['checkpoint_name']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or show a project checkpoint.")
    parser.add_argument("--create", action="store_true", help="Append a checkpoint. Existing checkpoints are kept.")
    parser.add_argument("--latest", action="store_true", help="Print the latest checkpoint id.")
    args = parser.parse_args(argv)
    if args.create and args.latest:
        parser.error("use either --create or --latest")
    if args.create:
        checkpoint = create_checkpoint()
        print(f"Created {checkpoint['checkpoint_id']} at {checkpoint['timestamp']}")
        return 0
    print(format_latest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
