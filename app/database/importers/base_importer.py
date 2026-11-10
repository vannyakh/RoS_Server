"""Shared file loading and transaction behavior for importers."""

import csv
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.importers.import_report import ImportReport
from app.database.importers.import_validator import require_version


class BaseImporter:
    filename = ""

    def __init__(self, session: AsyncSession, source: Path, report: ImportReport, batch_size: int = 100) -> None:
        self.session = session
        self.source = source
        self.report = report
        self.batch_size = batch_size

    def load_records(self, key: str) -> list[dict]:
        json_path = self.source / f"{self.filename}.json"
        csv_path = self.source / f"{self.filename}.csv"
        if json_path.exists():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            require_version(payload, json_path.name)
            records = payload.get(key)
            if not isinstance(records, list):
                raise ValueError(f"{json_path.name} must contain a list named {key}")
            return records
        if csv_path.exists():
            with csv_path.open(encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))
        return []

    def batches(self, records: list[dict]) -> list[list[dict]]:
        size = max(1, self.batch_size)
        return [records[index : index + size] for index in range(0, len(records), size)]
