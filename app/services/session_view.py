"""Login-history rows as the admin console shows them."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geoip import is_public
from app.models.account import LoginHistory


def session_row(row: LoginHistory) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "status": row.login_status,
        "source": row.source,
        "ip_address": row.ip_address,
        # "public", "private" (LAN, loopback, reserved) or null when no IP was recorded.
        "network": None if not row.ip_address else ("public" if is_public(row.ip_address) else "private"),
        "country": row.country,
        "device_model": row.device_model,
        "os_name": row.os_name,
        "client_version": row.client_version,
        "time_zone": row.time_zone,
        "language": row.language,
        "user_agent": row.user_agent,
    }


async def latest_sessions(session: AsyncSession, account_ids: list[str]) -> dict[str, dict]:
    """Newest successful login per account, keyed by account id."""
    if not account_ids:
        return {}
    ranked = (
        select(
            LoginHistory.id,
            func.row_number()
            .over(partition_by=LoginHistory.account_id, order_by=LoginHistory.created_at.desc())
            .label("rank"),
        )
        .where(LoginHistory.account_id.in_(account_ids), LoginHistory.login_status == "success")
        .subquery()
    )
    rows = await session.scalars(
        select(LoginHistory).join(ranked, ranked.c.id == LoginHistory.id).where(ranked.c.rank == 1)
    )
    return {row.account_id: session_row(row) for row in rows if row.account_id}
