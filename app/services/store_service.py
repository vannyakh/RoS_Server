"""Store administration over the currency ledger: spend, top-ups, refunds and the skin catalog.

Every balance change is already a `currency_transactions` row. This service reads that ledger
for the admin panel and adds two operator writes: a top-up (credit against an order
reference) and a refund (credit back a purchase). No payment provider is involved.
"""

import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.account import Account
from app.models.inventory import CurrencyTransaction, PlayerCurrency
from app.models.player import Player
from app.networking.admin_hub import admin_hub
from app.services.cosmetics_service import SKINS
from app.services.operator_service import OperatorActor, OperatorService

KINDS = ("purchase", "draw", "topup", "refund", "grant", "admin")
MALL = re.compile(r"^gateway:mall:(\d+)x(\d+)$")
DRAW = re.compile(r"^gateway:draw:(\d+)$")
CODE = re.compile(r"[a-z0-9_]{1,16}")


def kind_of(reason: str) -> str:
    if reason == "skin_purchase" or reason.startswith("gateway:mall:") or reason.startswith("gateway:buy"):
        return "purchase"
    if reason.startswith("gateway:draw:"):
        return "draw"
    if reason.startswith("topup:"):
        return "topup"
    if reason.startswith("refund:"):
        return "refund"
    if reason == "admin_adjust":
        return "admin"
    return "grant"


def item_of(row: CurrencyTransaction) -> str | None:
    """What was bought: 'mall 9183 ×1', 'draw pool 13', a skin code, or None."""
    mall = MALL.match(row.reason)
    if mall:
        return f"mall {mall.group(1)} ×{mall.group(2)}"
    draw = DRAW.match(row.reason)
    if draw:
        return f"draw pool {draw.group(1)}"
    if row.reason == "skin_purchase" and isinstance(row.details, dict) and row.details.get("skin"):
        return f"skin {row.details['skin']}"
    return None


def _view(row: CurrencyTransaction, account_id: str | None, nickname: str | None, refunded: bool) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "account_id": account_id,
        "player_id": row.player_id,
        "nickname": nickname,
        "currency": row.currency_code,
        "amount": row.amount,
        "balance_after": row.balance_after,
        "reason": row.reason,
        "kind": kind_of(row.reason),
        "item": item_of(row),
        "note": row.note,
        "refunded": refunded,
    }


def _range(first: date | None, last: date | None, days: int) -> tuple[datetime, datetime, date, date]:
    today = datetime.now(timezone.utc).date()
    last = last or today
    first = first or last - timedelta(days=days - 1)
    if last < first:
        raise AppError(422, "end must not be before start")
    if (last - first).days >= 366:
        raise AppError(422, "The range is limited to 366 days")
    return (
        datetime.combine(first, time.min, tzinfo=timezone.utc),
        datetime.combine(last + timedelta(days=1), time.min, tzinfo=timezone.utc),
        first,
        last,
    )


class StoreService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.operators = OperatorService(session)

    async def _refunded_ids(self) -> set[str]:
        reasons = await self.session.scalars(select(CurrencyTransaction.reason).where(CurrencyTransaction.reason.like("refund:%")))
        return {reason.split(":", 1)[1] for reason in reasons}

    async def ledger(
        self,
        actor: OperatorActor,
        *,
        first: date | None,
        last: date | None,
        currency: str | None,
        kind: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        self.operators._need(actor, "store.read")
        start, end, _first, _last = _range(first, last, 30)
        listed = (
            select(CurrencyTransaction, Player.account_id, Player.nickname)
            .join(Player, Player.id == CurrencyTransaction.player_id)
            .where(CurrencyTransaction.created_at >= start, CurrencyTransaction.created_at < end)
        )
        if currency:
            listed = listed.where(CurrencyTransaction.currency_code == currency)
        if kind == "purchase":
            listed = listed.where(or_(CurrencyTransaction.reason == "skin_purchase", CurrencyTransaction.reason.like("gateway:mall:%"), CurrencyTransaction.reason.like("gateway:buy%")))
        elif kind == "draw":
            listed = listed.where(CurrencyTransaction.reason.like("gateway:draw:%"))
        elif kind == "topup":
            listed = listed.where(CurrencyTransaction.reason.like("topup:%"))
        elif kind == "refund":
            listed = listed.where(CurrencyTransaction.reason.like("refund:%"))
        elif kind == "admin":
            listed = listed.where(CurrencyTransaction.reason == "admin_adjust")
        elif kind == "grant":
            listed = listed.where(
                ~CurrencyTransaction.reason.like("gateway:mall:%"),
                ~CurrencyTransaction.reason.like("gateway:draw:%"),
                ~CurrencyTransaction.reason.like("gateway:buy%"),
                ~CurrencyTransaction.reason.like("topup:%"),
                ~CurrencyTransaction.reason.like("refund:%"),
                CurrencyTransaction.reason.not_in(("skin_purchase", "admin_adjust")),
            )
        if query and query.strip():
            needle = query.strip()
            pattern = f"%{needle.casefold()}%"
            listed = listed.where(
                or_(
                    func.lower(Player.nickname).like(pattern),
                    Player.account_id == needle,
                    CurrencyTransaction.id == needle,
                    func.lower(CurrencyTransaction.reason).like(pattern),
                    func.lower(func.coalesce(CurrencyTransaction.note, "")).like(pattern),
                )
            )
        total = int(await self.session.scalar(select(func.count()).select_from(listed.subquery())) or 0)
        rows = (await self.session.execute(listed.order_by(CurrencyTransaction.created_at.desc()).limit(limit).offset(offset))).all()
        refunded = await self._refunded_ids()
        return [_view(row, account_id, nickname, row.id in refunded) for row, account_id, nickname in rows], total

    async def summary(self, actor: OperatorActor, *, first: date | None, last: date | None, days: int) -> dict:
        self.operators._need(actor, "store.read")
        start, end, first_day, last_day = _range(first, last, days)
        rows = (
            await self.session.execute(
                select(CurrencyTransaction, Player.account_id, Player.nickname)
                .join(Player, Player.id == CurrencyTransaction.player_id)
                .where(CurrencyTransaction.created_at >= start, CurrencyTransaction.created_at < end)
            )
        ).all()
        dates = [(first_day + timedelta(days=offset)).isoformat() for offset in range((last_day - first_day).days + 1)]
        daily: dict[str, Counter] = {day: Counter() for day in dates}
        spent: Counter[str] = Counter()
        credited: Counter[str] = Counter()
        by_kind: Counter[str] = Counter()
        items: dict[str, Counter] = defaultdict(Counter)
        spenders: dict[str, dict] = {}
        buyers: set[str] = set()
        purchases = 0
        for row, account_id, nickname in rows:
            kind = kind_of(row.reason)
            created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
            day = created.date().isoformat()
            if kind in {"purchase", "draw"} and row.amount < 0:
                cost = -row.amount
                spent[row.currency_code] += cost
                by_kind[kind] += 1
                purchases += 1
                buyers.add(row.player_id)
                if day in daily:
                    daily[day][row.currency_code] += cost
                label = item_of(row) or row.reason
                items[label]["count"] += 1
                items[label][row.currency_code] += cost
                entry = spenders.setdefault(row.player_id, {"account_id": account_id, "nickname": nickname, "purchases": 0, "spent": Counter()})
                entry["purchases"] += 1
                entry["spent"][row.currency_code] += cost
            elif kind in {"topup", "refund"} and row.amount > 0:
                credited[f"{kind}:{row.currency_code}"] += row.amount
                by_kind[kind] += 1
        top_items = sorted(items.items(), key=lambda pair: (-pair[1]["count"], pair[0]))[:10]
        top_spenders = sorted(spenders.values(), key=lambda entry: (-entry["purchases"], -(sum(entry["spent"].values()))))[:10]
        currencies = sorted({row.currency_code for row, _account, _nick in rows} | set(spent))
        return {
            "start": first_day.isoformat(),
            "end": last_day.isoformat(),
            "currencies": currencies,
            "spent": dict(spent),
            "credited": dict(credited),
            "purchases": purchases,
            "buyers": len(buyers),
            "by_kind": dict(by_kind),
            "daily": [{"date": day, **{code: daily[day].get(code, 0) for code in currencies}} for day in dates],
            "top_items": [{"item": label, "count": counts["count"], "spent": {code: value for code, value in counts.items() if code != "count"}} for label, counts in top_items],
            "top_spenders": [{**entry, "spent": dict(entry["spent"])} for entry in top_spenders],
        }

    async def catalog(self, actor: OperatorActor) -> list[dict]:
        self.operators._need(actor, "store.read")
        sold: Counter[str] = Counter()
        details = await self.session.scalars(select(CurrencyTransaction.details).where(CurrencyTransaction.reason == "skin_purchase"))
        for detail in details:
            if isinstance(detail, dict) and detail.get("skin"):
                sold[detail["skin"]] += 1
        return [{"code": skin.code, "name": skin.name, "currency": skin.currency, "price": skin.price, "sold": sold.get(skin.code, 0)} for skin in SKINS]

    async def _player(self, account_id: str) -> Player:
        player = await self.session.scalar(select(Player).where(Player.account_id == account_id))
        if player is None or await self.session.get(Account, account_id) is None:
            raise AppError(404, "Player account was not found")
        return player

    async def _credit(self, player_id: str, currency: str, amount: int, reason: str, note: str, details: dict) -> CurrencyTransaction:
        wallet = await self.session.scalar(select(PlayerCurrency).where(PlayerCurrency.player_id == player_id, PlayerCurrency.currency_code == currency))
        if wallet is None:
            wallet = PlayerCurrency(player_id=player_id, currency_code=currency, balance=0)
            self.session.add(wallet)
            await self.session.flush()
        wallet.balance += amount
        row = CurrencyTransaction(player_id=player_id, currency_code=currency, amount=amount, balance_after=wallet.balance, reason=reason[:64], note=note, details=details)
        self.session.add(row)
        await self.session.flush()
        return row

    async def topup(self, actor: OperatorActor, account_id: str, currency: str, amount: int, reference: str, reason: str) -> dict:
        """Credit currency against an order reference. A reference is used once per currency."""
        self.operators._need(actor, "players.economy")
        currency = currency.strip().lower()
        reference = reference.strip()
        if not CODE.fullmatch(currency):
            raise AppError(422, "Currency code must be 1-16 lowercase letters, digits or underscores")
        if amount <= 0:
            raise AppError(422, "A top-up must be a positive amount")
        if not reference or len(reference) > 40:
            raise AppError(422, "An order reference of 1-40 characters is required")
        player = await self._player(account_id)
        key = f"topup:{reference}"
        exists = await self.session.scalar(
            select(CurrencyTransaction.id).where(CurrencyTransaction.reason == key[:64], CurrencyTransaction.currency_code == currency)
        )
        if exists:
            raise AppError(409, "This order reference was already credited")
        row = await self._credit(player.id, currency, amount, key, reason.strip()[:240], {"reference": reference, "operator": actor.operator.username})
        await self.operators._audit(actor, "store.topup", "player", account_id, f"{currency} +{amount} ref {reference}", reason.strip())
        await self.session.commit()
        admin_hub.player_changed(account_id, "currency", actor.operator.username)
        return _view(row, account_id, player.nickname, False)

    async def refund(self, actor: OperatorActor, transaction_id: str, reason: str) -> dict:
        """Credit back the currency of one purchase or draw. Items already granted are not taken back."""
        self.operators._need(actor, "players.economy")
        original = await self.session.get(CurrencyTransaction, transaction_id)
        if original is None:
            raise AppError(404, "Transaction was not found")
        if kind_of(original.reason) not in {"purchase", "draw"} or original.amount >= 0:
            raise AppError(422, "Only a purchase or draw that spent currency can be refunded")
        if transaction_id in await self._refunded_ids():
            raise AppError(409, "This transaction was already refunded")
        player = await self.session.get(Player, original.player_id)
        if player is None:
            raise AppError(404, "Player was not found")
        row = await self._credit(
            original.player_id, original.currency_code, -original.amount, f"refund:{original.id}", reason.strip()[:240], {"refund_of": original.id, "operator": actor.operator.username}
        )
        await self.operators._audit(actor, "store.refund", "player", player.account_id, f"{original.currency_code} +{-original.amount} for {original.reason}", reason.strip())
        await self.session.commit()
        admin_hub.player_changed(player.account_id, "currency", actor.operator.username)
        return _view(row, player.account_id, player.nickname, False)
