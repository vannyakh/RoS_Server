"""Add missing folders and documentation templates for the existing RoS projects.

The default workspace is the parent of this repository. Pass ``--workspace``
when that parent is not the directory that already contains ``RoS_Server``.
Existing files and directories are skipped. Nothing is deleted.

The script does not write Python modules, a patch script, or an update feed.
It does not write under original Android artifacts, the read-only client
archive, databases, or Git metadata.

    python scripts/setup_ros_workspace.py --dry-run
    python scripts/setup_ros_workspace.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]

SERVER_DIRS = [
    "game_runtime/core",
    "game_runtime/entities",
    "game_runtime/systems",
    "game_runtime/players",
    "game_runtime/movement",
    "game_runtime/physics",
    "game_runtime/combat",
    "game_runtime/weapons",
    "game_runtime/inventory",
    "game_runtime/vehicles",
    "game_runtime/loot",
    "game_runtime/zone",
    "game_runtime/teams",
    "game_runtime/matches",
    "game_runtime/networking",
    "game_runtime/persistence",
    "shared/contracts",
    "shared/config",
    "tests/unit",
    "tests/integration",
]

CLIENT_DIRS = [
    "research/apk_inventory",
    "research/android_structure",
    "research/native_analysis",
    "research/gameplay_observations",
    "research/asset_catalog",
    "research/maps",
    "research/evidence",
    "research/reports",
    "docs",
    "management",
]

FORBIDDEN_PREFIXES = (
    "Android/",
    "Android\\",
    "Ios/",
    "Ios\\",
    "Client/Decompiled/",
    "Client\\Decompiled\\",
)

SERVER_FILES = {
    "AGENTS.md": """# RoS Server agents

Shared instructions for coding agents. Replace this fallback with the repository's full agent guide if it is missing. Read `docs/ARCHITECTURE.md` before editing. Do not invent original protocol fields. Do not bypass original client protections.
""",
    "docs/ARCHITECTURE.md": """# Architecture

Fallback page. The running system is a FastAPI control plane and an in-process match loop. The wire format is version 1 JSON in `docs/NETWORK_PROTOCOL.md`. Original-client research is not that protocol.
""",
    "docs/NETWORK_PROTOCOL.md": """# Network protocol

Fallback page. Document only the messages this server implements and tests. Do not add unverified numeric opcodes or an original client packet layout.
""",
    "game_runtime/README.md": """# Game runtime layout

`app/game` is the running simulation. The directories next to this file are reserved names only. They are not a second engine. Do not add empty modules here. Splitting a dedicated runtime process requires an architecture decision.
""",
    "docs/GAMEPLAY_SYSTEMS.md": """# Gameplay systems

This page is the independent rules template for this server. Original Rules of Survival movement, combat, weapon, inventory, vehicle, and zone numbers were not observed. Do not fill them in from memory or from an unverified article.

The running simulation is `app/game/`. Constants in that package are this project's design. A test that passes shows the code matches itself. It does not show original-game compatibility.

## Evidence labels

- **Confirmed:** observed in this repository's code or tests.
- **Inferred:** a reading supported by that code.
- **Unknown:** not observed. Leave it unknown.

## Systems

| ID | System | Status |
| --- | --- | --- |
| ROS-R01 | Match flow | Independent loop exists in `app/game`. Original phases are Unknown. |
| ROS-R02 | Movement | Independent movement exists. Original speeds and poses are Unknown. |
| ROS-R03 | Combat | Independent hits exist. Original damage and armor are Unknown. |
| ROS-R04 | Weapons | Independent weapon table exists. Original statistics are Unknown. |
| ROS-R05 | Inventory | Durable stacks exist on HTTP. Original backpack rules are Unknown. |
| ROS-R06 | Map | Published map packages exist. Original terrain is Unknown. |
| ROS-R07 | Loot | Independent pickups exist. Original loot tables are Unknown. |
| ROS-R08 | Vehicles | One independent vehicle exists. Original vehicle statistics are Unknown. |
| ROS-R09 | Zone | Independent zone phases exist. Original timing and damage are Unknown. |
| ROS-R10 | Multiplayer | Independent JSON session exists. Original synchronization is Unknown. |
| ROS-R11 | Progression | Profile totals exist. Original rank and reward rules are Unknown. |

Client observations for the same IDs are in the sibling client repository under `research/GAMEPLAY_SYSTEMS.md`.

## Agent rule

Add a new gameplay number only in the same change as the code and the test, and label it as an independent design. Do not present it as an original Rules of Survival specification.
""",
    "docs/RESEARCH_POLICY.md": """# Research policy

Research supports an independent game. It does not become a copy of a proprietary client, protocol, or asset pack.

## Evidence

- **Confirmed:** directly observed in permitted materials or reproduced by a test.
- **Inferred:** a reasonable interpretation supported by that evidence.
- **Unknown:** needs more research. Do not replace it with a guess.

A new design decision is labeled as independent. It is not labeled as an original Rules of Survival fact.

## Boundaries

- Keep original Android artifacts and `Client/Decompiled/` read-only in the client repository. Do not point a patch script at that archive.
- Do not bypass authentication, encryption, certificate pinning, or access controls on an original game client.
- Do not publish numeric opcodes, packet layouts, or handshake fields unless a reviewed design implements and tests them as this project's own protocol.
- The wire format in `docs/NETWORK_PROTOCOL.md` is this server's version 1 JSON. Research notes in `docs/reverse-engineering/` are not that protocol.
- Publisher binaries, artwork, fonts, and sounds stay out of the public tree. A source license does not cover those files.
- Do not write a home directory, drive letter, or machine address into rules, skills, or shared notes.
- Do not print secrets, password hashes, raw tokens, or session hashes.

## Tools

Package inspection, static analysis, and multiplayer-architecture references may inform a later note. Running a disassembler is a separate task. A filename or a string in a binary is not a protocol field.
""",
    "management/TASKS.md": """# Task checkpoints

This file is a reading list. It does not assign work and it does not mark work complete.

The server registry is `.cursor/management/tasks.json`. The CTO agent is the only role that changes assignment or status there. A specialist does not edit that file. Completion needs command output in the registry, not a summary in chat.

The client registry is `management/client_tasks.json` in the sibling client repository.

## Rebuild checkpoints

| Order | Checkpoint | State to record |
| --- | --- | --- |
| 1 | Research inventory | Client `research/reports/PHASE-01-REPORT.md` |
| 2 | Independent gameplay rules | This repository's `docs/GAMEPLAY_SYSTEMS.md` plus tests for any new number |
| 3 | Authoritative simulation | Existing `app/game` loop. A separate runtime process needs a new architecture decision. |
| 4 | Gameplay implementation | One system per change, with tests |
| 5 | Two independent clients | Two `com.ros.client` sessions in one match. The original package is not the test client. |
| 6 | Admin and community | Not started. This checkpoint does not create an admin application. |

## Do not start from this file

- A new workspace root
- Empty Python modules that stand in for unfinished systems
- A client patch script or an update-feed config
- Original protocol opcodes
""",
}

CLIENT_FILES = {
    "AGENTS.md": """# RoS Client agents

Shared instructions for the client repository. `Android/` and `Client/Decompiled/` stay protected. Build the independent app under `Android_API_Client/`. Do not bypass original client protections.
""",
    "docs/ARCHITECTURE.md": """# Client architecture

This page is the client map. It does not replace `research/CLIENT_ARCHITECTURE.md`.

## Two applications

| Application | Path | Role |
| --- | --- | --- |
| Original package | `Android/`, `Client/Decompiled/` | Read-only reference and existing rebuild artifacts. Package observed: `com.netease.chiji`. |
| Independent client | `Android_API_Client/` | Kotlin client for this project's JSON API. Package `com.ros.client`. |

`Ios/` is present and is not an active target. The folder name on disk is `Ios`.

## Server

The authoritative server is the sibling repository `RoS_Server`. Its control plane is FastAPI. Its current match loop is in-process. The wire format is that repository's `docs/NETWORK_PROTOCOL.md`.

## Boundaries

- Do not modify `Client/Decompiled/` or overwrite original APKs.
- Do not point `Android/apk/patch_android.py` at the archive.
- Do not bypass original client protections.
- Do not copy publisher assets into a public tree.
""",
    "docs/GAMEPLAY_SYSTEMS.md": """# Gameplay systems

Original gameplay numbers are not documented here.

Observations and unknowns are in `research/GAMEPLAY_SYSTEMS.md`. Independent server rules, when written, belong in the sibling server repository at `docs/GAMEPLAY_SYSTEMS.md`. Those rules are a new design. They are not original Rules of Survival statistics.

Do not add weapon, movement, zone, or reward numbers to this page unless a research record marks the evidence Confirmed or the value is explicitly an independent design.
""",
    "docs/NETWORK_PROTOCOL.md": """# Network protocol

This client does not define an original Rules of Survival packet format.

Verified observations and the independent protocol boundary are in `research/MULTIPLAYER_RESEARCH.md`. The server's implemented messages are in the sibling repository at `docs/NETWORK_PROTOCOL.md`. That document is version 1 JSON. It has no numeric opcodes.

Do not add opcode numbers, binary layouts, or original authentication fields to this page.
""",
    "docs/RESEARCH_POLICY.md": """# Research policy

Use `research/RESEARCH_TEMPLATE.md` for new records. Label every claim Confirmed, Inferred, or Unknown.

- `Client/Decompiled/` is read-only. `Android/` keeps existing rebuild artifacts. Do not overwrite either.
- `Android_API_Client/` is the independent application.
- Do not bypass authentication, encryption, certificate pinning, or access controls.
- Do not treat a research note as an original protocol.
- Do not copy publisher binaries, artwork, or sounds into a public tree.
- The sibling server policy is `docs/RESEARCH_POLICY.md` in `RoS_Server`.
""",
    "management/TASKS.md": """# Task checkpoints

This file is a reading list. The client registry remains `management/client_tasks.json`. Do not mark a task complete by editing this note.

| Order | Checkpoint | Where the evidence lives |
| --- | --- | --- |
| 1 | Inventory | `research/reports/PHASE-01-REPORT.md` |
| 2 | Gameplay evidence | `research/GAMEPLAY_SYSTEMS.md` |
| 3 | Independent client | `Android_API_Client/` and `docs/ANDROID_API_CLIENT.md` |
| 4 | Two-client match | Not run. The original package is not the test client. |

Server assignments stay in the sibling repository's `.cursor/management/tasks.json`.
""",
}

ADMIN_FILES = {
    "AGENTS.md": """# RoS Admin agents

This tree is a documentation placeholder. There is no admin application yet. Do not invent an original protocol or copy publisher assets here. Server map publishing stays in the sibling `RoS_Server` repository.
""",
    "docs/ARCHITECTURE.md": """# Admin architecture

No admin frontend is implemented in this directory.

The server already publishes maps through an allow-list on its own admin routes. That allow-list is not this application. A future console should call those HTTP routes and should not open the live database directly.

Original Android packages and decompiled files stay in the client repository and are not used here.
""",
    "management/TASKS.md": """# Task checkpoints

No admin task is assigned from this file. Do not treat this note as a task registry.

The server registry is `.cursor/management/tasks.json` in the sibling `RoS_Server` repository.
""",
}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _allowed(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    for prefix in FORBIDDEN_PREFIXES:
        if normalized.startswith(prefix.replace("\\", "/")):
            return False
    parts = Path(normalized).parts
    if ".git" in parts or ".env" in parts:
        return False
    name = parts[-1] if parts else normalized
    if name.endswith((".apk", ".obb", ".xapk", ".so", ".idsig", ".db")):
        return False
    return True


def _plan(root: Path, files: dict[str, str]) -> list[tuple[Path, str]]:
    planned: list[tuple[Path, str]] = []
    for relative, content in files.items():
        if not _allowed(relative):
            raise RuntimeError(f"refusing protected path: {relative}")
        planned.append((root / relative, content))
    return planned


def _apply(root: Path, planned: list[tuple[Path, str]], dry_run: bool) -> list[str]:
    lines: list[str] = []
    label = root.name
    for path, content in planned:
        shown = f"{label}/{_relative(path, root)}"
        if path.exists():
            lines.append(f"skip  {shown}")
            continue
        lines.append(f"{'would' if dry_run else 'create'} {shown}")
        if dry_run:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    return lines


def _apply_dirs(root: Path, relatives: list[str], dry_run: bool) -> list[str]:
    lines: list[str] = []
    for relative in relatives:
        if not _allowed(relative):
            raise RuntimeError(f"refusing protected path: {relative}")
        path = root / relative
        shown = f"{root.name}/{relative}/"
        if path.is_dir():
            lines.append(f"skip  {shown}")
            continue
        if path.exists():
            lines.append(f"skip  {shown} exists and is not a directory")
            continue
        lines.append(f"{'would' if dry_run else 'create'} {shown}")
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)
    return lines


def _workspace(argument: str | None) -> Path:
    if argument:
        return Path(argument).expanduser().resolve()
    return SERVER_ROOT.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add missing RoS folders and documentation templates.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing.")
    parser.add_argument(
        "--workspace",
        help="Parent directory that already contains RoS_Server. Defaults to this repository's parent.",
    )
    args = parser.parse_args(argv)

    workspace = _workspace(args.workspace)
    server = workspace / "RoS_Server"
    client = workspace / "RoS_Client"
    admin = workspace / "RoS_Admin"
    if server.resolve() != SERVER_ROOT.resolve():
        print("refusing to create or edit a different RoS_Server than this repository", file=sys.stderr)
        return 1
    if not client.is_dir():
        print("client missing: RoS_Client was not found beside this repository", file=sys.stderr)
        return 1

    print("workspace parent of RoS_Server" if args.workspace is None else "workspace --workspace")
    print("server RoS_Server")
    print("client RoS_Client")
    print("admin RoS_Admin")

    lines = _apply_dirs(server, SERVER_DIRS, args.dry_run)
    lines.extend(_apply(server, _plan(server, SERVER_FILES), args.dry_run))
    lines.extend(_apply_dirs(client, CLIENT_DIRS, args.dry_run))
    lines.extend(_apply(client, _plan(client, CLIENT_FILES), args.dry_run))
    lines.extend(_apply(admin, _plan(admin, ADMIN_FILES), args.dry_run))
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
