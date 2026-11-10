"""Report implementation, test, and original-behavior compatibility separately."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from tools.project_tracker.store import ROOT, load_json, management_path

REPORT = ROOT / "reports" / "compatibility" / "SUMMARY.md"


def load_features() -> tuple[str, list[dict]]:
    document = load_json(management_path("compatibility.json"))
    return document.get("source", ""), document["features"]


def _counts(features: list[dict], field: str) -> Counter:
    return Counter(feature.get(field, "missing") for feature in features)


def format_report(features: list[dict] | None = None, source: str | None = None) -> str:
    if features is None:
        source, features = load_features()
    implementation = _counts(features, "implementation_status")
    tests = _counts(features, "test_status")
    compatibility = _counts(features, "compatibility_status")
    lines = [
        "Compatibility report",
        source or "",
        "",
        "Implementation is not compatibility. A passing local test does not prove original RoS behavior.",
        "",
        f"Features: {len(features)}",
        "Implementation: " + ", ".join(f"{name} {implementation[name]}" for name in ("implemented", "partial", "not_implemented")),
        "Local tests: " + ", ".join(f"{name} {tests[name]}" for name in ("passing", "failing", "not_run")),
        "Original compatibility: " + ", ".join(f"{name} {compatibility[name]}" for name in sorted(compatibility)),
        "",
        "Not implemented:",
    ]
    unimplemented = [feature for feature in features if feature["implementation_status"] == "not_implemented"]
    if not unimplemented:
        lines.append("- none")
    for feature in unimplemented:
        lines.append(f"- {feature['feature_id']} {feature['feature_name']}: {feature['known_differences']}")
    lines.append("")
    lines.append("Compatible with authorized original behavior:")
    compatible = [feature for feature in features if feature["compatibility_status"] in {"compatible", "partially_compatible"}]
    if not compatible:
        lines.append("- none")
    for feature in compatible:
        lines.append(f"- {feature['feature_id']} {feature['feature_name']} ({feature['compatibility_status']})")
    return "\n".join(lines)


def write_report(path: Path = REPORT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    source, features = load_features()
    body = "# Compatibility summary\n\n" + format_report(features, source) + "\n"
    path.write_text(body, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report RoS compatibility records.")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write reports/compatibility/SUMMARY.md")
    args = parser.parse_args(argv)
    if not args.report and not args.write:
        parser.error("use --report or --write")
    if args.report:
        print(format_report())
    if args.write:
        path = write_report()
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
