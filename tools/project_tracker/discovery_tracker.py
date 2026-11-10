"""List reverse-engineering discoveries."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.project_tracker.store import ROOT, load_json, management_path

REPORT = ROOT / "reports" / "discoveries" / "INDEX.md"


def load_discoveries() -> list[dict]:
    return load_json(management_path("discoveries.json"))["discoveries"]


def format_discovery_list(rows: list[dict] | None = None) -> str:
    discoveries = rows if rows is not None else load_discoveries()
    blocks = []
    for row in discoveries:
        blocks.append(
            "\n".join(
                [
                    f"{row['discovery_id']}  {row['status']}  {row['confidence']}  {row['title']}",
                    f"  OBSERVED FACT: {row['observed_fact']}",
                    f"  INTERPRETATION: {row['interpretation']}",
                    f"  HYPOTHESIS: {row['hypothesis']}",
                    f"  IMPLEMENTATION IMPACT: {row['implementation_impact']}",
                ]
            )
        )
    return "\n\n".join(blocks)


def index_markdown(rows: list[dict] | None = None) -> str:
    discoveries = rows if rows is not None else load_discoveries()
    lines = [
        "# Discovery index",
        "",
        "Source of truth: `.cursor/management/discoveries.json`.",
        "A hypothesis stays a hypothesis until a new evidence path is recorded.",
        "",
    ]
    for row in discoveries:
        lines.extend(
            [
                f"## {row['discovery_id']} — {row['title']}",
                "",
                f"- Category: {row['category']}",
                f"- Confidence: {row['confidence']}",
                f"- Status: {row['status']}",
                f"- Source: {row['source_type']} — {row['source_reference']}",
                f"- Evidence: {row['evidence_path'] or 'none'}",
                "",
                f"OBSERVED FACT: {row['observed_fact']}",
                "",
                f"INTERPRETATION: {row['interpretation']}",
                "",
                f"HYPOTHESIS: {row['hypothesis']}",
                "",
                f"IMPLEMENTATION IMPACT: {row['implementation_impact']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_index(path: Path = REPORT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(index_markdown(), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List reverse-engineering discoveries.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write reports/discoveries/INDEX.md")
    args = parser.parse_args(argv)
    if not args.list and not args.write:
        parser.error("use --list or --write")
    if args.list:
        print(format_discovery_list())
    if args.write:
        path = write_index()
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
