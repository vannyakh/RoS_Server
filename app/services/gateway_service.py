"""Accounts for players who connect through the original-client gateway.

The gateway knows a player only by the uid in the Mercury login name. The first login
creates an account and a player profile, so operators see and moderate that player in
the admin console like any other account. Those accounts have no usable password.
"""

import hashlib
import re
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.models.account import Account, LoginHistory
from app.core.config import settings
from app.models.gateway import GatewayIdentity, GatewayItem
from app.models.player import Player, PlayerStatistics
from app.models.types import utc_now
from app.schemas.gateway import (
    GatewayAccount,
    GatewayItemView,
    GatewayOutfit,
    GatewayPurchaseResult,
    GatewayState,
)
from app.services.inventory_service import InventoryService

_UNSAFE = re.compile(r"[^a-z0-9_]")
USERNAME_PREFIX = "gw_"
YUANBAO = "yuanbao"   # original-client diamonds, kept in the normal currency ledger


def gateway_username(external_uid: str) -> str:
    cleaned = _UNSAFE.sub("_", external_uid.casefold())
    if len(USERNAME_PREFIX + cleaned) <= 32:
        return USERNAME_PREFIX + cleaned
    return USERNAME_PREFIX + hashlib.sha256(external_uid.encode()).hexdigest()[:29]


class GatewayService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, external_uid: str, ip_address: str | None) -> GatewayAccount:
        identity = await self._identity(external_uid)
        if identity is None:
            identity = await self._create(external_uid)
        account = await self.session.get(Account, identity.account_id)
        player = await self._player(identity.account_id)
        now = utc_now()
        identity.last_login_at = now
        identity.last_ip = ip_address
        allowed = account.status == "active"
        if allowed:
            account.last_login_at = now
        self.session.add(
            LoginHistory(account_id=account.id, login_status="success" if allowed else "failure", ip_address=ip_address)
        )
        await self.session.commit()
        return self._view(account, player, identity)

    async def set_character(self, external_uid: str, nickname: str, char_type: int) -> GatewayAccount:
        identity = await self._identity(external_uid)
        if identity is None:
            raise AppError(404, "Gateway identity was not found")
        account = await self.session.get(Account, identity.account_id)
        player = await self._player(identity.account_id)
        cleaned = nickname.strip()
        if not cleaned:
            raise AppError(422, "Nickname is required")
        taken = await self.session.scalar(select(Player.id).where(Player.nickname == cleaned, Player.id != player.id))
        if taken is not None:
            raise AppError(409, "Nickname is already taken")
        player.nickname = cleaned
        identity.char_type = char_type
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(409, "Nickname is already taken") from exc
        return self._view(account, player, identity)

    async def set_portrait(self, external_uid: str, portrait: str) -> GatewayAccount:
        identity = await self._identity(external_uid)
        if identity is None:
            raise AppError(404, "Gateway identity was not found")
        account = await self.session.get(Account, identity.account_id)
        player = await self._player(identity.account_id)
        identity.portrait = portrait
        await self.session.commit()
        return self._view(account, player, identity)

    async def state(self, external_uid: str) -> GatewayState:
        identity, player = await self._known(external_uid)
        yuanbao = await self._yuanbao(player.id)
        await self.session.commit()
        items = (
            await self.session.scalars(
                select(GatewayItem).where(GatewayItem.identity_id == identity.id).order_by(GatewayItem.prop_id)
            )
        ).all()
        return GatewayState(
            yuanbao=yuanbao,
            items=[GatewayItemView(prop_id=i.prop_id, number=i.number) for i in items],
            outfit=GatewayOutfit(**(identity.outfit or {})),
        )

    async def purchase(self, external_uid: str, price: int, props: list[int], reason: str) -> GatewayPurchaseResult:
        """Charge diamonds and add the items in one transaction (409 if the balance is too low)."""
        identity, player = await self._known(external_uid)
        balance = await self._yuanbao(player.id)
        if price:
            row = await InventoryService(self.session).apply_currency(
                player.id, YUANBAO, -price, f"gateway:{reason}", commit=False
            )
            balance = row.balance
        added = []
        for prop_id in props:
            item = await self.session.scalar(
                select(GatewayItem).where(GatewayItem.identity_id == identity.id, GatewayItem.prop_id == prop_id)
            )
            if item is None:
                self.session.add(GatewayItem(identity_id=identity.id, prop_id=prop_id, number=1))
                await self.session.flush()
                added.append(prop_id)
            else:
                item.number += 1
        await self.session.commit()
        return GatewayPurchaseResult(yuanbao=balance, added=added)

    async def set_outfit(self, external_uid: str, outfit: GatewayOutfit) -> GatewayOutfit:
        identity, _player = await self._known(external_uid)
        identity.outfit = outfit.model_dump()
        await self.session.commit()
        return outfit

    async def _known(self, external_uid: str) -> tuple[GatewayIdentity, Player]:
        identity = await self._identity(external_uid)
        if identity is None:
            raise AppError(404, "Gateway identity was not found")
        return identity, await self._player(identity.account_id)

    async def _yuanbao(self, player_id: str) -> int:
        """Diamond balance; a player without a row yet gets the starting amount (ledger: gateway:start)."""
        inventory = InventoryService(self.session)
        row = await inventory.inventory.currency(player_id, YUANBAO)
        if row is None:
            if settings.gateway_starting_yuanbao <= 0:
                return 0
            row = await inventory.apply_currency(
                player_id, YUANBAO, settings.gateway_starting_yuanbao, "gateway:start", commit=False
            )
        return row.balance

    async def _identity(self, external_uid: str) -> GatewayIdentity | None:
        return await self.session.scalar(select(GatewayIdentity).where(GatewayIdentity.external_uid == external_uid))

    async def _player(self, account_id: str) -> Player:
        player = await self.session.scalar(select(Player).where(Player.account_id == account_id))
        if player is None:
            raise AppError(409, "Gateway account has no player profile")
        return player

    async def _create(self, external_uid: str) -> GatewayIdentity:
        username = gateway_username(external_uid)
        if await self.session.scalar(select(Account.id).where(Account.username == username)) is not None:
            raise AppError(409, "A non-gateway account already uses this username")
        # Nobody can sign in to this account with a password: the hash is of a discarded random value.
        account = Account(username=username, password_hash=hash_password(secrets.token_urlsafe(32)), status="active")
        self.session.add(account)
        await self.session.flush()
        player = Player(account_id=account.id, nickname=username, status="active")
        self.session.add(player)
        await self.session.flush()
        self.session.add(PlayerStatistics(player_id=player.id))
        from app.services.cosmetics_service import ensure_starter

        await ensure_starter(self.session, player, commit=False)
        identity = GatewayIdentity(account_id=account.id, external_uid=external_uid)
        self.session.add(identity)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(409, "Gateway identity already exists") from exc
        return identity

    @staticmethod
    def _view(account: Account, player: Player, identity: GatewayIdentity) -> GatewayAccount:
        return GatewayAccount(
            account_id=account.id,
            username=account.username,
            status=account.status,
            can_play=account.status == "active",
            is_new=identity.char_type is None,
            nickname=player.nickname,
            char_type=identity.char_type,
            portrait=identity.portrait or "",
        )
