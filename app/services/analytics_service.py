"""Dashboard analytics from stored rows: sign-ups, logins, matches, support load, players.

Everything is counted in UTC days from rows already in the database; nothing is sampled or
estimated. The window is 1-366 UTC days, given as a start and end date (both inclusive) or as
the last N days, so the row scan stays bounded.
"""

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.geoip import is_public
from app.models.account import Account, LoginHistory
from app.models.gateway import GatewayIdentity
from app.models.match import Match
from app.models.player import Player, PlayerStatistics
from app.models.support import PlayerReport, SupportCase
from app.networking.admin_hub import admin_hub
from app.services.operator_service import OperatorActor, OperatorService
from app.services.session_view import latest_sessions

LEVEL_BUCKETS = ((1, 4), (5, 9), (10, 19), (20, 29), (30, 49), (50, 1000))


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(
        self, actor: OperatorActor, days: int | None = 14, first: date | None = None, last: date | None = None
    ) -> dict:
        OperatorService(self.session)._need(actor, "dashboard.read")
        now = datetime.now(timezone.utc)
        if first is None and last is None:
            if days is None or not 1 <= days <= 366:
                raise AppError(422, "days must be 1-366")
            last = now.date()
            first = last - timedelta(days=days - 1)
        elif first is None or last is None:
            raise AppError(422, "Give both start and end")
        if last < first:
            raise AppError(422, "end must not be before start")
        days = (last - first).days + 1
        if days > 366:
            raise AppError(422, "The range is limited to 366 days")
        start = datetime.combine(first, time.min, tzinfo=timezone.utc)
        end = datetime.combine(last + timedelta(days=1), time.min, tzinfo=timezone.utc)
        dates = [(first + timedelta(days=offset)).isoformat() for offset in range(days)]
        daily = {date: Counter() for date in dates}

        def bump(moment: datetime, field: str) -> None:
            key = _utc(moment).date().isoformat()
            if key in daily:
                daily[key][field] += 1

        game_accounts = set(await self.session.scalars(select(GatewayIdentity.account_id)))
        for account_id, created_at in (
            await self.session.execute(select(Account.id, Account.created_at).where(Account.created_at >= start, Account.created_at < end))
        ).all():
            bump(created_at, "registrations_game" if account_id in game_accounts else "registrations_web")

        active_by_day: dict[str, set[str]] = {date: set() for date in dates}
        hourly = Counter()
        countries = Counter()
        country_players: dict[str, set[str]] = {}
        private_logins = 0
        devices = Counter()
        systems = Counter()
        sources = Counter()
        logins = (
            await self.session.execute(
                select(
                    LoginHistory.account_id,
                    LoginHistory.created_at,
                    LoginHistory.login_status,
                    LoginHistory.source,
                    LoginHistory.country,
                    LoginHistory.ip_address,
                    LoginHistory.device_model,
                    LoginHistory.os_name,
                ).where(LoginHistory.created_at >= start, LoginHistory.created_at < end)
            )
        ).all()
        for account_id, created_at, status, source, country, ip, model, os_name in logins:
            moment = _utc(created_at)
            if status != "success":
                bump(moment, "failed_logins")
                continue
            bump(moment, "logins")
            day = moment.date().isoformat()
            if account_id and day in active_by_day:
                active_by_day[day].add(account_id)
            hourly[(moment.weekday(), moment.hour)] += 1
            sources[source or "unknown"] += 1
            if country:
                countries[country] += 1
                if account_id:
                    country_players.setdefault(country, set()).add(account_id)
            elif ip and not is_public(ip):
                private_logins += 1
            devices[model or ("Web browser" if source == "web" else "Not reported")] += 1
            if os_name:
                systems[os_name] += 1

        for (created_at,) in (await self.session.execute(select(Match.created_at).where(Match.created_at >= start, Match.created_at < end))).all():
            bump(created_at, "matches")
        for (created_at,) in (
            await self.session.execute(select(SupportCase.created_at).where(SupportCase.created_at >= start, SupportCase.created_at < end))
        ).all():
            bump(created_at, "cases")
        for (created_at,) in (
            await self.session.execute(select(PlayerReport.created_at).where(PlayerReport.created_at >= start, PlayerReport.created_at < end))
        ).all():
            bump(created_at, "reports")

        statuses = dict((await self.session.execute(select(Account.status, func.count()).group_by(Account.status))).all())
        levels = [level for (level,) in (await self.session.execute(select(Player.level))).all()]
        totals = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(PlayerStatistics.total_matches), 0),
                    func.coalesce(func.sum(PlayerStatistics.total_wins), 0),
                    func.coalesce(func.sum(PlayerStatistics.total_kills), 0),
                    func.coalesce(func.sum(PlayerStatistics.total_deaths), 0),
                    func.coalesce(func.sum(PlayerStatistics.total_playtime_seconds), 0),
                )
            )
        ).one()
        top = (
            await self.session.execute(
                select(Account.id, Player.nickname, PlayerStatistics.total_kills, PlayerStatistics.total_wins, PlayerStatistics.total_matches)
                .join(Player, Player.id == PlayerStatistics.player_id)
                .join(Account, Account.id == Player.account_id)
                .where(PlayerStatistics.total_matches > 0)
                .order_by(PlayerStatistics.total_kills.desc(), PlayerStatistics.total_wins.desc())
                .limit(5)
            )
        ).all()

        # Online now, placed by each online account's newest login country.
        online_ids = admin_hub.online_ids()
        online_by_country = Counter(
            row["country"] for row in (await latest_sessions(self.session, online_ids)).values() if row.get("country")
        )
        activity_codes = set(countries) | set(online_by_country)

        fields = ("registrations_web", "registrations_game", "logins", "failed_logins", "matches", "cases", "reports")
        return {
            "days": days,
            "since": start,
            "start": first.isoformat(),
            "end": last.isoformat(),
            "generated_at": now,
            "daily": [
                {"date": date, **{field: daily[date][field] for field in fields}, "active_players": len(active_by_day[date])}
                for date in dates
            ],
            "hourly_logins": [[weekday, hour, count] for (weekday, hour), count in sorted(hourly.items())],
            "countries": [{"code": code, "count": count} for code, count in countries.most_common(10)],
            "country_activity": sorted(
                (
                    {
                        "code": code,
                        "logins": countries.get(code, 0),
                        "players": len(country_players.get(code, ())),
                        "online": online_by_country.get(code, 0),
                    }
                    for code in activity_codes
                ),
                key=lambda row: (-row["players"], -row["logins"], row["code"]),
            ),
            "online_now": admin_hub.online_players,
            "private_logins": private_logins,
            "devices": [{"name": name, "count": count} for name, count in devices.most_common(8)],
            "systems": [{"name": name, "count": count} for name, count in systems.most_common(6)],
            "sources": dict(sources),
            "statuses": {key: int(statuses.get(key, 0)) for key in ("active", "suspended", "closed")},
            "levels": [
                {"label": f"{low}+" if high >= 1000 else f"{low}-{high}", "count": sum(low <= level <= high for level in levels)}
                for low, high in LEVEL_BUCKETS
            ],
            "totals": dict(zip(("matches", "wins", "kills", "deaths", "playtime_seconds"), (int(value) for value in totals))),
            "top_players": [
                {"account_id": account_id, "nickname": nickname, "kills": kills, "wins": wins, "matches": matches}
                for account_id, nickname, kills, wins, matches in top
            ],
        }
