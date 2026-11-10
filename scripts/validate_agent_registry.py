"""Validate the engineering team and task registries.

Exit 0 when the registries match their schemas and the dependency, ownership,
and status rules. Exit 1 with one line per problem.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGEMENT = ROOT / ".cursor" / "management"
SCHEMAS = MANAGEMENT / "schemas"


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"{path.relative_to(ROOT)}: invalid JSON ({exc})"


def fail(problems: list[str]) -> int:
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1


def require_keys(node: dict, required: list[str], label: str, problems: list[str]) -> None:
    for key in required:
        if key not in node:
            problems.append(f"{label}: missing {key}")


def overlaps(left: str, right: str) -> bool:
    def prefix(pattern: str) -> str | None:
        if pattern.endswith("/**"):
            return pattern[:-3]
        if pattern.endswith("/*"):
            return pattern[:-2]
        return None

    if left == right:
        return True
    left_prefix, right_prefix = prefix(left), prefix(right)
    if left_prefix and (right == left_prefix or right.startswith(left_prefix + "/") or (right_prefix and (right_prefix == left_prefix or right_prefix.startswith(left_prefix + "/")))):
        return True
    if right_prefix and (left == right_prefix or left.startswith(right_prefix + "/")):
        return True
    return False


def cycles(tasks: dict[str, dict]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    found: list[str] = []

    def walk(task_id: str, stack: list[str]) -> None:
        if task_id in visiting:
            found.append(" -> ".join(stack + [task_id]))
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in tasks[task_id]["dependencies"]:
            if dependency in tasks:
                walk(dependency, stack + [task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        walk(task_id, [])
    return found


def main() -> int:
    problems: list[str] = []
    team, error = load(MANAGEMENT / "team.json")
    tasks_doc, tasks_error = load(MANAGEMENT / "tasks.json")
    workflow, workflow_error = load(MANAGEMENT / "workflow.json")
    team_schema, team_schema_error = load(SCHEMAS / "team.schema.json")
    task_schema, task_schema_error = load(SCHEMAS / "tasks.schema.json")
    for error in (error, tasks_error, workflow_error, team_schema_error, task_schema_error):
        if error:
            problems.append(error)
    if problems:
        return fail(problems)

    require_keys(team, team_schema["required"], "team.json", problems)
    require_keys(tasks_doc, task_schema["required"], "tasks.json", problems)
    if problems:
        return fail(problems)

    if team.get("assignment_authority") != "cto":
        problems.append("team.json: assignment_authority must be cto")

    agent_ids: list[str] = []
    agents: dict[str, dict] = {}
    for index, agent in enumerate(team.get("agents", [])):
        label = f"team.agents[{index}]"
        require_keys(agent, team_schema["properties"]["agents"]["items"]["required"], label, problems)
        agent_id = agent.get("id")
        if isinstance(agent_id, str):
            if agent_id in agents:
                problems.append(f"{label}: duplicate id {agent_id}")
            agents[agent_id] = agent
            agent_ids.append(agent_id)
        for skill in agent.get("skills", []):
            skill_file = ROOT / ".cursor" / "skills" / skill / "SKILL.md"
            if not skill_file.is_file():
                problems.append(f"{label}: skill {skill} has no SKILL.md")

    task_items = task_schema["$defs"]["task"]
    history_items = task_schema["$defs"]["history"]
    statuses = set(workflow["statuses"])
    priorities = set(workflow["priorities"])
    if set(tasks_doc.get("task_statuses", [])) != statuses:
        problems.append("tasks.json: task_statuses must match workflow.json")
    if set(tasks_doc.get("priorities", [])) != priorities:
        problems.append("tasks.json: priorities must match workflow.json")

    by_id: dict[str, dict] = {}
    for index, task in enumerate(tasks_doc.get("tasks", [])):
        label = f"tasks[{index}]"
        require_keys(task, task_items["required"], label, problems)
        task_id = task.get("id")
        if task_id in by_id:
            problems.append(f"{label}: duplicate id {task_id}")
        elif isinstance(task_id, str):
            by_id[task_id] = task
        if task.get("status") not in statuses:
            problems.append(f"{task_id}: invalid status")
        if task.get("priority") not in priorities:
            problems.append(f"{task_id}: invalid priority")
        agent_id = task.get("assigned_agent")
        if agent_id not in agents:
            problems.append(f"{task_id}: assigned_agent {agent_id} is not in team.json")
        elif not agents[agent_id].get("active", False):
            problems.append(f"{task_id}: assigned_agent {agent_id} is inactive")
        for reviewer in task.get("review_agents", []):
            if reviewer not in agents:
                problems.append(f"{task_id}: review agent {reviewer} is not in team.json")
            if reviewer == agent_id and task.get("status") == "completed":
                problems.append(f"{task_id}: {agent_id} cannot be the only completed-task approver")
        if task.get("status") == "completed" and task.get("review_agents") == [agent_id]:
            problems.append(f"{task_id}: specialist approved its own completed task")

    for task_id, task in by_id.items():
        for dependency in task.get("dependencies", []):
            if dependency == task_id:
                problems.append(f"{task_id}: depends on itself")
            elif dependency not in by_id:
                problems.append(f"{task_id}: missing dependency {dependency}")
        if task.get("status") in workflow["requires_completed_dependencies"]:
            for dependency in task.get("dependencies", []):
                if dependency in by_id and by_id[dependency].get("status") != "completed":
                    problems.append(f"{task_id}: dependency {dependency} is not completed")
        if task.get("status") == "blocked":
            if not task.get("block_reason") or not task.get("resolution_plan"):
                problems.append(f"{task_id}: blocked task needs block_reason and resolution_plan")
        elif task.get("block_reason") or task.get("resolution_plan"):
            problems.append(f"{task_id}: block fields are only valid while blocked")
        if task.get("status") == "completed":
            report = task.get("completion_report")
            if not isinstance(report, dict):
                problems.append(f"{task_id}: completed task needs a completion_report")
            else:
                for key in ("summary", "files_changed", "tests_executed", "test_results", "migration_results", "review_findings", "remaining_issues"):
                    if key not in report:
                        problems.append(f"{task_id}: completion_report missing {key}")
                if not str(report.get("summary", "")).strip() or not str(report.get("test_results", "")).strip():
                    problems.append(f"{task_id}: completion_report needs summary and test_results")
        elif task.get("completion_report") is not None:
            problems.append(f"{task_id}: completion_report must be null until completed")

        history = task.get("history", [])
        previous = None
        for entry_index, entry in enumerate(history):
            entry_label = f"{task_id}.history[{entry_index}]"
            require_keys(entry, history_items["required"], entry_label, problems)
            source = entry.get("from_status")
            target = entry.get("to_status")
            if previous is None:
                if source is not None:
                    problems.append(f"{entry_label}: first history row must start from null")
            else:
                if source != previous:
                    problems.append(f"{entry_label}: history skips {previous} -> {source}")
                allowed = set(workflow["transitions"].get(source, []))
                if target not in allowed:
                    problems.append(f"{entry_label}: transition {source} -> {target} is not allowed")
            if target not in statuses and target is not None:
                problems.append(f"{entry_label}: unknown status {target}")
            previous = target
        if history and history[-1].get("to_status") != task.get("status"):
            problems.append(f"{task_id}: history does not end at {task.get('status')}")
        if history and history[-1].get("to_agent") != task.get("assigned_agent"):
            problems.append(f"{task_id}: history agent does not match assigned_agent")

    for cycle in cycles(by_id):
        problems.append(f"dependency cycle: {cycle}")

    active = [task for task in by_id.values() if task.get("status") in workflow["active_statuses"]]
    counts: dict[str, int] = {}
    for task in active:
        counts[task["assigned_agent"]] = counts.get(task["assigned_agent"], 0) + 1
    for agent_id, count in counts.items():
        limit = agents.get(agent_id, {}).get("max_parallel_tasks", 1)
        if count > limit:
            problems.append(f"{agent_id}: {count} active tasks exceeds max_parallel_tasks {limit}")
    for left_index, left in enumerate(active):
        for right in active[left_index + 1 :]:
            for left_path in left.get("files_allowed", []):
                for right_path in right.get("files_allowed", []):
                    if overlaps(left_path, right_path):
                        problems.append(f"file overlap: {left['id']} {left_path} conflicts with {right['id']} {right_path}")

    if "cto" not in agents:
        problems.append("team.json: cto agent is required")
    if problems:
        return fail(problems)
    print(f"OK: {len(agents)} agents, {len(by_id)} tasks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
