"""Staff accounts, roles, and the audit rows those actions write."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import tail_server_log
from app.core.security import create_access_token, decode_access_token, hash_password, hash_token, token_expires_in, verify_password
from app.models.account import Account
from app.models.operator import AuditLog, Operator, OperatorRole, OperatorSession, Permission, Role, RolePermission
from app.models.gateway import GatewayIdentity
from app.models.player import Player
from app.schemas.auth import TokenResponse
from app.services.account_service import normalize_username

CATALOG: tuple[tuple[str, str], ...] = (
    ("dashboard.read", "Read support and account counts"),
    ("players.read", "List and inspect player accounts"),
    ("players.manage", "Suspend or restore a player account"),
    ("players.ban", "Ban or unban a player account"),
    ("players.notes", "Add an internal player note"),
    ("support.read", "Read support cases"),
    ("support.write", "Create and update support cases"),
    ("support.assign", "Assign a support case"),
    ("reports.read", "Read player reports"),
    ("reports.review", "Investigate and resolve player reports"),
    ("lobbies.read", "Read stored lobbies"),
    ("matches.read", "Read stored matches"),
    ("operators.read", "List operators"),
    ("operators.create", "Create operators"),
    ("operators.manage", "Activate or deactivate operators"),
    ("roles.read", "List roles and permissions"),
    ("roles.create", "Create roles"),
    ("roles.assign", "Assign roles and permissions"),
    ("logs.read", "Read audit and server logs"),
)
ROLE_TEMPLATES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "game_admin": (
        "Game administrator",
        "Players, cases, reports, lobbies, and stored matches.",
        (
            "dashboard.read",
            "players.read",
            "players.manage",
            "players.ban",
            "players.notes",
            "support.read",
            "support.write",
            "reports.read",
            "reports.review",
            "lobbies.read",
            "matches.read",
            "logs.read",
        ),
    ),
    "support_manager": (
        "Support manager",
        "Assign cases and review reports.",
        (
            "dashboard.read",
            "players.read",
            "players.notes",
            "support.read",
            "support.write",
            "support.assign",
            "reports.read",
            "reports.review",
            "matches.read",
        ),
    ),
    "support_agent": (
        "Support agent",
        "Inspect players and update assigned cases.",
        ("dashboard.read", "players.read", "players.notes", "support.read", "support.write", "reports.read"),
    ),
    "moderator": (
        "Moderator",
        "Review reports and apply permitted account actions.",
        (
            "dashboard.read",
            "players.read",
            "players.manage",
            "players.ban",
            "reports.read",
            "reports.review",
            "matches.read",
        ),
    ),
    "observer": (
        "Read-only operator",
        "View operations without changing them.",
        (
            "dashboard.read",
            "players.read",
            "support.read",
            "reports.read",
            "lobbies.read",
            "matches.read",
            "logs.read",
        ),
    ),
}
SUPPORT_ROLE = "support"


@dataclass
class OperatorActor:
    operator: Operator
    permissions: set[str]
    role_codes: list[str]


class OperatorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_catalog(self) -> None:
        for code, description in CATALOG:
            found = await self.session.scalar(select(Permission).where(Permission.code == code))
            if found is None:
                self.session.add(Permission(code=code, description=description))
        await self.session.flush()
        role = await self.session.scalar(select(Role).where(Role.code == SUPPORT_ROLE))
        if role is None:
            role = Role(
                code=SUPPORT_ROLE,
                name="Support",
                description="Creates roles and assigns the permissions this operator holds.",
                is_system=True,
            )
            self.session.add(role)
            await self.session.flush()
        permissions = list(await self.session.scalars(select(Permission)))
        linked = set(
            await self.session.scalars(select(RolePermission.permission_id).where(RolePermission.role_id == role.id))
        )
        for permission in permissions:
            if permission.id not in linked:
                self.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        by_code = {item.code: item for item in permissions}
        for code, (name, description, grants) in ROLE_TEMPLATES.items():
            template = await self.session.scalar(select(Role).where(Role.code == code))
            if template is None:
                template = Role(code=code, name=name, description=description, is_system=False)
                self.session.add(template)
                await self.session.flush()
            already = set(
                await self.session.scalars(
                    select(RolePermission.permission_id).where(RolePermission.role_id == template.id)
                )
            )
            if already:
                continue
            for grant in grants:
                self.session.add(RolePermission(role_id=template.id, permission_id=by_code[grant].id))
        await self.session.commit()

    async def ensure_bootstrap(self) -> None:
        username = settings.admin_username.strip()
        password = settings.admin_password
        if not username or not password:
            return
        normalized = normalize_username(username)
        existing = await self.session.scalar(select(Operator).where(Operator.username == normalized))
        if existing is None:
            await self.create_operator(username, password, [SUPPORT_ROLE], audit=False)
            return
        roles = await self._roles_for_assignment(None, [SUPPORT_ROLE])
        linked = set(
            await self.session.scalars(select(OperatorRole.role_id).where(OperatorRole.operator_id == existing.id))
        )
        for role in roles:
            if role.id not in linked:
                self.session.add(OperatorRole(operator_id=existing.id, role_id=role.id))
        await self.session.commit()

    async def login(self, username: str, password: str) -> TokenResponse:
        normalized = username.strip().casefold()
        operator = await self.session.scalar(select(Operator).where(Operator.username == normalized))
        if operator is None or not verify_password(password, operator.password_hash) or operator.status != "active":
            raise AppError(401, "Invalid username or password")
        token = create_access_token(operator.id, kind="operator")
        now = datetime.now(timezone.utc)
        operator.last_login_at = now
        self.session.add(
            OperatorSession(
                operator_id=operator.id,
                token_hash=hash_token(token),
                expires_at=now + timedelta(minutes=settings.jwt_expire_minutes),
            )
        )
        await self.session.commit()
        return TokenResponse(access_token=token, expires_in=token_expires_in())

    async def revoke(self, operator_id: str, token: str) -> None:
        stored = await self.session.scalar(
            select(OperatorSession).where(OperatorSession.token_hash == hash_token(token))
        )
        if stored is None or stored.operator_id != operator_id or stored.revoked_at is not None:
            raise AppError(401, "Invalid or expired token")
        stored.revoked_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def actor_for_token(self, token: str) -> OperatorActor:
        payload = decode_access_token(token)
        if payload.get("kind") != "operator":
            raise AppError(401, "Invalid or expired token")
        operator_id = payload.get("sub")
        operator = await self.session.get(Operator, operator_id) if operator_id else None
        if operator is None or operator.status != "active":
            raise AppError(401, "Operator unavailable")
        stored = await self.session.scalar(
            select(OperatorSession).where(OperatorSession.token_hash == hash_token(token))
        )
        if stored is None or stored.operator_id != operator.id or stored.revoked_at is not None:
            raise AppError(401, "Invalid or expired token")
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise AppError(401, "Invalid or expired token")
        permissions, role_codes = await self._access(operator.id)
        return OperatorActor(operator=operator, permissions=permissions, role_codes=role_codes)

    async def players(
        self,
        limit: int,
        offset: int,
        query: str | None = None,
        status: str | None = None,
        *,
        client: str | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
    ) -> tuple[list[dict], int]:
        listed = (
            select(Account, Player, GatewayIdentity.external_uid, GatewayIdentity.char_type)
            .join(Player, Player.account_id == Account.id)
            .outerjoin(GatewayIdentity, GatewayIdentity.account_id == Account.id)
        )
        counted = (
            select(func.count())
            .select_from(Player)
            .join(Account, Account.id == Player.account_id)
            .outerjoin(GatewayIdentity, GatewayIdentity.account_id == Account.id)
        )
        filters = []
        if client == "game":
            filters.append(GatewayIdentity.id.is_not(None))
        elif client == "web":
            filters.append(GatewayIdentity.id.is_(None))
        if created_from is not None:
            filters.append(Account.created_at >= datetime.combine(created_from, time.min, tzinfo=timezone.utc))
        if created_to is not None:
            filters.append(Account.created_at < datetime.combine(created_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
        if filters:
            listed = listed.where(*filters)
            counted = counted.where(*filters)
        if status:
            listed = listed.where(Account.status == status)
            counted = counted.where(Account.status == status)
        if query and query.strip():
            needle = query.strip()
            pattern = f"%{needle.casefold()}%"
            matched = or_(
                func.lower(Account.username).like(pattern),
                func.lower(Player.nickname).like(pattern),
                func.lower(func.coalesce(Account.email, "")).like(pattern),
                Account.id == needle,
                Player.id == needle,
            )
            listed = listed.where(matched)
            counted = counted.where(matched)
        rows = (await self.session.execute(listed.order_by(Account.created_at.desc()).limit(limit).offset(offset))).all()
        total = int(await self.session.scalar(counted) or 0)
        items = [
            {
                "id": account.id,
                "username": account.username,
                "nickname": player.nickname,
                "client": "game" if external_uid else "web",
                "char_type": char_type,
                "email": account.email,
                "status": account.status,
                "player_id": player.id,
                "level": player.level,
                "created_at": account.created_at,
                "last_login_at": account.last_login_at,
            }
            for account, player, external_uid, char_type in rows
        ]
        return items, total

    async def set_player_status(self, actor: OperatorActor, account_id: str, status: str) -> dict:
        self._need(actor, "players.manage")
        account = await self.session.get(Account, account_id)
        if account is None:
            raise AppError(404, "Player account was not found")
        account.status = status
        await self._audit(actor, "player.status", "player", account.id, status)
        await self.session.commit()
        return {"id": account.id, "username": account.username, "status": account.status}

    async def operators(self) -> list[dict]:
        rows = list(await self.session.scalars(select(Operator).order_by(Operator.username)))
        items = []
        for operator in rows:
            _permissions, role_codes = await self._access(operator.id)
            items.append(
                {
                    "id": operator.id,
                    "username": operator.username,
                    "status": operator.status,
                    "roles": role_codes,
                    "last_login_at": operator.last_login_at,
                }
            )
        return items

    async def create_operator(self, username: str, password: str, role_codes: list[str], *, audit: bool = True, actor: OperatorActor | None = None) -> Operator:
        if actor is not None:
            self._need(actor, "operators.create")
        normalized = normalize_username(username)
        if len(password) < 12:
            raise AppError(422, "Password must be at least 12 characters")
        if await self.session.scalar(select(Operator).where(Operator.username == normalized)):
            raise AppError(409, "Operator already exists")
        roles = await self._roles_for_assignment(actor, role_codes)
        operator = Operator(username=normalized, password_hash=hash_password(password), status="active")
        self.session.add(operator)
        await self.session.flush()
        for role in roles:
            self.session.add(OperatorRole(operator_id=operator.id, role_id=role.id))
        if audit and actor is not None:
            await self._audit(actor, "operator.create", "operator", operator.id, normalized)
        await self.session.commit()
        return operator

    async def set_operator_roles(self, actor: OperatorActor, operator_id: str, role_codes: list[str]) -> list[str]:
        self._need(actor, "roles.assign")
        operator = await self.session.get(Operator, operator_id)
        if operator is None:
            raise AppError(404, "Operator was not found")
        roles = await self._roles_for_assignment(actor, role_codes)
        await self.session.execute(delete(OperatorRole).where(OperatorRole.operator_id == operator.id))
        for role in roles:
            self.session.add(OperatorRole(operator_id=operator.id, role_id=role.id))
        await self._audit(actor, "operator.roles", "operator", operator.id, ",".join(role.code for role in roles))
        await self.session.commit()
        return [role.code for role in roles]

    async def set_operator_status(self, actor: OperatorActor, operator_id: str, status: str) -> dict:
        self._need(actor, "operators.manage")
        operator = await self.session.get(Operator, operator_id)
        if operator is None:
            raise AppError(404, "Operator was not found")
        if status == "suspended" and operator.id == actor.operator.id:
            raise AppError(403, "An operator cannot deactivate this account")
        if status == "suspended" and await self._last_support_operator(operator.id):
            raise AppError(403, "The last support operator stays active")
        operator.status = status
        await self._audit(actor, "operator.status", "operator", operator.id, status)
        await self.session.commit()
        return {"id": operator.id, "username": operator.username, "status": operator.status}

    async def _last_support_operator(self, operator_id: str) -> bool:
        support = await self.session.scalar(select(Role).where(Role.code == SUPPORT_ROLE))
        if support is None:
            return False
        linked = await self.session.scalar(
            select(OperatorRole).where(OperatorRole.operator_id == operator_id, OperatorRole.role_id == support.id)
        )
        if linked is None:
            return False
        active = list(
            await self.session.scalars(
                select(Operator.id)
                .join(OperatorRole, OperatorRole.operator_id == Operator.id)
                .where(OperatorRole.role_id == support.id, Operator.status == "active")
            )
        )
        return active == [operator_id]

    async def roles(self) -> list[dict]:
        rows = list(await self.session.scalars(select(Role).order_by(Role.code)))
        items = []
        for role in rows:
            codes = await self._permission_codes(role.id)
            items.append(
                {
                    "id": role.id,
                    "code": role.code,
                    "name": role.name,
                    "description": role.description,
                    "is_system": role.is_system,
                    "permissions": codes,
                }
            )
        return items

    async def permissions(self) -> list[dict]:
        rows = list(await self.session.scalars(select(Permission).order_by(Permission.code)))
        return [{"code": row.code, "description": row.description} for row in rows]

    async def create_role(self, actor: OperatorActor, code: str, name: str, description: str) -> Role:
        self._need(actor, "roles.create")
        normalized = normalize_username(code)
        if await self.session.scalar(select(Role).where(Role.code == normalized)):
            raise AppError(409, "Role already exists")
        role = Role(code=normalized, name=name.strip() or normalized, description=description.strip(), is_system=False)
        self.session.add(role)
        await self.session.flush()
        await self._audit(actor, "role.create", "role", role.id, role.code)
        await self.session.commit()
        return role

    async def set_role_permissions(self, actor: OperatorActor, role_id: str, codes: list[str]) -> list[str]:
        self._need(actor, "roles.assign")
        role = await self.session.get(Role, role_id)
        if role is None:
            raise AppError(404, "Role was not found")
        if role.is_system:
            raise AppError(403, "The support role keeps the full permission catalog")
        requested = sorted(set(codes))
        unknown = [code for code in requested if code not in actor.permissions]
        if unknown:
            raise AppError(403, "A role can only receive permissions this operator holds")
        permissions = (
            list(await self.session.scalars(select(Permission).where(Permission.code.in_(requested))))
            if requested
            else []
        )
        if len(permissions) != len(requested):
            raise AppError(422, "Unknown permission")
        await self.session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for permission in permissions:
            self.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        await self._audit(actor, "role.permissions", "role", role.id, ",".join(requested))
        await self.session.commit()
        return requested

    async def audit(self, limit: int) -> list[dict]:
        rows = list(
            await self.session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
        )
        items = []
        for row in rows:
            username = None
            if row.operator_id:
                operator = await self.session.get(Operator, row.operator_id)
                username = operator.username if operator else None
            items.append(
                {
                    "id": row.id,
                    "operator_id": row.operator_id,
                    "username": username,
                    "action": row.action,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "detail": row.detail,
                    "reason": row.reason,
                    "created_at": row.created_at,
                }
            )
        return items

    def server_log(self, limit: int) -> list[str]:
        return tail_server_log(limit)

    async def _access(self, operator_id: str) -> tuple[set[str], list[str]]:
        links = list(await self.session.scalars(select(OperatorRole).where(OperatorRole.operator_id == operator_id)))
        permissions: set[str] = set()
        role_codes: list[str] = []
        for link in links:
            role = await self.session.get(Role, link.role_id)
            if role is None:
                continue
            role_codes.append(role.code)
            permissions.update(await self._permission_codes(role.id))
        return permissions, sorted(role_codes)

    async def _permission_codes(self, role_id: str) -> list[str]:
        links = list(await self.session.scalars(select(RolePermission).where(RolePermission.role_id == role_id)))
        codes = []
        for link in links:
            permission = await self.session.get(Permission, link.permission_id)
            if permission is not None:
                codes.append(permission.code)
        return sorted(codes)

    async def _roles_for_assignment(self, actor: OperatorActor | None, role_codes: list[str]) -> list[Role]:
        roles: list[Role] = []
        for code in sorted(set(role_codes)):
            role = await self.session.scalar(select(Role).where(Role.code == code.strip().casefold()))
            if role is None:
                raise AppError(422, "Unknown role")
            if actor is not None:
                held = set(await self._permission_codes(role.id))
                if not held.issubset(actor.permissions):
                    raise AppError(403, "A role can only be assigned when this operator holds its permissions")
            roles.append(role)
        return roles

    async def _audit(
        self,
        actor: OperatorActor,
        action: str,
        target_type: str,
        target_id: str,
        detail: str,
        reason: str = "",
    ) -> None:
        self.session.add(
            AuditLog(
                operator_id=actor.operator.id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail=detail[:240],
                reason=reason[:240],
            )
        )

    def _need(self, actor: OperatorActor, permission: str) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "Permission denied")
