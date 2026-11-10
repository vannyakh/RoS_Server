---
name: performance-audit
description: Reviews indexes, query loading, pooling, and tick isolation for RoS_Server. Use when a change adds a list endpoint, a relationship, or a hot-path query.
---

# Performance audit

## When

A change adds a list endpoint, a relationship traversal, or a write on a frequently called path.

## Input

The query, the filter, and the expected row growth (players, matches, or history).

## Workflow

1. Confirm the filter columns are covered by a unique key or an explicit index.
2. Confirm relationships used by that query are loaded with `selectinload` once, not per row.
3. Keep SQLite on a null pool and PostgreSQL on the configured pool size.
4. Keep match positions out of SQL. Redis remains optional until a measured need exists.
5. Paginate collection endpoints with the existing `Page` schema.
6. Do not add a cache during the audit. Record the measurement that would justify one.

## Checklist

- Lookup columns are indexed
- No per-row lazy load
- Tick path still has no database call
- Pagination has a bound

## Output

The index or query change, or a note that no change is justified yet.

## Failure

If the only evidence is a guess about row counts, report that and leave the query unchanged.
