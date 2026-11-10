"""Attach profiles to accounts that already exist. Existing nicknames are left unchanged."""

from app.database.importers.base_importer import BaseImporter
from app.database.importers.import_validator import require_fields
from app.models.player import Player, PlayerStatistics
from app.repositories.account_repository import AccountRepository
from app.repositories.player_repository import PlayerRepository
from app.services.account_service import normalize_username


class PlayerImporter(BaseImporter):
    filename = "players"

    async def run(self) -> None:
        accounts = AccountRepository(self.session)
        players = PlayerRepository(self.session)
        for batch in self.batches(self.load_records("players")):
            for record in batch:
                label = str(record.get("username") or record.get("nickname") or "<missing>")
                try:
                    require_fields(record, ("username", "nickname"), label)
                    username = normalize_username(str(record["username"]))
                    nickname = str(record["nickname"]).strip()
                except (ValueError, Exception) as exc:
                    self.report.errors.append(f"{label}: {exc}")
                    continue
                account = await accounts.by_username(username)
                if account is None:
                    self.report.errors.append(f"{label}: account does not exist")
                    continue
                if await players.by_account_id(account.id) is not None:
                    self.report.skipped.append(nickname)
                    continue
                if await players.by_nickname(nickname) is not None:
                    self.report.skipped.append(nickname)
                    continue
                player = Player(account_id=account.id, nickname=nickname, status="active")
                self.session.add(player)
                await self.session.flush()
                self.session.add(PlayerStatistics(player_id=player.id))
                self.report.created.append(nickname)
