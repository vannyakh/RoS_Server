"""Sync bigworld_gateway/ with the RosGG-Server-v2 repository (the other team's working copy).

RosGG-Server-v2 is where another team develops the original-client gateway. RoS_Server is the
copy that runs the real game and gateway. This script moves changes between the two without
losing work on either side. It uses a three-way rule per file:

    base     = RosGG commit recorded in bigworld_gateway/UPSTREAM_SYNC.json (last sync)
    upstream = RosGG commit being pulled (default: the checkout's HEAD)
    local    = the file in RoS_Server/bigworld_gateway/ right now

    local == upstream             -> already in sync
    local == base                 -> take upstream (RosGG changed it, we did not)
    upstream == base              -> keep local (we changed it, RosGG did not)
    all three differ              -> conflict: left alone and reported

Commands (run from the RoS_Server root):

    python scripts/sync_rosgg_gateway.py status --source <path to RosGG-Server-v2>
    python scripts/sync_rosgg_gateway.py pull   --source <path> [--fetch] [--ref origin/main] [--dry-run]
    python scripts/sync_rosgg_gateway.py push   --source <path> [--dry-run]

`--source` may also come from the ROSGG_SERVER_V2 environment variable.

`pull` writes upstream files into bigworld_gateway/ and records the new base only when no
conflict is left. `push` copies RoS_Server-side gateway changes into the RosGG working tree
(never commits there) so the other team can review and commit them. Nothing is committed in
either repository; review with `git diff` and commit by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_DIR = "bigworld_gateway"
STATE_NAME = "UPSTREAM_SYNC.json"

# Files that never cross between the repositories: secrets, keys, captures, logs, local state.
EXCLUDE = (
    ".env",
    "*.pem",
    "*.key",
    "server/server_keys/*",
    "server/latest_bf_key.bin",
    "server/*_capture.bin",
    "server/saved_accounts.json",
    "client/frida/payloads/framing/captures/*",
    "logs/*",
    "*.log",
    "*.apk",
    "*.xapk",
    STATE_NAME,
)


def excluded(path: str) -> bool:
    return any(fnmatch(path, pat) or fnmatch(Path(path).name, pat) for pat in EXCLUDE)


def git(repo: Path, *args: str, check: bool = True, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=text,
    )


def tree_blobs(repo: Path, ref: str) -> dict[str, str]:
    """Map path -> blob id for every file at `ref`."""
    out = git(repo, "ls-tree", "-r", "-z", ref).stdout
    blobs: dict[str, str] = {}
    for entry in out.split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        _mode, kind, oid = meta.split()
        if kind == "blob":
            blobs[path] = oid
    return blobs


def hash_files(repo: Path, prefix: str, rels: list[str]) -> dict[str, str | None]:
    """Blob ids git in `repo` would store for repo/prefix/rel (its eol filters apply). One call."""
    result: dict[str, str | None] = {rel: None for rel in rels}
    present = [rel for rel in rels if (repo / prefix / rel).is_file()]
    if not present:
        return result
    paths = "\n".join(f"{prefix}/{rel}" if prefix else rel for rel in present) + "\n"
    out = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "--stdin-paths"],
        input=paths, check=True, capture_output=True, text=True,
    ).stdout.split()
    result.update(zip(present, out))
    return result


def local_blobs(dest_root: Path, rels: list[str]) -> dict[str, str | None]:
    return hash_files(dest_root, GATEWAY_DIR, rels)


def worktree_blobs(src: Path, rels: list[str]) -> dict[str, str | None]:
    return hash_files(src, "", rels)


def local_paths(dest_root: Path) -> set[str]:
    """Gateway files tracked by RoS_Server git plus untracked, not ignored ones."""
    out = git(
        dest_root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", GATEWAY_DIR
    ).stdout
    prefix = GATEWAY_DIR + "/"
    return {p[len(prefix):] for p in out.split("\0") if p.startswith(prefix)}


def read_state(dest_root: Path) -> dict:
    path = dest_root / GATEWAY_DIR / STATE_NAME
    if not path.is_file():
        raise SystemExit(
            f"{GATEWAY_DIR}/{STATE_NAME} is missing. Create it with the RosGG commit the gateway "
            "currently matches: python scripts/sync_rosgg_gateway.py init --source <path> --base <commit>"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(dest_root: Path, state: dict) -> None:
    path = dest_root / GATEWAY_DIR / STATE_NAME
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


@dataclass
class Plan:
    take: list[str] = field(default_factory=list)      # upstream -> local
    delete: list[str] = field(default_factory=list)    # upstream deleted, local unchanged
    keep_local: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    in_sync: int = 0


def plan_pull(src: Path, dest_root: Path, base: str, target: str) -> Plan:
    base_t = tree_blobs(src, base)
    up_t = tree_blobs(src, target)
    plan = Plan()
    changed = git(src, "diff", "--no-renames", "--name-only", "-z", base, target).stdout.split("\0")
    changed_rels = sorted(p for p in changed if p and not excluded(p))
    loc_paths = sorted(p for p in local_paths(dest_root) if not excluded(p))
    loc = local_blobs(dest_root, sorted(set(changed_rels) | set(loc_paths)))
    for rel in changed_rels:
        b, u = base_t.get(rel), up_t.get(rel)
        if loc[rel] == u:
            plan.in_sync += 1
        elif loc[rel] == b:
            (plan.take if u else plan.delete).append(rel)
        else:
            plan.conflicts.append(rel)
    for rel in loc_paths:
        b, u = base_t.get(rel), up_t.get(rel)
        if b == u and loc[rel] != b:
            plan.keep_local.append(rel)
    return plan


def plan_push(src: Path, dest_root: Path, base: str) -> tuple[list[str], list[str]]:
    """RoS_Server-side changes since base -> (copy into RosGG worktree, conflicts)."""
    base_t = tree_blobs(src, base)
    copy, conflicts = [], []
    rels = sorted(p for p in local_paths(dest_root) if not excluded(p))
    loc_all = local_blobs(dest_root, rels)
    changed = [rel for rel in rels if loc_all[rel] != base_t.get(rel)]
    wt_all = worktree_blobs(src, changed)
    for rel in changed:
        loc, wt = loc_all[rel], wt_all[rel]
        if wt == loc:
            continue
        if wt == base_t.get(rel):
            copy.append(rel)
        else:
            conflicts.append(rel)
    return copy, conflicts


def show(title: str, items: list[str], limit: int = 40) -> None:
    print(f"{title}: {len(items)}")
    for rel in items[:limit]:
        print(f"  {rel}")
    if len(items) > limit:
        print(f"  ... {len(items) - limit} more")


def resolve_source(arg: str | None) -> Path:
    raw = arg or os.environ.get("ROSGG_SERVER_V2")
    if not raw:
        raise SystemExit("Give --source <RosGG-Server-v2 checkout> or set ROSGG_SERVER_V2.")
    src = Path(raw).resolve()
    if not (src / ".git").exists():
        raise SystemExit(f"{src} is not a git checkout.")
    return src


def cmd_init(args, src: Path) -> int:
    commit = git(src, "rev-parse", args.base).stdout.strip()
    url = git(src, "remote", "get-url", "origin", check=False).stdout.strip()
    write_state(args.dest, {"upstream": url, "commit": commit})
    print(f"recorded base {commit[:10]}")
    return 0


def cmd_status(args, src: Path) -> int:
    state = read_state(args.dest)
    target = git(src, "rev-parse", args.ref).stdout.strip()
    print(f"base {state['commit'][:10]}  upstream {args.ref} = {target[:10]}")
    plan = plan_pull(src, args.dest, state["commit"], target)
    show("RosGG changes to pull", plan.take)
    show("RosGG deletions to pull", plan.delete)
    show("RoS_Server-only changes (push candidates)", plan.keep_local)
    show("conflicts (changed on both sides)", plan.conflicts)
    return 1 if plan.conflicts else 0


def cmd_pull(args, src: Path) -> int:
    state = read_state(args.dest)
    if args.fetch:
        print(git(src, "fetch", "origin").stderr.strip() or "fetched origin")
    target = git(src, "rev-parse", args.ref).stdout.strip()
    plan = plan_pull(src, args.dest, state["commit"], target)
    show("take from RosGG", plan.take)
    show("delete (removed in RosGG)", plan.delete)
    show("conflicts (left alone)", plan.conflicts)
    if args.dry_run:
        print("dry run: nothing written")
        return 1 if plan.conflicts else 0
    gw = args.dest / GATEWAY_DIR
    for rel in plan.take:
        data = git(src, "cat-file", "blob", f"{target}:{rel}", text=False).stdout
        out = gw / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    for rel in plan.delete:
        (gw / rel).unlink(missing_ok=True)
    if plan.conflicts:
        print("conflicts remain: base not advanced. Merge them by hand, then run pull again.")
        return 1
    url = git(src, "remote", "get-url", "origin", check=False).stdout.strip()
    write_state(args.dest, {"upstream": url or state.get("upstream", ""), "commit": target})
    print(f"synced to RosGG {target[:10]}; review with: git diff --stat -- {GATEWAY_DIR}")
    return 0


def cmd_push(args, src: Path) -> int:
    state = read_state(args.dest)
    copy, conflicts = plan_push(src, args.dest, state["commit"])
    show("copy into RosGG working tree", copy)
    show("conflicts (RosGG working tree differs)", conflicts)
    if args.dry_run:
        print("dry run: nothing written")
        return 1 if conflicts else 0
    gw = args.dest / GATEWAY_DIR
    for rel in copy:
        out = src / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((gw / rel).read_bytes())
    print(f"copied {len(copy)} files; review and commit in {src.name} by hand.")
    return 1 if conflicts else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("init", "status", "pull", "push"):
        p = sub.add_parser(name)
        p.add_argument("--source", help="RosGG-Server-v2 checkout (or env ROSGG_SERVER_V2)")
        p.add_argument("--dest", type=Path, default=ROOT, help=argparse.SUPPRESS)
        if name == "init":
            p.add_argument("--base", required=True, help="RosGG commit the gateway matches now")
        if name in ("status", "pull"):
            p.add_argument("--ref", default="HEAD", help="RosGG ref to sync to (default HEAD)")
        if name == "pull":
            p.add_argument("--fetch", action="store_true", help="git fetch origin in RosGG first")
        if name in ("pull", "push"):
            p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    args.dest = Path(args.dest).resolve()
    src = resolve_source(args.source)
    return {"init": cmd_init, "status": cmd_status, "pull": cmd_pull, "push": cmd_push}[args.cmd](args, src)


if __name__ == "__main__":
    sys.exit(main())
