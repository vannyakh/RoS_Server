"""Accounts for players who connect through the original-client gateway.

The gateway knows a player only by the uid in the Mercury login name. The first login
creates an account and a player profile, so operators see and moderate that player in
the admin console like any other account. Those accounts have no usable password.
"""

import asyncio
import hashlib
import re
import secrets
import weakref

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.geoip import country_for
from app.core.security import hash_password
from app.models.account import Account, LoginHistory
from app.core.config import settings
from app.models.gateway import GatewayIdentity, GatewayItem
from app.models.inventory import CurrencyTransaction, PlayerCurrency
from app.models.player import Player, PlayerStatistics
from app.models.types import utc_now
from app.schemas.gateway import GatewayDevice
from app.schemas.gateway import (
    GatewayAccount,
    GatewayCompoundRequest,
    GatewayCompoundResult,
    GatewayCurrencyAmount,
    GatewayPropCount,
    GatewayItemView,
    GatewayOutfit,
    GatewayPurchaseResult,
    GatewayTopupResult,
    GatewayState,
)
from app.networking.admin_hub import admin_hub
from app.services.inventory_service import InventoryService

_UNSAFE = re.compile(r"[^a-z0-9_]")
USERNAME_PREFIX = "gw_"
YUANBAO = "yuanbao"   # original-client diamonds, kept in the normal currency ledger
GOLD = "gold"         # original-client gold coins (client currency id 1), same ledger
GOLD_ID = 1
WORKSHOP_NOTE = "workshop:"  # CurrencyTransaction.note prefix that holds a compound request_id
PURCHASE_NOTE = "purchase:"  # CurrencyTransaction.note prefix that holds a purchase request_id
RECENT_GOT_LIMIT = 20
_PURCHASE_STRIPES = 64
_purchase_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, list[asyncio.Lock]]" = (
    weakref.WeakKeyDictionary()
)


def _purchase_lock(player_id: str) -> asyncio.Lock:
    """Striped per-player lock for idempotent purchases, one set per event loop."""
    loop = asyncio.get_running_loop()
    locks = _purchase_locks.get(loop)
    if locks is None:
        locks = [asyncio.Lock() for _ in range(_PURCHASE_STRIPES)]
        _purchase_locks[loop] = locks
    stripe = int.from_bytes(hashlib.sha256(player_id.encode()).digest()[:4], "big") % _PURCHASE_STRIPES
    return locks[stripe]


def _recent_from_outfit(outfit: dict | None) -> list[int]:
    raw = (outfit or {}).get("recent_got")
    if not isinstance(raw, list):
        return []
    return [int(x) for x in raw[:RECENT_GOT_LIMIT]]


def bootstrap_recent_got(state: dict | None, appearance_ids: set[int]) -> list[int]:
    """Build recentGotPropIDList from saved rows or owned appearance props (accounts before recent tracking)."""
    if not state:
        return []
    recent = [int(x) for x in (state.get("recent_got") or []) if int(x) in appearance_ids]
    if not recent:
        recent = _recent_from_outfit(state.get("outfit") if isinstance(state.get("outfit"), dict) else None)
    if recent:
        return recent[:RECENT_GOT_LIMIT]
    seen: set[int] = set()
    out: list[int] = []
    for row in reversed(state.get("items") or []):
        pid = int(row["prop_id"] if isinstance(row, dict) else row)
        if pid in seen or pid not in appearance_ids:
            continue
        seen.add(pid)
        out.append(pid)
        if len(out) >= RECENT_GOT_LIMIT:
            break
    return out


def _merge_recent(existing: list[int], props: list[int]) -> list[int]:
    """Newest acquisitions first; one row per prop id (multi-draw keeps draw order)."""
    seen: set[int] = set()
    merged: list[int] = []
    for prop_id in props + existing:
        pid = int(prop_id)
        if pid in seen:
            continue
        seen.add(pid)
        merged.append(pid)
        if len(merged) >= RECENT_GOT_LIMIT:
            break
    return merged


def _summed(rows: list[GatewayPropCount]) -> dict[int, int]:
    totals: dict[int, int] = {}
    for row in rows:
        totals[row.prop_id] = totals.get(row.prop_id, 0) + row.number
    return totals


def _gold_amount(rows: list[GatewayCurrencyAmount]) -> int:
    return sum(row.amount for row in rows if row.currency_id == GOLD_ID)


def _prop_list(rows: list[GatewayPropCount]) -> list[dict]:
    return [{"prop_id": row.prop_id, "number": row.number} for row in rows]


def _insufficient(missing: list[dict]) -> AppError:
    return AppError(409, {"code": "insufficient", "missing": missing})  # type: ignore[arg-type]


def gateway_username(external_uid: str) -> str:
    cleaned = _UNSAFE.sub("_", external_uid.casefold())
    if len(USERNAME_PREFIX + cleaned) <= 32:
        return USERNAME_PREFIX + cleaned
    return USERNAME_PREFIX + hashlib.sha256(external_uid.encode()).hexdigest()[:29]


class GatewayService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, external_uid: str, ip_address: str | None, device: GatewayDevice | None = None) -> GatewayAccount:
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
            LoginHistory(
                account_id=account.id,
                login_status="success" if allowed else "failure",
                ip_address=ip_address,
                source="game",
                country=country_for(ip_address),
                device_model=device.model if device else None,
                os_name=device.os_name if device else None,
                client_version=device.client_version if device else None,
                time_zone=device.time_zone if device else None,
                language=device.language if device else None,
            )
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

    async def set_head_frame(self, external_uid: str, head_frame: int) -> GatewayAccount:
        identity = await self._identity(external_uid)
        if identity is None:
            raise AppError(404, "Gateway identity was not found")
        account = await self.session.get(Account, identity.account_id)
        player = await self._player(identity.account_id)
        identity.head_frame = head_frame
        await self.session.commit()
        return self._view(account, player, identity)

    async def set_national_flag(self, external_uid: str, national_flag: str) -> GatewayAccount:
        identity = await self._identity(external_uid)
        if identity is None:
            raise AppError(404, "Gateway identity was not found")
        account = await self.session.get(Account, identity.account_id)
        player = await self._player(identity.account_id)
        identity.national_flag = national_flag.upper()
        await self.session.commit()
        return self._view(account, player, identity)

    async def state(self, external_uid: str) -> GatewayState:
        identity, player = await self._known(external_uid)
        yuanbao = await self._yuanbao(player.id)
        gold = (await self._gold_row(player.id)).balance
        await self.session.commit()
        return await self._state_view(identity, yuanbao, gold)

    async def _state_view(self, identity: GatewayIdentity, yuanbao: int, gold: int) -> GatewayState:
        items = (
            await self.session.scalars(
                select(GatewayItem)
                .where(GatewayItem.identity_id == identity.id, GatewayItem.number > 0)
                .order_by(GatewayItem.prop_id)
            )
        ).all()
        raw = identity.outfit or {}
        fields = GatewayOutfit.model_fields
        return GatewayState(
            yuanbao=yuanbao,
            items=[GatewayItemView(prop_id=i.prop_id, number=i.number) for i in items],
            outfit=GatewayOutfit(**{k: raw[k] for k in fields if k in raw}),
            head_frame=identity.head_frame or 0,
            recent_got=_recent_from_outfit(identity.outfit),
            currencies={str(GOLD_ID): gold},
        )

    def _save_recent(self, identity: GatewayIdentity, props: list[int]) -> list[int]:
        if not props:
            return _recent_from_outfit(identity.outfit)
        data = dict(identity.outfit or {})
        data["recent_got"] = _merge_recent(_recent_from_outfit(identity.outfit), [int(p) for p in props])
        identity.outfit = data
        return data["recent_got"]

    async def compound(self, external_uid: str, body: GatewayCompoundRequest) -> GatewayCompoundResult:
        """Workshop upgrade in one transaction: check `require` and `consume` counts and gold,
        then take the consumed props and gold and add `add`. A refusal (409, code "insufficient")
        changes nothing. A request_id already applied for this player returns its stored result
        with replayed=true. The request_id is kept in the gold ledger row's note."""
        identity, player = await self._known(external_uid)
        note = WORKSHOP_NOTE + body.request_id
        done = await self.session.scalar(
            select(CurrencyTransaction).where(
                CurrencyTransaction.player_id == player.id,
                CurrencyTransaction.currency_code == GOLD,
                CurrencyTransaction.note == note,
            )
        )
        if done is not None and isinstance(done.details, dict) and "result" in done.details:
            return GatewayCompoundResult(**{**done.details["result"], "replayed": True})

        require, consume, add = _summed(body.require), _summed(body.consume), _summed(body.add)
        price = _gold_amount(body.consume_currency)
        gold = await self._gold_row(player.id)
        touched = sorted(set(require) | set(consume) | set(add))
        counts = await self._counts(identity.id, touched)

        missing = []
        for kind, needed in (("require", require), ("consume", consume)):
            for prop_id, number in sorted(needed.items()):
                have = counts.get(prop_id, 0)
                if have < number:
                    missing.append({"kind": kind, "prop_id": prop_id, "need": number, "have": have})
        if gold.balance < price:
            missing.append({"kind": "currency", "currency_id": GOLD_ID, "need": price, "have": gold.balance})
        if missing:
            await self.session.rollback()
            raise _insufficient(missing)

        # Conditional updates: a change between the check and the write cannot take a count or
        # the balance below zero; if one misses, the whole transaction is rolled back.
        for prop_id, number in consume.items():
            taken = await self.session.execute(
                update(GatewayItem)
                .where(
                    GatewayItem.identity_id == identity.id,
                    GatewayItem.prop_id == prop_id,
                    GatewayItem.number >= number,
                )
                .values(number=GatewayItem.number - number)
                .execution_options(synchronize_session=False)
            )
            if taken.rowcount != 1:
                await self.session.rollback()
                raise _insufficient([{"kind": "consume", "prop_id": prop_id, "need": number}])
        if price:
            paid = await self.session.execute(
                update(PlayerCurrency)
                .where(PlayerCurrency.id == gold.id, PlayerCurrency.balance >= price)
                .values(balance=PlayerCurrency.balance - price)
                .execution_options(synchronize_session=False)
            )
            if paid.rowcount != 1:
                await self.session.rollback()
                raise _insufficient([{"kind": "currency", "currency_id": GOLD_ID, "need": price}])
        await self._add_items(identity.id, add)
        self._save_recent(identity, [prop_id for prop_id, number in add.items() for _ in range(number)])
        await self.session.flush()

        # Column reads, not ORM objects: the bulk updates above bypassed the identity map.
        counts = await self._counts(identity.id, touched)
        balance = await self.session.scalar(select(PlayerCurrency.balance).where(PlayerCurrency.id == gold.id))
        result = GatewayCompoundResult(
            items=[GatewayItemView(prop_id=p, number=counts.get(p, 0)) for p in touched],
            currencies={str(GOLD_ID): balance},
            replayed=False,
        )
        self.session.add(
            CurrencyTransaction(
                player_id=player.id,
                currency_code=GOLD,
                amount=-price,
                balance_after=balance,
                reason=f"gateway:workshop:{body.reason}"[:64],
                note=note,
                details={
                    "request_id": body.request_id,
                    "require": _prop_list(body.require),
                    "consume": _prop_list(body.consume),
                    "add": _prop_list(body.add),
                    "result": result.model_dump(exclude={"replayed"}),
                },
            )
        )
        await self.session.commit()
        return result

    async def dev_grant(
        self, external_uid: str, props: list[GatewayPropCount], currencies: list[GatewayCurrencyAmount]
    ) -> GatewayState:
        """Development only (the route answers 404 elsewhere): add props and gold."""
        identity, player = await self._known(external_uid)
        summed = _summed(props)
        await self._add_items(identity.id, summed)
        self._save_recent(identity, [prop_id for prop_id, number in summed.items() for _ in range(number)])
        gold = await self._gold_row(player.id)
        amount = _gold_amount(currencies)
        if amount:
            gold = await InventoryService(self.session).apply_currency(
                player.id, GOLD, amount, "gateway:dev_grant", commit=False
            )
        balance = gold.balance
        yuanbao = await self._yuanbao(player.id)
        await self.session.commit()
        return await self._state_view(identity, yuanbao, balance)

    async def _counts(self, identity_id: str, prop_ids: list[int]) -> dict[int, int]:
        if not prop_ids:
            return {}
        rows = await self.session.execute(
            select(GatewayItem.prop_id, GatewayItem.number).where(
                GatewayItem.identity_id == identity_id, GatewayItem.prop_id.in_(prop_ids)
            )
        )
        return {prop_id: number for prop_id, number in rows}

    async def _add_items(self, identity_id: str, add: dict[int, int]) -> None:
        for prop_id, number in add.items():
            found = await self.session.scalar(
                select(GatewayItem.id).where(GatewayItem.identity_id == identity_id, GatewayItem.prop_id == prop_id)
            )
            if found is None:
                self.session.add(GatewayItem(identity_id=identity_id, prop_id=prop_id, number=number))
                await self.session.flush()
            else:
                await self.session.execute(
                    update(GatewayItem)
                    .where(GatewayItem.id == found)
                    .values(number=GatewayItem.number + number)
                    .execution_options(synchronize_session=False)
                )

    async def purchase(
        self, external_uid: str, price: int, props: list[int], reason: str, *, request_id: str | None = None
    ) -> GatewayPurchaseResult:
        """Charge diamonds and add the items in one transaction (409 if the balance is too low).

        With a request_id, the purchase is recorded in one diamond ledger row whose note is
        PURCHASE_NOTE + request_id (amount 0 for a free draw). A repeat for the same player
        returns the stored result with replayed=true and changes nothing; the same id with a
        different price or props is refused (409, code "request_id_reused")."""
        if request_id is None:
            identity, player = await self._known(external_uid)
            balance = await self._yuanbao(player.id)
            if price:
                row = await InventoryService(self.session).apply_currency(
                    player.id, YUANBAO, -price, f"gateway:{reason}", commit=False
                )
                balance = row.balance
            added = await self._grant_purchase(identity, props)
            recent = self._save_recent(identity, props)
            await self.session.commit()
            return GatewayPurchaseResult(yuanbao=balance, added=added, recent_got=recent)

        identity, player = await self._known(external_uid)
        # One process serves the API: the lock makes check-then-write atomic per player.
        async with _purchase_lock(player.id):
            return await self._purchase_once(identity, player, price, props, reason, request_id)

    async def topup_yuanbao(self, external_uid: str, amount: int, reference: str, reason: str) -> GatewayTopupResult:
        """Credit diamonds for a private IAP reference. A repeat for the same player returns replayed=true."""
        identity, player = await self._known(external_uid)
        reference = reference.strip()[:40]
        key = f"topup:{reference}"[:64]
        done = await self.session.scalar(
            select(CurrencyTransaction).where(
                CurrencyTransaction.player_id == player.id,
                CurrencyTransaction.currency_code == YUANBAO,
                CurrencyTransaction.reason == key,
                CurrencyTransaction.amount > 0,
            )
        )
        if done is not None:
            balance = int(done.balance_after)
            await self.session.rollback()
            return GatewayTopupResult(yuanbao=balance, replayed=True)
        row = await InventoryService(self.session).apply_currency(
            player.id, YUANBAO, int(amount), key, commit=False, details={"gateway_reason": reason[:64]}
        )
        await self.session.commit()
        return GatewayTopupResult(yuanbao=int(row.balance), replayed=False)

    async def _purchase_once(
        self, identity: GatewayIdentity, player: Player, price: int, props: list[int], reason: str, request_id: str
    ) -> GatewayPurchaseResult:
        note = PURCHASE_NOTE + request_id
        done = await self.session.scalar(
            select(CurrencyTransaction).where(
                CurrencyTransaction.player_id == player.id,
                CurrencyTransaction.currency_code == YUANBAO,
                CurrencyTransaction.note == note,
            )
        )
        if done is not None and isinstance(done.details, dict) and "result" in done.details:
            if done.details.get("price") != price or done.details.get("props") != list(props):
                await self.session.rollback()
                raise AppError(
                    409,
                    {  # type: ignore[arg-type]
                        "code": "request_id_reused",
                        "message": "request_id was already used for a purchase with a different price or props",
                    },
                )
            stored = dict(done.details["result"])  # read before rollback expires the row
            await self.session.rollback()
            return GatewayPurchaseResult(**{**stored, "replayed": True})

        balance = await self._yuanbao(player.id)
        if price:
            row = await InventoryService(self.session).inventory.currency(player.id, YUANBAO)
            if row is None or row.balance < price:
                await self.session.rollback()
                raise AppError(409, "Insufficient balance")
            paid = await self.session.execute(
                update(PlayerCurrency)
                .where(PlayerCurrency.id == row.id, PlayerCurrency.balance >= price)
                .values(balance=PlayerCurrency.balance - price)
                .execution_options(synchronize_session=False)
            )
            if paid.rowcount != 1:
                await self.session.rollback()
                raise AppError(409, "Insufficient balance")
            balance = await self.session.scalar(select(PlayerCurrency.balance).where(PlayerCurrency.id == row.id))
        added = await self._grant_purchase(identity, props)
        recent = self._save_recent(identity, props)
        result = GatewayPurchaseResult(yuanbao=balance, added=added, recent_got=recent, replayed=False)
        self.session.add(
            CurrencyTransaction(
                player_id=player.id,
                currency_code=YUANBAO,
                amount=-price,
                balance_after=balance,
                reason=f"gateway:{reason}",  # same reason as the path without request_id
                note=note,
                details={
                    "request_id": request_id,
                    "price": price,
                    "props": list(props),
                    "result": result.model_dump(exclude={"replayed"}),
                },
            )
        )
        await self.session.commit()
        return result

    async def _grant_purchase(self, identity: GatewayIdentity, props: list[int]) -> list[int]:
        """Add one of each prop; return the props the player did not own before."""
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
                if item.number <= 0:
                    added.append(prop_id)  # a Workshop compound can leave a row at 0
                item.number += 1
        return added

    async def set_outfit(self, external_uid: str, outfit: GatewayOutfit) -> GatewayOutfit:
        identity, _player = await self._known(external_uid)
        data = outfit.model_dump()
        prev = identity.outfit or {}
        if not data.get("recent_got") and prev.get("recent_got"):
            data["recent_got"] = prev["recent_got"]
        identity.outfit = data
        await self.session.commit()
        return GatewayOutfit(**{k: data[k] for k in GatewayOutfit.model_fields if k in data})

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

    async def _gold_row(self, player_id: str) -> PlayerCurrency:
        """Gold row; created on first use with GATEWAY_START_GOLD (ledger: gateway:start)."""
        inventory = InventoryService(self.session)
        row = await inventory.inventory.currency(player_id, GOLD)
        if row is None:
            start = max(settings.gateway_start_gold, 0)
            if start:
                row = await inventory.apply_currency(player_id, GOLD, start, "gateway:start", commit=False)
            else:
                row = PlayerCurrency(player_id=player_id, currency_code=GOLD, balance=0)
                self.session.add(row)
                await self.session.flush()
        return row

    async def report_presence(self, external_uid: str, online: bool) -> bool:
        """Session report from the gateway. Returns whether the account now counts as online."""
        identity = await self._identity(external_uid)
        if identity is None:
            raise AppError(404, "Gateway account was not found")
        admin_hub.gateway_presence(identity.account_id, online)
        return admin_hub.is_online(identity.account_id)

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
            national_flag=identity.national_flag or "",
            head_frame=identity.head_frame or 0,
        )
