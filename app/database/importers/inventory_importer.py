"""Import inventory quantities. Existing balances are not replaced."""

from app.core.exceptions import AppError
from app.database.importers.base_importer import BaseImporter
from app.database.importers.import_validator import require_fields
from app.repositories.player_repository import PlayerRepository
from app.services.inventory_service import InventoryService


class InventoryImporter(BaseImporter):
    filename = "inventory"

    async def run(self) -> None:
        players = PlayerRepository(self.session)
        service = InventoryService(self.session)
        for batch in self.batches(self.load_records("inventory")):
            for record in batch:
                label = str(record.get("nickname") or "<missing>")
                try:
                    require_fields(record, ("nickname", "item_code", "quantity"), label)
                    nickname = str(record["nickname"]).strip()
                    quantity = int(record["quantity"])
                except (ValueError, Exception) as exc:
                    self.report.errors.append(f"{label}: {exc}")
                    continue
                player = await players.by_nickname(nickname)
                if player is None:
                    self.report.errors.append(f"{label}: player does not exist")
                    continue
                try:
                    await service.add_item(player.id, str(record["item_code"]), quantity, commit=False)
                except AppError as exc:
                    self.report.errors.append(f"{label}: {exc.detail}")
                    continue
                self.report.created.append(f"{nickname}:{record['item_code']}")
