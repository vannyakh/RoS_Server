"""Back up and restore the SQLite database with SQLite's online backup API.

    python -m app.infrastructure.backup backup [--out FILE]
    python -m app.infrastructure.backup verify FILE
    python -m app.infrastructure.backup restore FILE [--target DB]

A backup is safe while the server runs. Stop the server before a restore: a restore replaces
every table, and a running server would keep writing on top of it. The database being
replaced is first copied beside itself as <name>.before-restore-<time>.db.
PostgreSQL is not covered; use pg_dump and pg_restore for it.
"""

import argparse
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

BACKUP_DIR = Path(__file__).resolve().parents[2] / "storage" / "backups"


def database_path(url: str) -> Path:
    scheme, _, rest = url.partition(":///")
    if not scheme.startswith("sqlite") or not rest or rest == ":memory:":
        raise SystemExit("Only a SQLite file database can be backed up with this tool")
    return Path(rest)


def verify(path: Path) -> dict[str, int]:
    """Row count per table. Raises if the file is missing, damaged or not this server's database."""
    if not path.is_file():
        raise SystemExit(f"No such file: {path}")
    try:
        with closing(sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)) as db:
            state = db.execute("PRAGMA integrity_check").fetchone()[0]
            if state != "ok":
                raise SystemExit(f"{path} failed the integrity check: {state}")
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            if "alembic_version" not in tables or "accounts" not in tables:
                raise SystemExit(f"{path} is not a RoS_Server database")
            return {name: db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in tables}
    except sqlite3.DatabaseError as error:
        raise SystemExit(f"{path} is not a readable database: {error}") from error


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def backup(database: Path, out: Path | None = None) -> Path:
    if not database.is_file():
        raise SystemExit(f"No such database: {database}")
    out = out or BACKUP_DIR / f"{database.stem}-{_stamp()}.db"
    if out.exists():
        raise SystemExit(f"{out} already exists")
    _copy(database, out)
    verify(out)
    return out


def restore(source: Path, target: Path) -> Path | None:
    """Replace `target` with `source`. Returns the safety copy of the old target, if there was one."""
    verify(source)
    if source.resolve() == target.resolve():
        raise SystemExit("The backup and the target are the same file")
    kept = None
    if target.is_file():
        kept = target.with_name(f"{target.stem}.before-restore-{_stamp()}.db")
        _copy(target, kept)
    _copy(source, target)
    verify(target)
    return kept


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.infrastructure.backup")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup").add_argument("--out", type=Path)
    commands.add_parser("verify").add_argument("file", type=Path)
    restoring = commands.add_parser("restore")
    restoring.add_argument("file", type=Path)
    restoring.add_argument("--target", type=Path)
    args = parser.parse_args(argv)

    def configured() -> Path:
        from app.core.config import settings

        return database_path(settings.database_url)

    if args.command == "backup":
        out = backup(configured(), args.out)
        print(f"backup written: {out} ({out.stat().st_size} bytes)")
    elif args.command == "verify":
        counts = verify(args.file)
        print(f"ok: {len(counts)} tables, {sum(counts.values())} rows")
    else:
        target = args.target or configured()
        kept = restore(args.file, target)
        print(f"restored {args.file} -> {target}" + (f"; previous copy: {kept}" if kept else ""))


if __name__ == "__main__":
    main()
