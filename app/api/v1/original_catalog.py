"""Read-only catalog of the original client's battle items (weapons, ammo, armour...).

The data is text read from the original client's prop table (data/reference/original_battle_props.json):
id, type, name, icon path and stack size. Pictures are not part of it; operators upload icons to the
asset library under kind "prop" with the item id as the key. Each row also carries `stats` (armour
damage reduction, heal amounts...) from the imported prop table when storage/original_data has it.
"""

import json
from functools import lru_cache
from pathlib import Path

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin_access import require
from app.game.original_data import prop_stats
from app.infrastructure.database import get_db
from app.services.operator_service import OperatorActor
from app.services.store_listing_service import StoreListingService

router = APIRouter(prefix="/admin/original", tags=["Original client"])

_DATA = Path(__file__).resolve().parents[3] / "data" / "reference" / "original_battle_props.json"


@lru_cache(maxsize=1)
def _props() -> list[dict]:
    return json.loads(_DATA.read_text(encoding="utf-8"))["props"]


@router.get("/props")
async def list_props(
    type: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=64),
    _: OperatorActor = Depends(require("store.read")),
) -> dict:
    rows = _props()
    if type:
        rows = [r for r in rows if r["type"] == type]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r["name"].lower() or needle in r["description"].lower() or needle == str(r["id"])]
    types: dict[str, int] = {}
    for r in _props():
        types[r["type"]] = types.get(r["type"], 0) + 1
    return {"items": [{**r, "stats": prop_stats(r["id"])} for r in rows], "total": len(rows), "types": types}


@router.get("/props/{prop_id}")
async def get_prop(prop_id: int, _: OperatorActor = Depends(require("store.read"))) -> dict:
    for r in _props():
        if r["id"] == prop_id:
            return {**r, "stats": prop_stats(r["id"])}
    raise HTTPException(status_code=404, detail="Unknown prop id")


# ---- Lobby content: Depot tabs, sets, store goods, supply boxes ---------------------------------
_LOBBY = Path(__file__).resolve().parents[3] / "data" / "reference" / "original_lobby.json"
LOBBY_CATEGORIES = ("firearms", "clothes", "character", "vehicles", "items", "companions", "lobby_theme", "actions", "profile")


@lru_cache(maxsize=1)
def _lobby() -> dict:
    return json.loads(_LOBBY.read_text(encoding="utf-8"))


def _page(rows: list[dict], offset: int, limit: int) -> dict:
    return {"items": rows[offset:offset + limit], "total": len(rows), "offset": offset, "limit": limit}


def _matches(row: dict, q: str | None) -> bool:
    if not q:
        return True
    needle = q.lower()
    return needle in str(row.get("name", "")).lower() or needle == str(row["id"])


@router.get("/lobby")
async def list_lobby_items(
    category: str | None = Query(default=None, pattern="^(" + "|".join(LOBBY_CATEGORIES) + ")$"),
    q: str | None = Query(default=None, max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=120, ge=1, le=500),
    _: OperatorActor = Depends(require("store.read")),
) -> dict:
    """Lobby (Depot) items: weapon skins, clothes, character parts, vehicles, themes, companions..."""
    every = _lobby()["items"]
    rows = [r for r in every if (not category or r["category"] == category) and _matches(r, q)]
    counts: dict[str, int] = {}
    for r in every:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    return {**_page(rows, offset, limit), "categories": counts}


@router.get("/sets")
async def list_sets(_: OperatorActor = Depends(require("store.read"))) -> list[dict]:
    names = {r["id"]: r["name"] for r in _lobby()["items"]}
    return [{**s, "item_names": [names.get(i, "") for i in s["items"]]} for s in _lobby()["sets"]]


@router.get("/store")
async def list_store_goods(
    q: str | None = Query(default=None, max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=120, ge=1, le=500),
    _: OperatorActor = Depends(require("store.read")),
) -> dict:
    rows = [r for r in _lobby()["store"] if _matches(r, q)]
    return _page(rows, offset, limit)


@router.get("/supply")
async def list_supply_boxes(
    kind: str | None = Query(default=None, max_length=40),
    on_sale: bool | None = Query(default=None),
    _: OperatorActor = Depends(require("store.read")),
) -> list[dict]:
    names = {r["id"]: r["name"] for r in _lobby()["items"]}
    rows = [b for b in _lobby()["supply"] if (not kind or b["kind"] == kind) and (on_sale is None or b["on_sale"] == on_sale)]
    return [{**b, "item_count": len(b["items"]), "preview": [{"id": i, "name": names.get(i, "")} for i in b["items"][:12]]} for b in rows]


# ---- Lobby theme store listings: game default + operator override, honoured by the gateway -----
class LobbyThemeListingChange(BaseModel):
    on_sale: bool
    currency: Literal["diamond", "coin"]
    price: int = Field(ge=0, le=1_000_000)
    reason: str = Field(min_length=1, max_length=200)


def _listing_matches(row: dict, filters: dict) -> bool:
    q = filters["q"]
    if q:
        needle = q.strip().lower()
        if needle not in row["name"].lower() and needle not in row["description"].lower() and needle != str(row["id"]) and needle != str(row["goods_id"]):
            return False
    for field in ("on_sale", "currency", "overridden", "quality"):
        if filters[field] is not None and row[field] != filters[field]:
            return False
    if filters["in_store"] is not None and (row["goods_id"] is not None) != filters["in_store"]:
        return False
    if filters["has_background"] is not None and bool(row["background_url"]) != filters["has_background"]:
        return False
    return True


@router.get("/lobby-themes")
async def list_lobby_theme_listings(
    q: str | None = Query(default=None, max_length=64, description="Name, description, theme id or goods id"),
    on_sale: bool | None = Query(default=None),
    currency: Literal["diamond", "coin"] | None = Query(default=None),
    overridden: bool | None = Query(default=None),
    in_store: bool | None = Query(default=None, description="true: the client has a mall good for it (goods_id set)"),
    has_background: bool | None = Query(default=None),
    quality: int | None = Query(default=None, ge=0, le=10),
    actor: OperatorActor = Depends(require("store.read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Every lobby theme with its effective store listing; each filter matches one column."""
    filters = {"q": q, "on_sale": on_sale, "currency": currency, "overridden": overridden, "in_store": in_store,
               "has_background": has_background, "quality": quality}
    rows = [row for row in await StoreListingService(db).listings(actor) if _listing_matches(row, filters)]
    return {"items": rows, "total": len(rows)}


@router.put("/lobby-themes/{theme_id}/listing")
async def set_lobby_theme_listing(
    theme_id: int,
    body: LobbyThemeListingChange,
    actor: OperatorActor = Depends(require("store.manage")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await StoreListingService(db).set_listing(actor, theme_id, body.on_sale, body.currency, body.price, body.reason)


@router.delete("/lobby-themes/{theme_id}/listing")
async def clear_lobby_theme_listing(
    theme_id: int,
    reason: str = Query(min_length=1, max_length=200),
    actor: OperatorActor = Depends(require("store.manage")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await StoreListingService(db).clear_listing(actor, theme_id, reason)
