"""RO-113: schema checks for the Solo first-playable acceptance checklist.

Does not invent Mercury opcodes or assert original-server behavior.
Live LDPlayer evidence lives in docs/testing/solo_first_playable.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
CHECKLIST = REPO_ROOT / "docs" / "testing" / "solo_first_playable.md"
STATUS = REPO_ROOT / "docs" / "SOLO_GAMEPLAY_STATUS.md"

REQUIRED_GATES = (
    "Solo Start",
    "9 bots",
    "plane",
    "Parachute",
    "Land",
)

RESULT_TOKENS = ("PASS", "FAIL", "NOT_RUN", "BLOCKED")


def test_checklist_file_exists():
    assert CHECKLIST.is_file(), f"missing checklist: {CHECKLIST}"


def test_checklist_has_five_gates_with_result_and_owner():
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "## Acceptance checklist" in text
    # Each gate row must carry a Result token and an owning RO-###.
    for gate in REQUIRED_GATES:
        assert gate in text, f"checklist missing gate label: {gate}"
    for token in ("FAIL", "NOT_RUN"):
        assert f"**{token}**" in text or f"| {token} |" in text or token in text
    owners = re.findall(r"RO-\d{3}", text)
    assert "RO-107" in owners or "RO-108" in owners
    assert "RO-069" in owners
    assert "RO-062" in owners
    assert "RO-063" in owners


def test_checklist_pass_cites_evidence_or_fail_cites_owner():
    """PASS rows need a path/log cite; FAIL/NOT_RUN rows need RO-###."""
    text = CHECKLIST.read_text(encoding="utf-8")
    # Extract markdown table rows under Acceptance checklist.
    section = text.split("## Acceptance checklist", 1)[1].split("## ", 1)[0]
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("|") and "---" not in line and "Gate" not in line
    ]
    assert len(rows) >= 5
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert len(cells) >= 4, row
        result, evidence, owner = cells[1], cells[2], cells[3]
        assert any(tok in result for tok in RESULT_TOKENS), row
        if "PASS" in result:
            assert (
                "logs/" in evidence
                or "artifacts/" in evidence
                or ".jpg" in evidence
                or ".png" in evidence
                or "server.log" in evidence
            ), row
        else:
            assert re.search(r"RO-\d{3}", owner), row


def test_solo_status_first_playable_not_verified_without_pass():
    status = STATUS.read_text(encoding="utf-8")
    assert "First-playable LDPlayer accept" in status
    # Must not claim VERIFIED when checklist has no PASS gates.
    checklist = CHECKLIST.read_text(encoding="utf-8")
    has_pass_gate = bool(re.search(r"\|\s*\*\*PASS\*\*\s*\|", checklist))
    for line in status.splitlines():
        if "First-playable LDPlayer accept" in line:
            if has_pass_gate:
                assert "VERIFIED" in line or "BROKEN" in line
            else:
                assert "VERIFIED" not in line
                assert "BROKEN" in line or "NOT_CHECKED" in line
            assert "compatible" not in line.lower() or "not original" in line.lower()
            break
    else:
        pytest.fail("first-playable row missing from SOLO_GAMEPLAY_STATUS.md")


def test_no_opcode_invention_in_checklist():
    text = CHECKLIST.read_text(encoding="utf-8")
    # Guardrail: acceptance doc must not mint wire opcodes (hex id assignments).
    assert not re.search(r"0x[0-9A-Fa-f]{2,}\s*=\s*", text)
