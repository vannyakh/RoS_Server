"""Lobby theme store listings: the game's own mall listing plus an optional operator override.

Game defaults come from data/reference/original_lobby.json: the 21 `lobby_theme` items and the
`store` rows (the client's mall goods, extracted from its mall_utils tables) whose `item_id` is a
theme. A theme with no mall good cannot appear in the client's store, so it cannot be put on sale.
"""

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.game_asset import GameAsset
from app.models.operator import Operator
from app.models.store_listing import StoreListingOverride
from app.services.asset_service import view as asset_view
from app.services.operator_service import OperatorActor, OperatorService

_LOBBY = Path(__file__).resolve().parents[2] / "data" / "reference" / "original_lobby.json"
CATEGORY = "lobby_theme"
# Client const.MallCurrencyType names in the store rows -> the listing currency.
_CURRENCY = {"YUANBAO": "diamond", "GP": "coin"}


@lru_cache(maxsize=1)
def _catalog() -> tuple[list[dict], dict[int, dict]]:
    data = json.loads(_LOBBY.read_text(encoding="utf-8"))
    themes = [r for r in data["items"] if r["category"] == CATEGORY]
    ids = {r["id"] for r in themes}
    goods: dict[int, dict] = {}
    for good in data["store"]:
        item = good.get("item_id")
        if item in ids and item not in goods:
            goods[item] = good
    return themes, goods


def _default(theme_id: int) -> dict:
    good = _catalog()[1].get(theme_id)
    if good is None:
        return {"goods_id": None, "default_on_sale": False, "default_currency": None, "default_price": None}
    price = int(good["price"]) * int(good.get("discount", 100)) // 100
    return {
        "goods_id": int(good["id"]),
        "default_on_sale": True,
        "default_currency": _CURRENCY.get(good["currency"]),
        "default_price": price,
    }


class StoreListingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.operators = OperatorService(session)

    async def listings(self, actor: OperatorActor) -> list[dict]:
        self.operators._need(actor, "store.read")
        overrides = {row.item_id: row for row in await self.session.scalars(select(StoreListingOverride))}
        names = await self._operator_names({row.updated_by for row in overrides.values()})
        backgrounds = {
            row.key: asset_view(row)["url"]
            for row in await self.session.scalars(select(GameAsset).where(GameAsset.kind == "background"))
        }
        return [self._view(theme, overrides.get(theme["id"]), names, backgrounds) for theme in _catalog()[0]]

    async def set_listing(self, actor: OperatorActor, theme_id: int, on_sale: bool, currency: str, price: int, reason: str) -> dict:
        self.operators._need(actor, "store.manage")
        theme = self._theme(theme_id)
        if on_sale and _default(theme_id)["goods_id"] is None:
            raise AppError(422, "This theme has no store good in the client, so it cannot be put on sale")
        row = await self.session.scalar(select(StoreListingOverride).where(StoreListingOverride.item_id == theme_id))
        if row is None:
            row = StoreListingOverride(item_id=theme_id, category=CATEGORY)
            self.session.add(row)
        row.on_sale, row.currency, row.price, row.updated_by = on_sale, currency, price, actor.operator.id
        state = f"{currency} {price}" if on_sale else "off sale"
        await self.operators._audit(actor, "store.listing", CATEGORY, str(theme_id), f"{theme['name']}: {state}", reason.strip())
        await self.session.commit()
        return await self._one(theme)

    async def clear_listing(self, actor: OperatorActor, theme_id: int, reason: str) -> dict:
        self.operators._need(actor, "store.manage")
        theme = self._theme(theme_id)
        row = await self.session.scalar(select(StoreListingOverride).where(StoreListingOverride.item_id == theme_id))
        if row is not None:
            await self.session.delete(row)
        await self.operators._audit(actor, "store.listing", CATEGORY, str(theme_id), f"{theme['name']}: game default", reason.strip())
        await self.session.commit()
        return await self._one(theme)

    async def gateway_listings(self) -> list[dict]:
        """Overridden listings only; the gateway keeps the client's own table for the rest."""
        rows = await self.session.scalars(select(StoreListingOverride).order_by(StoreListingOverride.item_id))
        return [
            {"item_id": r.item_id, "goods_id": _default(r.item_id)["goods_id"], "on_sale": r.on_sale, "currency": r.currency, "price": r.price}
            for r in rows
        ]

    @staticmethod
    def _theme(theme_id: int) -> dict:
        for theme in _catalog()[0]:
            if theme["id"] == theme_id:
                return theme
        raise AppError(404, "Unknown lobby theme id")

    async def _one(self, theme: dict) -> dict:
        row = await self.session.scalar(select(StoreListingOverride).where(StoreListingOverride.item_id == theme["id"]))
        names = await self._operator_names({row.updated_by} if row else set())
        asset = await self.session.scalar(select(GameAsset).where(GameAsset.kind == "background", GameAsset.key == str(theme["id"])))
        return self._view(theme, row, names, {asset.key: asset_view(asset)["url"]} if asset else {})

    async def _operator_names(self, ids: set[str | None]) -> dict[str, str]:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        return {op.id: op.username for op in await self.session.scalars(select(Operator).where(Operator.id.in_(ids)))}

    @staticmethod
    def _view(theme: dict, row: StoreListingOverride | None, names: dict[str, str], backgrounds: dict[str, str]) -> dict:
        default = _default(theme["id"])
        if row is not None:
            on_sale, currency, price = row.on_sale, row.currency, row.price
        else:
            on_sale, currency, price = default["default_on_sale"], default["default_currency"] or "diamond", default["default_price"] or 0
        return {
            "id": theme["id"],
            "name": theme["name"],
            "description": theme.get("description", ""),
            "quality": int(theme.get("quality") or 0),
            "icon_path": theme.get("icon_path", ""),
            **default,
            "on_sale": on_sale,
            "currency": currency,
            "price": price,
            "overridden": row is not None,
            "background_url": backgrounds.get(str(theme["id"]), ""),
            "updated_at": row.updated_at.isoformat() if row is not None else None,
            "updated_by": names.get(row.updated_by) if row is not None and row.updated_by else None,
        }
