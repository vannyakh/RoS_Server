"""Import accounts without overwriting an existing username or password."""

from app.database.importers.base_importer import BaseImporter
from app.database.importers.import_validator import require_fields
from app.services.account_service import AccountService, normalize_username


class AccountImporter(BaseImporter):
    filename = "accounts"

    async def run(self) -> None:
        service = AccountService(self.session)
        for batch in self.batches(self.load_records("accounts")):
            for record in batch:
                label = str(record.get("username") or "<missing>")
                try:
                    require_fields(record, ("username", "password"), label)
                    username = normalize_username(str(record["username"]))
                except (ValueError, Exception) as exc:
                    self.report.errors.append(f"{label}: {exc}")
                    continue
                if await service.accounts.by_username(username) is not None:
                    self.report.skipped.append(username)
                    continue
                await service.register(username, str(record["password"]), record.get("email"), commit=False)
                self.report.created.append(username)
