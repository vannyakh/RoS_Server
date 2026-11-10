"""Validate project-control registries and the existing agent registry."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from tools.project_tracker.store import ROOT, SCHEMAS, load_json, management_path

COMPATIBILITY_STATUSES = {
    "unknown",
    "researching",
    "documented",
    "implemented",
    "partially_compatible",
    "compatible",
    "incompatible",
    "not_applicable",
}
IMPLEMENTATION_STATUSES = {"not_implemented", "partial", "implemented"}
TEST_STATUSES = {"not_run", "passing", "failing"}
DISCOVERY_CONFIDENCE = {"confirmed", "high", "medium", "low", "unknown"}
DISCOVERY_STATUSES = {"new", "investigating", "verified", "rejected", "archived"}
CHANGE_CATEGORIES = {
    "Added",
    "Changed",
    "Fixed",
    "Removed",
    "Security",
    "Database",
    "Gameplay",
    "Networking",
    "Compatibility",
    "Performance",
    "Infrastructure",
    "Documentation",
}
HISTORICAL_TASKS = tuple(f"RO-{index:03d}" for index in list(range(1, 12)) + list(range(20, 29)))


def _require(node: dict, required: list[str], label: str, problems: list[str]) -> None:
    for key in required:
        if key not in node:
            problems.append(f"{label}: missing {key}")


def _cycles(tasks: dict[str, dict]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    found: list[str] = []

    def walk(task_id: str, stack: list[str]) -> None:
        if task_id in visiting:
            found.append(" -> ".join(stack + [task_id]))
            return
        if task_id in visited or task_id not in tasks:
            return
        visiting.add(task_id)
        for dependency in tasks[task_id].get("dependencies", []):
            walk(dependency, stack + [task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        walk(task_id, [])
    return found


def _load_registry(name: str, problems: list[str]) -> dict | None:
    path = management_path(name)
    if not path.is_file():
        problems.append(f"{name}: file is missing")
        return None
    try:
        return load_json(path)
    except json.JSONDecodeError as exc:
        problems.append(f"{name}: invalid JSON ({exc})")
        return None


def _agent_ids(team: dict | None) -> set[str]:
    if not team:
        return set()
    return {agent.get("id") for agent in team.get("agents", []) if isinstance(agent.get("id"), str)}


def validate_documents() -> list[str]:
    problems: list[str] = []
    team = _load_registry("team.json", problems)
    tasks_doc = _load_registry("tasks.json", problems)
    milestones = _load_registry("milestones.json", problems)
    discoveries = _load_registry("discoveries.json", problems)
    compatibility = _load_registry("compatibility.json", problems)
    checkpoints = _load_registry("checkpoints.json", problems)
    changelog = _load_registry("changelog.json", problems)
    decisions = _load_registry("decisions.json", problems)
    matrix_path = ROOT / "testdata" / "reference" / "compatibility_matrix.json"
    try:
        matrix = load_json(matrix_path)
    except (OSError, json.JSONDecodeError) as exc:
        matrix = None
        problems.append(f"testdata/reference/compatibility_matrix.json: {exc}")

    agents = _agent_ids(team)
    task_schema = None
    schema_path = SCHEMAS / "tasks.schema.json"
    if schema_path.is_file():
        task_schema = load_json(schema_path)

    phases: set[str] = set()
    if milestones:
        _require(milestones, ["version", "updated_at", "current_phase", "phases"], "milestones.json", problems)
        for index, phase in enumerate(milestones.get("phases", [])):
            label = f"milestones.phases[{index}]"
            _require(phase, ["phase", "name", "status", "summary", "task_ids"], label, problems)
            if isinstance(phase.get("phase"), str):
                phases.add(phase["phase"])
        if milestones.get("current_phase") not in phases:
            problems.append("milestones.json: current_phase is not a known phase")

    by_id: dict[str, dict] = {}
    categories = set()
    if task_schema:
        categories = set(task_schema["$defs"]["task"]["properties"]["category"]["enum"])
    if tasks_doc:
        for index, task in enumerate(tasks_doc.get("tasks", [])):
            task_id = task.get("id")
            label = f"tasks[{index}]"
            if task_id in by_id:
                problems.append(f"{label}: duplicate id {task_id}")
            elif isinstance(task_id, str):
                by_id[task_id] = task
            if task.get("phase") not in phases and phases:
                problems.append(f"{task_id}: phase {task.get('phase')} is not in milestones.json")
            if categories and task.get("category") not in categories:
                problems.append(f"{task_id}: invalid category")
            if task.get("compatibility_status") not in COMPATIBILITY_STATUSES:
                problems.append(f"{task_id}: invalid compatibility_status")
            if task.get("assigned_agent") not in agents and agents:
                problems.append(f"{task_id}: assigned_agent is not in team.json")
            if task.get("status") == "completed":
                if not task.get("completed_at"):
                    problems.append(f"{task_id}: completed task needs completed_at")
                report = task.get("completion_report")
                if not isinstance(report, dict) or not str(report.get("test_results", "")).strip():
                    problems.append(f"{task_id}: completed task needs test evidence")
            elif task.get("completed_at"):
                problems.append(f"{task_id}: completed_at must be null until completed")
            if task.get("compatibility_status") == "compatible":
                problems.append(f"{task_id}: task compatibility claim needs a compatibility feature record")
        for task_id in HISTORICAL_TASKS:
            if task_id not in by_id:
                problems.append(f"tasks.json: historical task {task_id} is missing")
        for cycle in _cycles(by_id):
            problems.append(f"dependency cycle: {cycle}")
        if milestones:
            phase_of = {}
            for phase in milestones.get("phases", []):
                for task_id in phase.get("task_ids", []):
                    if task_id in phase_of:
                        problems.append(f"milestones: {task_id} is listed in more than one phase")
                    phase_of[task_id] = phase.get("phase")
                    if task_id not in by_id:
                        problems.append(f"milestones phase {phase.get('phase')}: unknown task {task_id}")
            for task_id, task in by_id.items():
                if task_id not in phase_of:
                    problems.append(f"{task_id}: not listed in milestones.json")
                elif task.get("phase") != phase_of[task_id]:
                    problems.append(f"{task_id}: phase {task.get('phase')} does not match milestone phase {phase_of[task_id]}")

    feature_ids: set[str] = set()
    if compatibility:
        _require(compatibility, ["version", "updated_at", "source", "features"], "compatibility.json", problems)
        schema = load_json(SCHEMAS / "compatibility.schema.json")
        for index, feature in enumerate(compatibility.get("features", [])):
            label = f"compatibility.features[{index}]"
            _require(feature, schema["$defs"]["feature"]["required"], label, problems)
            feature_id = feature.get("feature_id")
            if feature_id in feature_ids:
                problems.append(f"{label}: duplicate feature_id {feature_id}")
            elif isinstance(feature_id, str):
                feature_ids.add(feature_id)
            if feature.get("compatibility_status") not in COMPATIBILITY_STATUSES:
                problems.append(f"{feature_id}: invalid compatibility_status")
            if feature.get("implementation_status") not in IMPLEMENTATION_STATUSES:
                problems.append(f"{feature_id}: invalid implementation_status")
            if feature.get("test_status") not in TEST_STATUSES:
                problems.append(f"{feature_id}: invalid test_status")
            reference = str(feature.get("original_reference", ""))
            evidence = str(feature.get("evidence", "")).strip()
            if feature.get("compatibility_status") in {"compatible", "partially_compatible"}:
                if not evidence or evidence == "none" or reference.startswith("No authorized"):
                    problems.append(f"{feature_id}: compatibility claim has no authorized reference evidence")
            for task_id in feature.get("related_tasks", []):
                if task_id not in by_id:
                    problems.append(f"{feature_id}: related task {task_id} does not exist")
        if matrix:
            matrix_ids = {row.get("feature_id") for row in matrix.get("features", [])}
            missing = matrix_ids - feature_ids
            if missing:
                problems.append("compatibility.json: missing feature ids from the reference matrix: " + ", ".join(sorted(missing)))

    discovery_ids: set[str] = set()
    if discoveries:
        _require(discoveries, ["version", "updated_at", "discoveries"], "discoveries.json", problems)
        schema = load_json(SCHEMAS / "discoveries.schema.json")
        for index, row in enumerate(discoveries.get("discoveries", [])):
            label = f"discoveries[{index}]"
            _require(row, schema["$defs"]["discovery"]["required"], label, problems)
            discovery_id = row.get("discovery_id")
            if discovery_id in discovery_ids:
                problems.append(f"{label}: duplicate discovery_id {discovery_id}")
            elif isinstance(discovery_id, str):
                discovery_ids.add(discovery_id)
            if row.get("confidence") not in DISCOVERY_CONFIDENCE:
                problems.append(f"{discovery_id}: invalid confidence")
            if row.get("status") not in DISCOVERY_STATUSES:
                problems.append(f"{discovery_id}: invalid status")
            if row.get("discovered_by") not in agents and agents:
                problems.append(f"{discovery_id}: discovered_by is not in team.json")
            for field in ("observed_fact", "interpretation", "hypothesis", "implementation_impact"):
                if not str(row.get(field, "")).strip():
                    problems.append(f"{discovery_id}: {field} is empty")
            if row.get("confidence") == "confirmed" and row.get("status") == "verified":
                if not str(row.get("evidence_path", "")).strip():
                    problems.append(f"{discovery_id}: verified discovery needs evidence_path")
            for task_id in row.get("related_tasks", []):
                if task_id not in by_id:
                    problems.append(f"{discovery_id}: related task {task_id} does not exist")
            for feature_id in row.get("related_features", []):
                if feature_id not in feature_ids:
                    problems.append(f"{discovery_id}: related feature {feature_id} does not exist")

    change_ids: set[str] = set()
    if changelog:
        _require(changelog, ["version", "updated_at", "entries"], "changelog.json", problems)
        schema = load_json(SCHEMAS / "changelog.schema.json")
        for index, row in enumerate(changelog.get("entries", [])):
            label = f"changelog[{index}]"
            _require(row, schema["$defs"]["entry"]["required"], label, problems)
            change_id = row.get("change_id")
            if change_id in change_ids:
                problems.append(f"{label}: duplicate change_id {change_id}")
            elif isinstance(change_id, str):
                change_ids.add(change_id)
            if row.get("category") not in CHANGE_CATEGORIES:
                problems.append(f"{change_id}: invalid category")
            if row.get("agent") not in agents and agents:
                problems.append(f"{change_id}: agent is not in team.json")
            task_id = row.get("task_id")
            if task_id and task_id not in by_id:
                problems.append(f"{change_id}: task_id {task_id} does not exist")
            discovery_id = row.get("related_discovery")
            if discovery_id and discovery_id not in discovery_ids:
                problems.append(f"{change_id}: related_discovery {discovery_id} does not exist")

    if checkpoints:
        _require(checkpoints, ["version", "updated_at", "checkpoints"], "checkpoints.json", problems)
        schema = load_json(SCHEMAS / "checkpoints.schema.json")
        seen: set[str] = set()
        previous_time = ""
        for index, row in enumerate(checkpoints.get("checkpoints", [])):
            label = f"checkpoints[{index}]"
            _require(row, schema["$defs"]["checkpoint"]["required"], label, problems)
            checkpoint_id = row.get("checkpoint_id")
            if checkpoint_id in seen:
                problems.append(f"{label}: duplicate checkpoint_id {checkpoint_id}")
            elif isinstance(checkpoint_id, str):
                seen.add(checkpoint_id)
            timestamp = str(row.get("timestamp", ""))
            if previous_time and timestamp < previous_time:
                problems.append(f"{checkpoint_id}: timestamp is earlier than the previous checkpoint")
            previous_time = timestamp
            if row.get("created_by") not in agents and agents:
                problems.append(f"{checkpoint_id}: created_by is not in team.json")
            for task_id in row.get("completed_tasks", []) + row.get("in_progress_tasks", []) + row.get("blocked_tasks", []) + row.get("next_tasks", []):
                if task_id not in by_id:
                    problems.append(f"{checkpoint_id}: unknown task {task_id}")

    if decisions:
        _require(decisions, ["version", "updated_at", "decisions"], "decisions.json", problems)
        seen_decisions: set[str] = set()
        for index, row in enumerate(decisions.get("decisions", [])):
            label = f"decisions[{index}]"
            _require(
                row,
                [
                    "decision_id",
                    "title",
                    "date",
                    "status",
                    "context",
                    "problem",
                    "options_considered",
                    "chosen_solution",
                    "reason",
                    "consequences",
                    "related_tasks",
                    "related_changes",
                    "record_path",
                ],
                label,
                problems,
            )
            decision_id = row.get("decision_id")
            if decision_id in seen_decisions:
                problems.append(f"{label}: duplicate decision_id {decision_id}")
            elif isinstance(decision_id, str):
                seen_decisions.add(decision_id)
            record = ROOT / str(row.get("record_path", ""))
            if row.get("record_path") and not record.is_file():
                problems.append(f"{decision_id}: record_path does not exist")
            for task_id in row.get("related_tasks", []):
                if task_id not in by_id:
                    problems.append(f"{decision_id}: related task {task_id} does not exist")
            for change_id in row.get("related_changes", []):
                if change_id not in change_ids:
                    problems.append(f"{decision_id}: related change {change_id} does not exist")

    return problems


def agent_registry_problems() -> list[str]:
    script = ROOT / "scripts" / "validate_agent_registry.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return []
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    return lines or [result.stdout.strip() or "agent registry validation failed"]


def validate_all() -> list[str]:
    return agent_registry_problems() + validate_documents()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate RoS project-control registries.")
    parser.parse_args(argv)
    problems = validate_all()
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    tasks = load_json(management_path("tasks.json"))
    discoveries = load_json(management_path("discoveries.json"))
    features = load_json(management_path("compatibility.json"))
    print(
        "OK: "
        f"{len(tasks['tasks'])} tasks, "
        f"{len(discoveries['discoveries'])} discoveries, "
        f"{len(features['features'])} compatibility features"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
