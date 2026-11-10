"""Import dry-run, duplicates, and rollback."""

import json

from sqlalchemy import func, select

from app.database.importers.account_importer import AccountImporter
from app.database.importers.import_report import ImportReport
from app.models.account import Account


def _write(directory, name, payload) -> None:
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


async def test_dry_run_creates_nothing(db_session, tmp_path):
    _write(
        tmp_path,
        "accounts.json",
        {"schema_version": 1, "accounts": [{"username": "dry_user", "password": "StrongTestPassword123!"}]},
    )
    report = ImportReport(dry_run=True)
    await AccountImporter(db_session, tmp_path, report).run()
    await db_session.rollback()
    count = await db_session.scalar(select(func.count()).select_from(Account))
    assert report.created == ["dry_user"]
    assert count == 0


async def test_duplicate_username_is_skipped(db_session, tmp_path):
    payload = {
        "schema_version": 1,
        "accounts": [
            {"username": "dup_user", "password": "StrongTestPassword123!"},
            {"username": "DUP_USER", "password": "StrongTestPassword123!"},
        ],
    }
    _write(tmp_path, "accounts.json", payload)
    report = ImportReport()
    await AccountImporter(db_session, tmp_path, report).run()
    await db_session.commit()
    count = await db_session.scalar(select(func.count()).select_from(Account))
    assert report.created == ["dup_user"]
    assert report.skipped == ["dup_user"]
    assert count == 1


async def test_invalid_record_rolls_back_the_batch(db_session, tmp_path):
    _write(
        tmp_path,
        "accounts.json",
        {
            "schema_version": 1,
            "accounts": [
                {"username": "kept_user", "password": "StrongTestPassword123!"},
                {"username": "broken_user"},
            ],
        },
    )
    report = ImportReport()
    await AccountImporter(db_session, tmp_path, report).run()
    assert report.errors
    await db_session.rollback()
    count = await db_session.scalar(select(func.count()).select_from(Account))
    assert count == 0
