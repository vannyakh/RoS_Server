---
name: fastapi-development
description: Adds FastAPI routes, Pydantic v2 schemas, services, and repositories for RoS_Server. Use when changing app/api, app/schemas, app/services, or app/repositories.
---

# FastAPI development

## When

A task adds or changes an HTTP contract.

## Input

The route, the request fields, the response fields, and the service that owns the rule.

## Workflow

1. Define the request and response in `app/schemas/`. Use `Page` from `app/schemas/common.py` for collections.
2. Add the query to the matching repository. Load relationships there with `selectinload`.
3. Put the transaction in the service. Routes depend on `get_db` and call the service.
4. Map expected failures to `AppError` with a 4xx status.
5. Exclude `password_hash` and `token_hash` from every response.
6. Cover the route with an existing test client fixture in `tests/conftest.py`.

## Checklist

- Router has no `select()` and no `commit()`
- Response model is explicit
- Optional fields are optional in the schema
- Auth uses `current_account` and checks `status == "active"`

## Output

The route, schema, service method, and the pytest command that hit the route.

## Failure

If the handler needs a column that does not exist, stop. Do not alter `app/models` from an API task.
