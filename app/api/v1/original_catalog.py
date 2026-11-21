"""Read-only catalog of the original client's battle items (weapons, ammo, armour...).

The data is text read from the original client's prop table (data/reference/original_battle_props.json):
id, type, name, icon path and stack size. Pictures are not part of it; operators upload icons to the
asset library under kind "prop" with the item id as the key. Each row also carries `stats` (armour
damage reduction, heal amounts...) from the imported prop table when storage/original_data has it.
"""

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.admin_access import require
from app.game.original_data import prop_stats
from app.services.operator_service import OperatorActor

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
