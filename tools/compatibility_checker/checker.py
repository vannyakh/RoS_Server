"""Reject a compatibility claim that has no authorized reference."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "testdata" / "reference" / "compatibility_matrix.json"
ALLOWED = {"unknown", "documented", "partially_compatible", "compatible", "incompatible", "not_applicable"}


def load_matrix() -> list[dict]:
    return json.loads(MATRIX.read_text(encoding="utf-8"))["features"]


def audit(features: list[dict]) -> list[str]:
    problems = []
    seen = set()
    for feature in features:
        feature_id = feature["feature_id"]
        if feature_id in seen:
            problems.append(f"{feature_id}: duplicate id")
        seen.add(feature_id)
        status = feature["compatibility_status"]
        if status not in ALLOWED:
            problems.append(f"{feature_id}: invalid status {status}")
        reference = feature.get("original_reference", "")
        if status == "compatible":
            if reference.startswith("No authorized"):
                problems.append(f"{feature_id}: compatible without an authorized reference")
            if not feature.get("evidence") or feature["evidence"] == "none":
                problems.append(f"{feature_id}: compatible without evidence")
            if feature.get("test_status") != "passing":
                problems.append(f"{feature_id}: compatible without a passing test")
    return problems


def summarize(features: list[dict]) -> dict[str, int]:
    def count(key: str, value: str) -> int:
        return sum(item[key] == value for item in features)

    return {
        "functions": len(features),
        "implemented": count("implementation_status", "implemented"),
        "partial": count("implementation_status", "partial"),
        "not_implemented": count("implementation_status", "not_implemented"),
        "tests_passing": count("test_status", "passing"),
        "tests_not_run": count("test_status", "not_run"),
        "compatible": count("compatibility_status", "compatible"),
        "unknown": count("compatibility_status", "unknown"),
    }


def render_markdown(features: list[dict]) -> str:
    totals = summarize(features)
    header = [
        "# Game compatibility matrix",
        "",
        "Compatibility status describes comparison with authorized original Rules of Survival behavior.",
        "A passing test of this server's own rules does not change `unknown` to `compatible`.",
        "No authorized original specification is checked in. Every current row stays `unknown`.",
        "",
        "## Measurements",
        "",
        f"- Tracked functions: {totals['functions']}",
        f"- Implementation coverage: {totals['implemented']} implemented, {totals['partial']} partial, {totals['not_implemented']} not implemented",
        f"- Test coverage of those functions: {totals['tests_passing']} passing, {totals['tests_not_run']} not run",
        f"- Original RoS compatibility: {totals['compatible']} compatible, {totals['unknown']} unknown",
        "",
        "| feature_id | function_name | implementation_status | compatibility_status | test_status | priority | evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for feature in features:
        header.append(
            "| {feature_id} | {function_name} | {implementation_status} | {compatibility_status} | {test_status} | {priority} | {evidence} |".format(
                **feature
            )
        )
    header.extend(["", "## Notes", ""])
    for feature in features:
        header.append(
            f"- `{feature['feature_id']}` original_reference: {feature['original_reference']} Known differences: {feature['known_differences']}"
        )
    header.append("")
    return "\n".join(header)
