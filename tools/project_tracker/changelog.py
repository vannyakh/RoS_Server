"""Render and list changelog records. Released rows are not rewritten."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from tools.project_tracker.store import ROOT, append_unique, atomic_write, load_json, management_path, now_iso

CHANGELOG_PATH = ROOT / "CHANGELOG.md"
UNRELEASED = "unreleased"


def load_changelog() -> dict:
    return load_json(management_path("changelog.json"))


def render_markdown(document: dict | None = None) -> str:
    document = document if document is not None else load_changelog()
    entries = document.get("entries", [])
    released: dict[str, list[dict]] = defaultdict(list)
    unreleased = []
    for entry in entries:
        if entry.get("version") == UNRELEASED:
            unreleased.append(entry)
        else:
            released[entry["version"]].append(entry)
    lines = [
        "# Changelog",
        "",
        "The source of truth is `.cursor/management/changelog.json`.",
        "Released sections are historical records. Rendering this file does not delete them.",
        "",
        "## [Unreleased]",
        "",
    ]
    lines.extend(_section(unreleased) or ["No unreleased changes.", ""])
    for version in sorted(released, reverse=True):
        lines.extend([f"## [{version}]", ""])
        lines.extend(_section(released[version]))
    return "\n".join(lines).rstrip() + "\n"


def _section(entries: list[dict]) -> list[str]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        grouped[entry["category"]].append(entry)
    lines: list[str] = []
    for category in sorted(grouped):
        lines.append(f"### {category}")
        lines.append("")
        for entry in grouped[category]:
            breaking = " Breaking change." if entry.get("breaking_change") else ""
            lines.append(f"- {entry['change_id']} {entry['title']}.{breaking} {entry['description']} Task: {entry.get('task_id') or 'none'}.")
        lines.append("")
    return lines


def add_entry(entry: dict) -> dict:
    """Append one changelog row. Existing change ids cannot be replaced."""
    document = load_changelog()
    append_unique(document, "entries", entry, "change_id")
    document["updated_at"] = now_iso()
    atomic_write(management_path("changelog.json"), document)
    return document


def format_unreleased(document: dict | None = None) -> str:
    document = document if document is not None else load_changelog()
    rows = [entry for entry in document.get("entries", []) if entry.get("version") == UNRELEASED]
    if not rows:
        return "No unreleased changes."
    return "\n".join(f"{entry['change_id']} [{entry['category']}] {entry['title']}" for entry in rows)


def write_markdown() -> None:
    CHANGELOG_PATH.write_text(render_markdown(), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the RoS changelog.")
    parser.add_argument("--unreleased", action="store_true")
    parser.add_argument("--render", action="store_true", help="Rewrite CHANGELOG.md from the JSON records.")
    args = parser.parse_args(argv)
    if not args.unreleased and not args.render:
        parser.error("use --unreleased or --render")
    if args.unreleased:
        print(format_unreleased())
    if args.render:
        write_markdown()
        print("Wrote CHANGELOG.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
