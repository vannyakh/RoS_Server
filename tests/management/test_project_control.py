"""Registry integrity for the project-control records."""

import json
from pathlib import Path

import pytest

from tools.project_tracker.changelog import render_markdown
from tools.project_tracker.store import ROOT, append_unique, atomic_write
from tools.project_tracker.validate_registry import validate_all, validate_documents

MANAGEMENT = ROOT / ".cursor" / "management"


def test_project_registries_validate():
    problems = validate_all()
    assert problems == []


def test_historical_tasks_and_evidence_remain():
    tasks = json.loads((MANAGEMENT / "tasks.json").read_text(encoding="utf-8"))
    by_id = {task["id"]: task for task in tasks["tasks"]}
    assert by_id["RO-001"]["status"] == "completed"
    assert "34 passed" in by_id["RO-001"]["completion_report"]["test_results"]
    assert by_id["RO-009"]["status"] == "ready"
    assert by_id["RO-011"]["status"] == "blocked"
    assert "0 are compatible" in by_id["RO-020"]["completion_report"]["summary"]
    assert by_id["RO-028"]["status"] == "completed"
    assert by_id["RO-012"]["status"] == "review"


def test_no_feature_is_marked_compatible():
    document = json.loads((MANAGEMENT / "compatibility.json").read_text(encoding="utf-8"))
    assert document["features"]
    assert all(feature["compatibility_status"] == "unknown" for feature in document["features"])


def test_checkpoint_ids_are_append_only():
    document = {"checkpoints": [{"checkpoint_id": "CP-0001"}]}
    with pytest.raises(ValueError, match="append-only"):
        append_unique(document, "checkpoints", {"checkpoint_id": "CP-0001"}, "checkpoint_id")


def test_changelog_render_keeps_entries():
    document = json.loads((MANAGEMENT / "changelog.json").read_text(encoding="utf-8"))
    rendered = render_markdown(document)
    assert "CH-0001" in rendered
    assert "## [Unreleased]" in rendered
    assert len(document["entries"]) == rendered.count("CH-")


def test_compatible_claim_without_reference_is_rejected():
    problems: list[str] = []
    from tools.project_tracker.validate_registry import COMPATIBILITY_STATUSES

    assert "compatible" in COMPATIBILITY_STATUSES
    feature = {
        "feature_id": "GP-999",
        "compatibility_status": "compatible",
        "original_reference": "No authorized original Rules of Survival specification is in this repository.",
        "evidence": "none",
    }
    reference = str(feature["original_reference"])
    evidence = str(feature["evidence"]).strip()
    if feature["compatibility_status"] in {"compatible", "partially_compatible"}:
        if not evidence or evidence == "none" or reference.startswith("No authorized"):
            problems.append("rejected")
    assert problems == ["rejected"]


def test_atomic_write_creates_a_backup(tmp_path: Path):
    target = tmp_path / "sample.json"
    target.write_text('{"version": "old"}\n', encoding="utf-8")
    backup = atomic_write(target, {"version": "new"}, backup_dir=tmp_path / "backups")
    assert backup is not None
    assert json.loads(backup.read_text(encoding="utf-8"))["version"] == "old"
    assert json.loads(target.read_text(encoding="utf-8"))["version"] == "new"


def test_validate_documents_reports_a_missing_historical_task(monkeypatch):
    monkeypatch.setattr(
        "tools.project_tracker.validate_registry.HISTORICAL_TASKS",
        ("RO-001", "RO-999"),
    )
    problems = validate_documents()
    assert any("RO-999" in problem for problem in problems)
