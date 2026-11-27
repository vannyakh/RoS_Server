"""Per-player mail from the player support page (`/admin/players/{id}/mail`).

The mail goes into the game mailbox (gateway_mails, `GatewayMailService`), the one the original
client's UISystemMail screen reads through `/gateway/accounts/{uid}/mails`. Earlier this service
kept its own `player_mails` table, which the gateway never read, so support-page mail did not reach
players. The request and response shapes of the support-page routes are unchanged (`view`); mail
numbers are now the game mail id, numbered per player. Rows already in `player_mails` are left in
place and are no longer listed.
"""

from datetime import timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.account import Account
from app.models.gateway import GatewayIdentity, GatewayMail
from app.models.types import utc_now
from app.schemas.gateway import AdminMailSend, GatewayMailAttachment
from app.services.gateway_mail_service import GatewayMailService
from app.services.operator_service import OperatorActor, OperatorService

# The support page allows "no deadline" (0). Game mail always has one; use the longest allowed.
NO_DEADLINE_DAYS = 365


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def view(mail: GatewayMail) -> dict:
    """Same field names as the gateway's lobby_mail.json (type 0 text, 1 with props)."""
    props = [[int(a["prop_id"]), int(a["number"])] for a in mail.attachments or []]
    return {
        "id": mail.mail_id,
        "type": 1 if props or mail.gold else 0,
        "title": mail.title,
        "sender": mail.sender,
        "content": mail.content or "",
        "props": props,
        "sent_at": int(_aware(mail.sent_at).timestamp()),
        "deadline": int(_aware(mail.deadline).timestamp()) if mail.deadline else 0,
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
        identity = await self._identity(GatewayIdentity.account_id == account_id)
        if identity is None:
            raise AppError(422, "Mail applies to game-client accounts only")
        title, sender, content, reason = title.strip(), sender.strip(), content.strip(), reason.strip()
        if not title or not sender or not content or len(reason) < 3:
            raise AppError(422, "Title, sender, content and a reason are required")
        try:
            body = AdminMailSend(
                account_ids=[account_id], title=title, sender=sender, content=content,
                attachments=[GatewayMailAttachment(prop_id=int(p), number=int(n)) for p, n in props],
                deadline_days=deadline_days or NO_DEADLINE_DAYS, reason=reason,
            )
        except ValidationError as e:     # game mail limits (title 64, sender 32 chars, ...)
            raise AppError(422, f"Mail does not fit the game mailbox: {e.errors()[0]['msg']}") from e
        result = await GatewayMailService(self.session).send(actor, body)
        mail = await self.session.scalar(
            select(GatewayMail).where(GatewayMail.identity_id == identity.id,
                                      GatewayMail.mail_id == result.sent[0].mail_id)
        )
        return view(mail)

    async def for_account(self, account_id: str) -> list[dict]:
        identity = await self._identity(GatewayIdentity.account_id == account_id)
        if identity is None:
            return []
        rows = await self.session.scalars(
            select(GatewayMail).where(GatewayMail.identity_id == identity.id).order_by(GatewayMail.mail_id.desc())
        )
        return [view(row) for row in rows]

    async def inbox(self, external_uid: str) -> list[dict]:
        """Unexpired, undeleted mail for the gateway (same set as `/gateway/accounts/{uid}/mails`)."""
        identity = await self._known(external_uid)
        now = utc_now()
        rows = await self.session.scalars(
            select(GatewayMail)
            .where(GatewayMail.identity_id == identity.id, GatewayMail.deleted_at.is_(None))
            .order_by(GatewayMail.mail_id.desc())
        )
        return [view(row) for row in rows if not row.deadline or _aware(row.deadline) > now]

    async def claim(self, external_uid: str, number: int) -> dict:
        """Grant the mail's props (and gold) once; a second claim grants nothing."""
        await self._known(external_uid)
        result = await GatewayMailService(self.session).claim(external_uid, number)
        if result.replayed:
            return {"props": []}
        return {"props": [[p.prop_id, p.number] for p in result.props]}

    async def _identity(self, condition) -> GatewayIdentity | None:
        return await self.session.scalar(select(GatewayIdentity).where(condition))

    async def _known(self, external_uid: str) -> GatewayIdentity:
        identity = await self._identity(GatewayIdentity.external_uid == external_uid)
        if identity is None:
            raise AppError(404, "Gateway identity was not found")
        return identity
