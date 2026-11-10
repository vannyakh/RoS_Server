"""Import authorized JSON or CSV datasets. Existing accounts and balances are not overwritten."""

import argparse
import asyncio
from pathlib import Path

from app.database.importers.account_importer import AccountImporter
from app.database.importers.game_data_importer import GameDataImporter
from app.database.importers.import_report import ImportReport
from app.database.importers.inventory_importer import InventoryImporter
from app.database.importers.player_importer import PlayerImporter
from app.infrastructure.database import SessionLocal, close_db, init_db


async def import_source(source: Path, *, commit: bool, batch_size: int) -> ImportReport:
    report = ImportReport(dry_run=not commit)
    await init_db()
    async with SessionLocal() as session:
        try:
            for importer in (
                GameDataImporter(session, source, report, batch_size),
                AccountImporter(session, source, report, batch_size),
                PlayerImporter(session, source, report, batch_size),
                InventoryImporter(session, source, report, batch_size),
            ):
                await importer.run()
            if report.errors or not commit:
                await session.rollback()
                if report.errors and commit:
                    report.created.clear()
            else:
                await session.commit()
        except Exception as exc:
            await session.rollback()
            report.errors.append(str(exc))
            report.created.clear()
    await close_db()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Import account, profile, and reference data.")
    parser.add_argument("--source", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    report = asyncio.run(import_source(args.source, commit=args.commit, batch_size=args.batch_size))
    print(report.as_dict())
    if report.errors and args.commit:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
