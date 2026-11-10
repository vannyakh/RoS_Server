# Data formats

OBSERVED FACT: ADR-0003 says primary keys are UUID strings and JSON columns use `PortableJSON`. The Python attribute is `details` because `metadata` is reserved by SQLAlchemy.

OBSERVED FACT: Session rows store a SHA-256 hex digest of the bearer token. New tokens include a unique `jti`. The raw token and the hash are not response fields. Source: `app/core/security.py` and ADR-0007.

OBSERVED FACT: Live match positions stay in memory. Stored match rows use the statuses `scheduled`, `lobby`, `running`, `completed`, and `cancelled`. Source: `app/models/match.py` and ADR-0008.

INTERPRETATION: These are this server's storage formats. They let one Alembic revision target SQLite and PostgreSQL.

HYPOTHESIS: Original client save files or network payloads use different layouts. Those layouts are not in the repository.

IMPLEMENTATION IMPACT: Do not replace UUID keys or `PortableJSON` without a new architecture decision. Do not describe these columns as original client formats.
