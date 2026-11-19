"""Player support records. Live match and lobby commands stay with the runtime."""

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.account import Account
from app.models.game_data import ItemDefinition
from app.models.gateway import GatewayIdentity, GatewayItem
from app.models.inventory import InventoryItem, PlayerCurrency, PlayerInventory
from app.models.lobby import Lobby, LobbyMember
from app.models.match import Match, MatchParticipant
from app.models.operator import AuditLog, Operator
from app.models.player import Player, PlayerStatistics
from app.models.support import ModerationAction, PlayerReport, SupportCase, SupportNote
from app.services.operator_service import OperatorActor, OperatorService

CASE_STATUSES = {"open", "in_progress", "waiting", "escalated", "resolved", "closed"}
PRIORITIES = {"low", "normal", "high", "urgent"}
CATEGORIES = {"account_access", "login", "progress", "purchase", "matchmaking", "gameplay", "bug", "other"}
REPORT_STATUSES = {"open", "reviewing", "dismissed", "confirmed", "closed"}
ACCOUNT_ACTIONS = {
    "suspend": ("players.manage", "suspended"),
    "reactivate": ("players.manage", "active"),
    "ban": ("players.ban", "closed"),
    "unban": ("players.ban", "active"),
    "note": ("players.notes", None),
}


class SupportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.operators = OperatorService(session)

    async def dashboard(self, actor: OperatorActor) -> dict:
        self.operators._need(actor, "dashboard.read")
        return {
            "registered_players": await self._count(select(func.count()).select_from(Player)),
            "suspended_accounts": await self._count(select(func.count()).select_from(Account).where(Account.status == "suspended")),
            "closed_accounts": await self._count(select(func.count()).select_from(Account).where(Account.status == "closed")),
            "open_lobbies": await self._count(select(func.count()).select_from(Lobby).where(Lobby.status.in_(("open", "starting")))),
            "stored_matches": await self._count(select(func.count()).select_from(Match)),
            "open_cases": await self._count(
                select(func.count()).select_from(SupportCase).where(SupportCase.status.in_(("open", "in_progress", "waiting", "escalated")))
            ),
            "open_reports": await self._count(
                select(func.count()).select_from(PlayerReport).where(PlayerReport.status.in_(("open", "reviewing")))
            ),
            "recent_cases": await self._case_rows(limit=5) if "support.read" in actor.permissions else [],
            "recent_audit": await self.operators.audit(5) if "logs.read" in actor.permissions else [],
        }

    async def player(self, actor: OperatorActor, account_id: str) -> dict:
        self.operators._need(actor, "players.read")
        account, profile = await self._account(account_id)
        statistics = await self.session.scalar(select(PlayerStatistics).where(PlayerStatistics.player_id == profile.id))
        inventory = (
            await self.session.execute(
                select(InventoryItem, ItemDefinition)
                .join(PlayerInventory, InventoryItem.inventory_id == PlayerInventory.id)
                .join(ItemDefinition, ItemDefinition.id == InventoryItem.item_definition_id)
                .where(PlayerInventory.player_id == profile.id)
            )
        ).all()
        currencies = list(await self.session.scalars(select(PlayerCurrency).where(PlayerCurrency.player_id == profile.id)))
        matches = (
            await self.session.execute(
                select(Match, MatchParticipant)
                .join(MatchParticipant, MatchParticipant.match_id == Match.id)
                .where(MatchParticipant.player_id == profile.id)
                .order_by(Match.created_at.desc())
                .limit(20)
            )
        ).all()
        notes = list(
            await self.session.scalars(
                select(ModerationAction)
                .where(ModerationAction.account_id == account.id, ModerationAction.action == "note")
                .order_by(ModerationAction.created_at.desc())
            )
        )
        moderation = list(
            await self.session.scalars(
                select(ModerationAction)
                .where(ModerationAction.account_id == account.id, ModerationAction.action != "note")
                .order_by(ModerationAction.created_at.desc())
            )
        )
        cases = list(
            await self.session.scalars(
                select(SupportCase).where(SupportCase.account_id == account.id).order_by(SupportCase.created_at.desc()).limit(20)
            )
        )
        reports = list(
            await self.session.scalars(
                select(PlayerReport)
                .where(PlayerReport.reported_account_id == account.id)
                .order_by(PlayerReport.created_at.desc())
                .limit(20)
            )
        )
        gateway = await self.session.scalar(select(GatewayIdentity).where(GatewayIdentity.account_id == account.id))
        gateway_items = (
            await self.session.scalar(
                select(func.count()).select_from(GatewayItem).where(GatewayItem.identity_id == gateway.id)
            )
            if gateway is not None
            else 0
        )
        audit = list(
            await self.session.scalars(
                select(AuditLog)
                .where(AuditLog.target_type == "player", AuditLog.target_id == account.id)
                .order_by(AuditLog.created_at.desc())
                .limit(20)
            )
        )
        return {
            "id": account.id,
            "username": account.username,
            "email": account.email,
            "status": account.status,
            "is_verified": account.is_verified,
            "created_at": account.created_at,
            "last_login_at": account.last_login_at,
            "player_id": profile.id,
            "nickname": profile.nickname,
            "level": profile.level,
            "experience": profile.experience,
            "statistics": None
            if statistics is None
            else {
                "total_matches": statistics.total_matches,
                "total_wins": statistics.total_wins,
                "total_kills": statistics.total_kills,
                "total_deaths": statistics.total_deaths,
                "total_playtime_seconds": statistics.total_playtime_seconds,
            },
            "inventory": [
                {"item_definition_id": item.item_definition_id, "name": definition.name, "quantity": item.quantity}
                for item, definition in inventory
            ],
            "currencies": [{"currency_code": row.currency_code, "balance": row.balance} for row in currencies],
            "matches": [
                {
                    "match_id": match.id,
                    "match_code": match.match_code,
                    "status": match.status,
                    "placement": participant.placement,
                    "kills": participant.kills,
                    "deaths": participant.deaths,
                    "started_at": match.started_at,
                    "ended_at": match.ended_at,
                }
                for match, participant in matches
            ],
            "notes": [await self._moderation_row(row) for row in notes],
            "moderation": [await self._moderation_row(row) for row in moderation],
            "cases": [
                {"id": row.id, "subject": row.subject, "status": row.status, "priority": row.priority, "created_at": row.created_at}
                for row in cases
            ],
            "reports": [
                {"id": row.id, "category": row.category, "status": row.status, "created_at": row.created_at} for row in reports
            ],
            "audit": [await self._audit_row(row) for row in audit],
            "gateway": None
            if gateway is None
            else {
                "external_uid": gateway.external_uid,
                "char_type": gateway.char_type,
                "last_login_at": gateway.last_login_at,
                "last_ip": gateway.last_ip,
                "portrait": gateway.portrait or "",
                "items": gateway_items,
                "outfit": gateway.outfit or {"body": [], "wear": []},
            },
        }

    async def update_profile(
        self, actor: OperatorActor, account_id: str, nickname: str | None, char_type: int | None, reason: str
    ) -> dict:
        self.operators._need(actor, "players.manage")
        cleaned_reason = reason.strip()
        if len(cleaned_reason) < 3:
            raise AppError(422, "A reason is required")
        account, profile = await self._account(account_id)
        gateway = await self.session.scalar(select(GatewayIdentity).where(GatewayIdentity.account_id == account.id))
        changes: list[str] = []
        if nickname is not None:
            cleaned = nickname.strip()
            if not cleaned:
                raise AppError(422, "Nickname is required")
            if cleaned != profile.nickname:
                taken = await self.session.scalar(
                    select(Player.id).where(Player.nickname == cleaned, Player.id != profile.id)
                )
                if taken is not None:
                    raise AppError(409, "Nickname is already taken")
                changes.append(f"nickname {profile.nickname} -> {cleaned}")
                profile.nickname = cleaned
        if char_type is not None:
            if gateway is None:
                raise AppError(422, "Character type applies to game-client accounts only")
            if char_type != gateway.char_type:
                changes.append(f"char_type {gateway.char_type} -> {char_type}")
                gateway.char_type = char_type
        if not changes:
            raise AppError(422, "Nothing to change")
        await self.operators._audit(actor, "player.profile", "player", account.id, "; ".join(changes)[:240], cleaned_reason[:240])
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(409, "Nickname is already taken") from exc
        return await self.player(actor, account_id)

    async def act(self, actor: OperatorActor, account_id: str, action: str, reason: str) -> dict:
        if action not in ACCOUNT_ACTIONS:
            raise AppError(422, "Unknown account action")
        permission, resulting = ACCOUNT_ACTIONS[action]
        self.operators._need(actor, permission)
        cleaned = reason.strip()
        if len(cleaned) < 3:
            raise AppError(422, "A reason is required")
        account, _profile = await self._account(account_id)
        if action == "suspend" and account.status != "active":
            raise AppError(409, "Only an active account can be suspended")
        if action == "reactivate" and account.status != "suspended":
            raise AppError(409, "Only a suspended account can be restored")
        if action == "ban" and account.status == "closed":
            raise AppError(409, "This account is already banned")
        if action == "unban" and account.status != "closed":
            raise AppError(409, "Only a banned account can be unbanned")
        if resulting is not None:
            account.status = resulting
        recorded = ModerationAction(
            account_id=account.id,
            operator_id=actor.operator.id,
            action=action,
            reason=cleaned[:240],
            resulting_status=account.status,
        )
        self.session.add(recorded)
        await self.operators._audit(actor, f"player.{action}", "player", account.id, account.status, cleaned)
        await self.session.commit()
        return await self._moderation_row(recorded)

    async def cases(self, actor: OperatorActor, limit: int, offset: int, query: str | None, status: str | None) -> tuple[list[dict], int]:
        self.operators._need(actor, "support.read")
        listed = select(SupportCase)
        counted = select(func.count()).select_from(SupportCase)
        if status:
            listed = listed.where(SupportCase.status == status)
            counted = counted.where(SupportCase.status == status)
        if query and query.strip():
            pattern = f"%{query.strip().casefold()}%"
            matched = or_(func.lower(SupportCase.subject).like(pattern), SupportCase.id == query.strip(), SupportCase.account_id == query.strip())
            listed = listed.where(matched)
            counted = counted.where(matched)
        rows = list(await self.session.scalars(listed.order_by(SupportCase.created_at.desc()).limit(limit).offset(offset)))
        total = int(await self.session.scalar(counted) or 0)
        return [await self._case(row, notes=False) for row in rows], total

    async def create_case(self, actor: OperatorActor, account_id: str, subject: str, description: str, category: str, priority: str) -> dict:
        self.operators._need(actor, "support.write")
        self._choice(category, CATEGORIES, "Unknown category")
        self._choice(priority, PRIORITIES, "Unknown priority")
        account, _profile = await self._account(account_id)
        created = SupportCase(
            account_id=account.id,
            subject=subject.strip(),
            description=description.strip(),
            category=category,
            priority=priority,
            status="open",
        )
        self.session.add(created)
        await self.session.flush()
        await self.operators._audit(actor, "support.create", "support_case", created.id, created.subject)
        await self.session.commit()
        return await self._case(created, notes=True)

    async def case(self, actor: OperatorActor, case_id: str) -> dict:
        self.operators._need(actor, "support.read")
        return await self._case(await self._load_case(case_id), notes=True)

    async def update_case(self, actor: OperatorActor, case_id: str, changes: dict) -> dict:
        row = await self._load_case(case_id)
        if "assignee_id" in changes and changes["assignee_id"] is not None:
            self.operators._need(actor, "support.assign")
            await self._active_operator(changes["assignee_id"])
            row.assignee_id = changes["assignee_id"]
        elif "assignee_id" in changes:
            self.operators._need(actor, "support.assign")
            row.assignee_id = None
        if any(key in changes for key in ("status", "priority", "resolution")):
            self.operators._need(actor, "support.write")
        if "status" in changes and changes["status"] is not None:
            self._choice(changes["status"], CASE_STATUSES, "Unknown status")
            if changes["status"] in {"resolved", "closed"} and not (changes.get("resolution") or row.resolution).strip():
                raise AppError(422, "A resolution is required")
            row.status = changes["status"]
        if "priority" in changes and changes["priority"] is not None:
            self._choice(changes["priority"], PRIORITIES, "Unknown priority")
            row.priority = changes["priority"]
        if "resolution" in changes and changes["resolution"] is not None:
            row.resolution = changes["resolution"].strip()[:240]
        await self.operators._audit(actor, "support.update", "support_case", row.id, row.status)
        await self.session.commit()
        return await self._case(row, notes=True)

    async def add_case_note(self, actor: OperatorActor, case_id: str, body: str, visibility: str) -> dict:
        self.operators._need(actor, "support.write")
        self._choice(visibility, {"internal", "reply"}, "Unknown note visibility")
        row = await self._load_case(case_id)
        note = SupportNote(case_id=row.id, operator_id=actor.operator.id, body=body.strip(), visibility=visibility)
        self.session.add(note)
        await self.operators._audit(actor, "support.note", "support_case", row.id, visibility)
        await self.session.commit()
        return await self._note(note)

    async def reports(self, actor: OperatorActor, limit: int, offset: int, status: str | None) -> tuple[list[dict], int]:
        self.operators._need(actor, "reports.read")
        listed = select(PlayerReport)
        counted = select(func.count()).select_from(PlayerReport)
        if status:
            listed = listed.where(PlayerReport.status == status)
            counted = counted.where(PlayerReport.status == status)
        rows = list(await self.session.scalars(listed.order_by(PlayerReport.created_at.desc()).limit(limit).offset(offset)))
        total = int(await self.session.scalar(counted) or 0)
        return [await self._report(row) for row in rows], total

    async def create_report(self, actor: OperatorActor, reported_account_id: str, category: str, description: str, reporter_account_id: str | None, match_id: str | None) -> dict:
        self.operators._need(actor, "reports.review")
        self._choice(category, CATEGORIES, "Unknown category")
        await self._account(reported_account_id)
        if reporter_account_id:
            await self._account(reporter_account_id)
        created = PlayerReport(
            reporter_account_id=reporter_account_id,
            reported_account_id=reported_account_id,
            match_id=match_id,
            category=category,
            description=description.strip(),
            status="open",
        )
        self.session.add(created)
        await self.session.flush()
        await self.operators._audit(actor, "report.create", "player_report", created.id, category)
        await self.session.commit()
        return await self._report(created)

    async def report(self, actor: OperatorActor, report_id: str) -> dict:
        self.operators._need(actor, "reports.read")
        return await self._report(await self._load_report(report_id))

    async def update_report(self, actor: OperatorActor, report_id: str, changes: dict) -> dict:
        self.operators._need(actor, "reports.review")
        row = await self._load_report(report_id)
        if "status" in changes and changes["status"] is not None:
            self._choice(changes["status"], REPORT_STATUSES, "Unknown status")
            if changes["status"] in {"dismissed", "confirmed", "closed"} and not (changes.get("resolution") or row.resolution).strip():
                raise AppError(422, "A resolution is required")
            row.status = changes["status"]
        if "assignee_id" in changes:
            if changes["assignee_id"]:
                await self._active_operator(changes["assignee_id"])
            row.assignee_id = changes["assignee_id"]
        if "resolution" in changes and changes["resolution"] is not None:
            row.resolution = changes["resolution"].strip()[:240]
        await self.operators._audit(actor, "report.update", "player_report", row.id, row.status)
        await self.session.commit()
        return await self._report(row)

    async def lobbies(self, actor: OperatorActor) -> list[dict]:
        self.operators._need(actor, "lobbies.read")
        rows = list(await self.session.scalars(select(Lobby).order_by(Lobby.created_at.desc()).limit(100)))
        return [await self._lobby(row, members=False) for row in rows]

    async def lobby(self, actor: OperatorActor, lobby_id: str) -> dict:
        self.operators._need(actor, "lobbies.read")
        row = await self.session.get(Lobby, lobby_id)
        if row is None:
            raise AppError(404, "Lobby was not found")
        return await self._lobby(row, members=True)

    async def matches(self, actor: OperatorActor) -> list[dict]:
        self.operators._need(actor, "matches.read")
        rows = list(await self.session.scalars(select(Match).order_by(Match.created_at.desc()).limit(100)))
        return [self._match(row) for row in rows]

    async def match(self, actor: OperatorActor, match_id: str) -> dict:
        self.operators._need(actor, "matches.read")
        row = await self.session.get(Match, match_id)
        if row is None:
            raise AppError(404, "Stored match was not found")
        payload = self._match(row)
        participants = (
            await self.session.execute(
                select(MatchParticipant, Player, Account)
                .join(Player, Player.id == MatchParticipant.player_id)
                .join(Account, Account.id == Player.account_id)
                .where(MatchParticipant.match_id == row.id)
            )
        ).all()
        payload["participants"] = [
            {
                "player_id": participant.player_id,
                "username": account.username,
                "placement": participant.placement,
                "kills": participant.kills,
                "deaths": participant.deaths,
            }
            for participant, _player, account in participants
        ]
        return payload

    async def _account(self, account_id: str) -> tuple[Account, Player]:
        account = await self.session.get(Account, account_id)
        profile = await self.session.scalar(select(Player).where(Player.account_id == account_id))
        if account is None or profile is None:
            raise AppError(404, "Player account was not found")
        return account, profile

    async def _load_case(self, case_id: str) -> SupportCase:
        row = await self.session.get(SupportCase, case_id)
        if row is None:
            raise AppError(404, "Support case was not found")
        return row

    async def _load_report(self, report_id: str) -> PlayerReport:
        row = await self.session.get(PlayerReport, report_id)
        if row is None:
            raise AppError(404, "Report was not found")
        return row

    async def _active_operator(self, operator_id: str) -> Operator:
        operator = await self.session.get(Operator, operator_id)
        if operator is None or operator.status != "active":
            raise AppError(422, "Assignee must be an active operator")
        return operator

    async def _count(self, statement) -> int:
        return int(await self.session.scalar(statement) or 0)

    async def _case_rows(self, limit: int) -> list[dict]:
        rows = list(await self.session.scalars(select(SupportCase).order_by(SupportCase.created_at.desc()).limit(limit)))
        return [await self._case(row, notes=False) for row in rows]

    async def _case(self, row: SupportCase, *, notes: bool) -> dict:
        assignee = await self.session.get(Operator, row.assignee_id) if row.assignee_id else None
        payload = {
            "id": row.id,
            "account_id": row.account_id,
            "subject": row.subject,
            "description": row.description,
            "category": row.category,
            "priority": row.priority,
            "status": row.status,
            "assignee_id": row.assignee_id,
            "assignee_username": assignee.username if assignee else None,
            "resolution": row.resolution,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        if notes:
            stored = list(
                await self.session.scalars(select(SupportNote).where(SupportNote.case_id == row.id).order_by(SupportNote.created_at))
            )
            payload["notes"] = [await self._note(note) for note in stored]
        return payload

    async def _note(self, note: SupportNote) -> dict:
        operator = await self.session.get(Operator, note.operator_id) if note.operator_id else None
        return {
            "id": note.id,
            "body": note.body,
            "visibility": note.visibility,
            "username": operator.username if operator else None,
            "created_at": note.created_at,
        }

    async def _report(self, row: PlayerReport) -> dict:
        assignee = await self.session.get(Operator, row.assignee_id) if row.assignee_id else None
        reporter = await self.session.get(Account, row.reporter_account_id) if row.reporter_account_id else None
        reported = await self.session.get(Account, row.reported_account_id)
        return {
            "id": row.id,
            "reporter_account_id": row.reporter_account_id,
            "reporter_username": reporter.username if reporter else None,
            "reported_account_id": row.reported_account_id,
            "reported_username": reported.username if reported else None,
            "match_id": row.match_id,
            "category": row.category,
            "description": row.description,
            "status": row.status,
            "assignee_id": row.assignee_id,
            "assignee_username": assignee.username if assignee else None,
            "resolution": row.resolution,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    async def _moderation_row(self, row: ModerationAction) -> dict:
        operator = await self.session.get(Operator, row.operator_id) if row.operator_id else None
        return {
            "id": row.id,
            "action": row.action,
            "reason": row.reason,
            "resulting_status": row.resulting_status,
            "username": operator.username if operator else None,
            "created_at": row.created_at,
        }

    async def _audit_row(self, row: AuditLog) -> dict:
        operator = await self.session.get(Operator, row.operator_id) if row.operator_id else None
        return {
            "id": row.id,
            "action": row.action,
            "detail": row.detail,
            "reason": row.reason,
            "username": operator.username if operator else None,
            "created_at": row.created_at,
        }

    async def _lobby(self, row: Lobby, *, members: bool) -> dict:
        payload = {
            "id": row.id,
            "code": row.code,
            "status": row.status,
            "max_players": row.max_players,
            "current_players": row.current_players,
            "created_at": row.created_at,
            "closed_at": row.closed_at,
        }
        if members:
            rows = (
                await self.session.execute(
                    select(LobbyMember, Account)
                    .join(Player, Player.id == LobbyMember.player_id)
                    .join(Account, Account.id == Player.account_id)
                    .where(LobbyMember.lobby_id == row.id)
                )
            ).all()
            payload["members"] = [
                {"player_id": member.player_id, "username": account.username, "ready": member.ready, "joined_at": member.joined_at}
                for member, account in rows
            ]
        return payload

    def _match(self, row: Match) -> dict:
        return {
            "id": row.id,
            "match_code": row.match_code,
            "status": row.status,
            "max_players": row.max_players,
            "current_players": row.current_players,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "created_at": row.created_at,
        }

    def _choice(self, value: str, allowed: set[str], message: str) -> None:
        if value not in allowed:
            raise AppError(422, message)
