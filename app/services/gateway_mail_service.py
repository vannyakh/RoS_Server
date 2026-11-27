"""System mail for original-client players (RO-117).

Operators send mail from the admin API; the gateway reads, claims and deletes it for the client's
UISystemMail screen. A claim adds the attachments to gateway_items and the gold to the "gold"
PlayerCurrency (client currency 1) in one transaction. The claim is guarded by a conditional
UPDATE ... WHERE claimed_at IS NULL, so two concurrent claims cannot both add.

Deleting a mail that was not claimed forfeits its attachments. A mail past its deadline is hidden
and cannot be claimed.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.gateway import MAIL_TYPE_PROPS, MAIL_TYPE_TXT, GatewayIdentity, GatewayMail
from app.models.inventory import CurrencyTransaction, PlayerCurrency
from app.models.types import utc_now
from app.networking.admin_hub import admin_hub
from app.schemas.gateway import (
    AdminMailSend,
    AdminMailSendResult,
    AdminMailSent,
    AdminMailView,
    GatewayItemView,
    GatewayMailAttachment,
    GatewayMailClaim,
    GatewayMailDetail,
    GatewayMailView,
)
from app.services.gateway_service import GOLD, GOLD_ID, GatewayService
from app.services.operator_service import OperatorActor, OperatorService

ABSTRACT_LENGTH = 40
MAIL_REASON = "gateway:mail:"


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _unix(value: datetime | None) -> int:
    value = _aware(value)
    return int(value.timestamp()) if value else 0


def _expired(mail: GatewayMail, now: datetime) -> bool:
    deadline = _aware(mail.deadline)
    return deadline is not None and deadline <= now


def _attachments(mail: GatewayMail) -> list[GatewayMailAttachment]:
    return [GatewayMailAttachment(prop_id=int(a["prop_id"]), number=int(a["number"])) for a in mail.attachments or []]


def _summed(rows: list[GatewayMailAttachment]) -> dict[int, int]:
    totals: dict[int, int] = {}
    for row in rows:
        totals[row.prop_id] = totals.get(row.prop_id, 0) + row.number
    return totals


def _view(mail: GatewayMail) -> dict:
    return {
        "mail_id": mail.mail_id,
        "type": mail.mail_type,
        "title": mail.title,
        "sender": mail.sender,
        "abstract": (mail.content or "")[:ABSTRACT_LENGTH],
        "sent_at": _unix(mail.sent_at),
        "deadline": _unix(mail.deadline),
        "unread": mail.read_at is None,
        "claimed": mail.claimed_at is not None,
        "attachments": _attachments(mail),
        "gold": mail.gold,
    }


class GatewayMailService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = GatewayService(session)
        self.operators = OperatorService(session)

    # Gateway side ---------------------------------------------------------------------------

    async def mails(self, external_uid: str) -> list[GatewayMailView]:
        identity, _player = await self.gateway._known(external_uid)
        now = utc_now()
        rows = (
            await self.session.scalars(
                select(GatewayMail)
                .where(GatewayMail.identity_id == identity.id, GatewayMail.deleted_at.is_(None))
                .order_by(GatewayMail.mail_id.desc())
            )
        ).all()
        return [GatewayMailView(**_view(mail)) for mail in rows if not _expired(mail, now)]

    async def detail(self, external_uid: str, mail_id: int) -> GatewayMailDetail:
        identity, _player = await self.gateway._known(external_uid)
        mail = await self._live(identity.id, mail_id, utc_now())
        if mail.read_at is None:
            mail.read_at = utc_now()
            await self.session.commit()
        return GatewayMailDetail(**_view(mail), content=mail.content or "")

    async def claim(self, external_uid: str, mail_id: int) -> GatewayMailClaim:
        identity, player = await self.gateway._known(external_uid)
        now = utc_now()
        mail = await self._live(identity.id, mail_id, now)
        props = _attachments(mail)
        summed = _summed(props)
        gold = await self.gateway._gold_row(player.id)

        taken = await self.session.execute(
            update(GatewayMail)
            .where(GatewayMail.id == mail.id, GatewayMail.claimed_at.is_(None), GatewayMail.deleted_at.is_(None))
            .values(claimed_at=now, read_at=func.coalesce(GatewayMail.read_at, now))
            .execution_options(synchronize_session=False)
        )
        replayed = taken.rowcount != 1
        if not replayed:
            await self.gateway._add_items(identity.id, summed)
            self.gateway._save_recent(identity, [p for p, n in summed.items() for _ in range(n)])
            if mail.gold:
                await self.session.execute(
                    update(PlayerCurrency)
                    .where(PlayerCurrency.id == gold.id)
                    .values(balance=PlayerCurrency.balance + mail.gold)
                    .execution_options(synchronize_session=False)
                )
            await self.session.flush()

        balance = await self.session.scalar(select(PlayerCurrency.balance).where(PlayerCurrency.id == gold.id))
        if not replayed and mail.gold:
            self.session.add(
                CurrencyTransaction(
                    player_id=player.id,
                    currency_code=GOLD,
                    amount=mail.gold,
                    balance_after=balance,
                    reason=f"{MAIL_REASON}{mail.mail_id}"[:64],
                    details={"mail": mail.id, "props": [p.model_dump() for p in props]},
                )
            )
        counts = await self.gateway._counts(identity.id, sorted(summed))
        await self.session.commit()
        return GatewayMailClaim(
            props=props,
            gold=mail.gold,
            items=[GatewayItemView(prop_id=p, number=counts.get(p, 0)) for p in sorted(summed)],
            currencies={str(GOLD_ID): balance},
            replayed=replayed,
        )

    async def delete(self, external_uid: str, mail_id: int) -> None:
        """Soft delete. Attachments that were not claimed are forfeited."""
        identity, _player = await self.gateway._known(external_uid)
        mail = await self._live(identity.id, mail_id, utc_now())
        mail.deleted_at = utc_now()
        await self.session.commit()

    async def _live(self, identity_id: str, mail_id: int, now: datetime) -> GatewayMail:
        mail = await self.session.scalar(
            select(GatewayMail).where(
                GatewayMail.identity_id == identity_id,
                GatewayMail.mail_id == mail_id,
                GatewayMail.deleted_at.is_(None),
            )
        )
        if mail is None or _expired(mail, now):
            raise AppError(404, "Mail was not found")
        return mail

    # Operator side --------------------------------------------------------------------------

    async def send(self, actor: OperatorActor, body: AdminMailSend) -> AdminMailSendResult:
        self.operators._need(actor, "players.economy")
        now = utc_now()
        deadline = now + timedelta(days=body.deadline_days)
        attachments = [a.model_dump() for a in body.attachments]
        mail_type = MAIL_TYPE_PROPS if attachments or body.gold else MAIL_TYPE_TXT
        reason = body.reason.strip()
        sent: list[AdminMailSent] = []
        skipped: list[str] = []
        for account_id in dict.fromkeys(a.strip() for a in body.account_ids):
            identity = await self.session.scalar(
                select(GatewayIdentity).where(GatewayIdentity.account_id == account_id)
            )
            if identity is None:
                skipped.append(account_id)
                continue
            last = await self.session.scalar(
                select(func.max(GatewayMail.mail_id)).where(GatewayMail.identity_id == identity.id)
            )
            mail = GatewayMail(
                identity_id=identity.id,
                mail_id=(last or 0) + 1,
                mail_type=mail_type,
                title=body.title,
                content=body.content,
                sender=body.sender,
                attachments=attachments,
                gold=body.gold,
                sent_at=now,
                deadline=deadline,
                sent_by=actor.operator.username,
            )
            self.session.add(mail)
            await self.session.flush()
            detail = f"mail {mail.mail_id} '{body.title}' props {len(attachments)} gold {body.gold}"
            await self.operators._audit(actor, "player.mail", "player", account_id, detail, reason)
            sent.append(AdminMailSent(account_id=account_id, mail_id=mail.mail_id))
        await self.session.commit()
        for row in sent:
            admin_hub.player_changed(row.account_id, "mail", actor.operator.username)
        return AdminMailSendResult(sent=sent, skipped=skipped)

    async def list_for_account(self, actor: OperatorActor, account_id: str) -> list[AdminMailView]:
        self.operators._need(actor, "players.read")
        identity = await self.session.scalar(select(GatewayIdentity).where(GatewayIdentity.account_id == account_id))
        if identity is None:
            return []
        now = utc_now()
        rows = (
            await self.session.scalars(
                select(GatewayMail).where(GatewayMail.identity_id == identity.id).order_by(GatewayMail.mail_id.desc())
            )
        ).all()
        return [
            AdminMailView(
                **_view(mail),
                content=mail.content or "",
                account_id=account_id,
                deleted=mail.deleted_at is not None,
                expired=_expired(mail, now),
                sent_by=mail.sent_by,
                read_at=mail.read_at,
                claimed_at=mail.claimed_at,
                deleted_at=mail.deleted_at,
            )
            for mail in rows
        ]
