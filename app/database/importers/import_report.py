"""Import result shared by every importer."""

from dataclasses import dataclass, field


@dataclass
class ImportReport:
    schema_version: int = 1
    dry_run: bool = False
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "dry_run": self.dry_run,
            "created": list(self.created),
            "skipped": list(self.skipped),
            "errors": list(self.errors),
        }
