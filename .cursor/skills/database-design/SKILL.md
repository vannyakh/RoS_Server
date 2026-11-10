---
name: database-design
description: Designs SQLAlchemy 2 models, foreign keys, unique constraints, and indexes for RoS_Server. Use when adding or changing tables in app/models.
---

# Database design

## When

A task adds a table, a foreign key, a uniqueness rule, or an index.

## Input

The entity, its owner (account, player, match, or catalog), and the lookup used by the API.

## Workflow

1. Subclass the mixins in `app/models/types.py`. Use `new_id()` and `utc_now()`.
2. Name the table in the plural snake case already used (`accounts`, `match_participants`).
3. Add the foreign key in the child table. Set `ondelete` explicitly.
4. Add a unique constraint for a one-to-one or a membership pair such as `(match_id, player_id)`.
5. Set `lazy="raise"` on relationships. Do not rely on implicit lazy loads.
6. Store documents with `PortableJSON` and the attribute `details`.
7. Export the model from `app/models/__init__.py`.
8. Leave the Alembic revision to the data-migration engineer.

## Checklist

- Primary key is a UUID string
- Required uniqueness is a database constraint
- Numeric totals reject negatives with a check constraint
- No position or aim columns on match tables

## Output

The model module and a list of constraints the migration must create.

## Failure

If an existing applied revision already created the table, do not rewrite that revision. Describe a follow-up revision instead.
