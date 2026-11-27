"""Per-player mail: operators send it, the gateway lists it and claims its props once."""

from datetime import timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.account import Account
from app.models.gateway import GatewayIdentity, GatewayItem
from app.models.mail import PlayerMail
from app.models.types import utc_now
from app.networking.admin_hub import admin_hub
from app.services.operator_service import OperatorActor, OperatorService

FIRST_NUMBER = 1_000_000


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def view(mail: PlayerMail) -> dict:
    """Same field names as the gateway's lobby_mail.json (type 0 text, 1 with props)."""
    expires = _aware(mail.expires_at)
    return {
        "id": mail.number,
        "type": 1 if mail.props else 0,
        "title": mail.title,
        "sender": mail.sender,
        "content": mail.content,
        "props": mail.props,
        "sent_at": int(_aware(mail.created_at).timestamp()),
        "deadline": int(expires.timestamp()) if expires else 0,
        "claimed": mail.claimed_at is not None,
    }


class MailService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.operators = OperatorService(session)

    async def send(self, actor: OperatorActor, account_id: str, title: str, sender: str, content: str,
                   props: list[list[int]], deadline_days: int, reason: str) -> dict:
        self.operators._need(actor, "players.economy")
        if await self.session.get(Account, account_id) is None:
            raise AppError(404, "Player account was not found")
        if await self._identity(GatewayIdentity.account_id == account_id) is None:
            raise AppError(422, "Mail applies to game-client accounts only")
        title, sender, content, reason = title.strip(), sender.strip(), content.strip(), reason.strip()
        if not title or not sender or not content or len(reason) < 3:
            raise AppError(422, "Title, sender, content and a reason are required")
        highest = await self.session.scalar(select(func.max(PlayerMail.number)))
        mail = PlayerMail(
            account_id=account_id,
            number=max(highest or 0, FIRST_NUMBER - 1) + 1,
            title=title,
            sender=sender,
            content=content,
            props=props,
            expires_at=utc_now() + timedelta(days=deadline_days) if deadline_days else None,
            operator_id=actor.operator.id,
        )
        self.session.add(mail)
        await self.operators._audit(actor, "player.mail", "player", account_id, f"mail {mail.number} {title}", reason)
        await self.session.commit()
        admin_hub.player_changed(account_id, "mail", actor.operator.username)
        return view(mail)

    async def for_account(self, account_id: str) -> list[dict]:
        rows = await self.session.scalars(
            select(PlayerMail).where(PlayerMail.account_id == account_id).order_by(PlayerMail.number.desc())
        )
        return [view(row) for row in rows]

    async def inbox(self, external_uid: str) -> list[dict]:
        """Unexpired mail for the gateway."""
        identity = await self._known(external_uid)
        now = int(utc_now().timestamp())
        return [mail for mail in await self.for_account(identity.account_id) if not mail["deadline"] or mail["deadline"] > now]

    async def claim(self, external_uid: str, number: int) -> dict:
        """Grant the mail's props. A second claim grants nothing."""
        identity = await self._known(external_uid)
        mail = await self.session.scalar(
            select(PlayerMail).where(PlayerMail.number == number, PlayerMail.account_id == identity.account_id)
        )
        if mail is None or (mail.expires_at and _aware(mail.expires_at) <= utc_now()):
            raise AppError(404, "Mail was not found")
        # One conditional UPDATE decides the winner when two claims arrive together.
        taken = await self.session.execute(
            update(PlayerMail).where(PlayerMail.id == mail.id, PlayerMail.claimed_at.is_(None)).values(claimed_at=utc_now())
        )
        if not taken.rowcount:
            return {"props": []}
        for prop_id, count in mail.props:
            item = await self.session.scalar(
                select(GatewayItem).where(GatewayItem.identity_id == identity.id, GatewayItem.prop_id == prop_id)
            )
            if item is None:
                self.session.add(GatewayItem(identity_id=identity.id, prop_id=prop_id, number=count))
                await self.session.flush()
            else:
                item.number += count
        await self.session.commit()
        return {"props": mail.props}

    async def _identity(self, condition) -> GatewayIdentity | None:
        return await self.session.scalar(select(GatewayIdentity).where(condition))

    async def _known(self, external_uid: str) -> GatewayIdentity:
        identity = await self._identity(GatewayIdentity.external_uid == external_uid)
        if identity is None:
            raise AppError(404, "Gateway identity was not found")
        return identity
