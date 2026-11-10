"""Upsert independently authored item definitions by stable code."""

from app.database.importers.base_importer import BaseImporter
from app.database.importers.import_validator import require_fields
from app.database.seeds._upsert import upsert_code
from app.models.game_data import ItemDefinition


class GameDataImporter(BaseImporter):
    filename = "items"

    async def run(self) -> None:
        for batch in self.batches(self.load_records("items")):
            for record in batch:
                label = str(record.get("code") or "<missing>")
                try:
                    require_fields(record, ("code", "name"), label)
                    code = str(record["code"]).strip().upper()
                except (ValueError, Exception) as exc:
                    self.report.errors.append(f"{label}: {exc}")
                    continue
                await upsert_code(
                    self.session,
                    ItemDefinition,
                    code,
                    name=str(record["name"]),
                    description=str(record.get("description") or ""),
                    category=str(record.get("category") or "misc"),
                    max_stack=int(record.get("max_stack") or 1),
                    details={"imported": True},
                )
                self.report.created.append(code)
