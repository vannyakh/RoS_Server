"""Profile data the original client's My Page, Stats and Credit screens read.

Battle records are kept per (season, queue, team mode). Season 0 is all-time. Each match adds to
its own team mode and to "overall", for both the match's season and season 0, so the client can
read any of its record types without the server adding rows up on every request.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.gateway import GatewayBattleRecord, GatewayCreditRecord, GatewayIdentity, GatewayItem
from app.models.player import Player, PlayerStatistics
from app.schemas.gateway import (
    GatewayBattleRecordView,
    GatewayCredit,
    GatewayCreditClaim,
    GatewayCreditRecordView,
    GatewayMatchReport,
    GatewayProfile,
)
from app.services.gateway_service import GatewayService

CREDIT_HISTORY = 20       # rows sent to the client's "Score inquire" list

_SUMS = (
    ("fight_count", None), ("kill_count", "kills"), ("death_count", "deaths"), ("assist_count", "assists"),
    ("damage", "damage"), ("head_shot_count", "head_shots"), ("hit_count", "hits"), ("fire_count", "fires"),
    ("fight_time_seconds", "fight_time_seconds"), ("collect_count", "collect_count"), ("heal_count", "heal_count"),
)
_MAXES = (
    ("max_round_kill", "kills"), ("max_round_assist", "assists"), ("max_round_heal", "heal_count"),
    ("max_kill_distance_dm", "kill_distance_dm"), ("max_move_distance_dm", "move_distance_dm"),
    ("max_fight_time_seconds", "fight_time_seconds"),
)


class GatewayProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = GatewayService(session)

    async def profile(self, external_uid: str) -> GatewayProfile:
        identity, player = await self.accounts._known(external_uid)
        records = (
            await self.session.scalars(
                select(GatewayBattleRecord)
                .where(GatewayBattleRecord.identity_id == identity.id)
                .order_by(GatewayBattleRecord.season, GatewayBattleRecord.queue, GatewayBattleRecord.team_mode)
            )
        ).all()
        return GatewayProfile(
            nickname=player.nickname,
            level=player.level,
            char_type=identity.char_type,
            portrait=identity.portrait or "",
            rank_score=identity.rank_score,
            space_likes=identity.space_likes,
            current_season=settings.gateway_current_season,
            credit=await self._credit(identity),
            records=[_record_view(row) for row in records],
        )

    async def record_match(self, external_uid: str, report: GatewayMatchReport) -> GatewayProfile:
        identity, player = await self.accounts._known(external_uid)
        season = report.season or settings.gateway_current_season
        for row_season in {season, 0}:
            for team_mode in {report.team_mode, "overall"}:
                row = await self._record_row(identity.id, row_season, report.queue, team_mode)
                _add_match(row, report)
        identity.rank_score = max(0, identity.rank_score + report.rank_score_delta)
        await self._add_to_player_totals(player, report)
        await self.session.commit()
        return await self.profile(external_uid)

    async def claim_credit_reward(self, external_uid: str) -> GatewayCreditClaim:
        """Grant last week's credit reward props once, then clear them."""
        identity, _player = await self.accounts._known(external_uid)
        awards = [int(p) for p in (identity.credit_gifts or [])]
        for prop_id in awards:
            item = await self.session.scalar(
                select(GatewayItem).where(GatewayItem.identity_id == identity.id, GatewayItem.prop_id == prop_id)
            )
            if item is None:
                self.session.add(GatewayItem(identity_id=identity.id, prop_id=prop_id, number=1))
            else:
                item.number += 1
        identity.credit_gifts = []
        await self.session.commit()
        return GatewayCreditClaim(awards=awards, credit=await self._credit(identity))

    async def _credit(self, identity: GatewayIdentity) -> GatewayCredit:
        rows = (
            await self.session.scalars(
                select(GatewayCreditRecord)
                .where(GatewayCreditRecord.identity_id == identity.id)
                .order_by(GatewayCreditRecord.created_at.desc())
                .limit(CREDIT_HISTORY)
            )
        ).all()
        return GatewayCredit(
            score=identity.credit_score,
            status_last_week=identity.credit_status_last_week,
            weeks=identity.credit_weeks,
            gifts=[int(p) for p in (identity.credit_gifts or [])],
            records=[
                GatewayCreditRecordView(
                    delta=r.delta, reason=r.reason, score_after=r.score_after, note=r.note, created_at=r.created_at
                )
                for r in rows
            ],
        )

    async def _record_row(self, identity_id: str, season: int, queue: str, team_mode: str) -> GatewayBattleRecord:
        row = await self.session.scalar(
            select(GatewayBattleRecord).where(
                GatewayBattleRecord.identity_id == identity_id,
                GatewayBattleRecord.season == season,
                GatewayBattleRecord.queue == queue,
                GatewayBattleRecord.team_mode == team_mode,
            )
        )
        if row is None:
            row = GatewayBattleRecord(identity_id=identity_id, season=season, queue=queue, team_mode=team_mode)
            for column in GatewayBattleRecordView.model_fields:
                if column not in ("season", "queue", "team_mode"):
                    setattr(row, column, 0)
            self.session.add(row)
            await self.session.flush()
        return row

    async def _add_to_player_totals(self, player: Player, report: GatewayMatchReport) -> None:
        """Keep the web console's PlayerStatistics in step with original-client matches."""
        stats = await self.session.scalar(select(PlayerStatistics).where(PlayerStatistics.player_id == player.id))
        if stats is None:
            stats = PlayerStatistics(player_id=player.id)
            self.session.add(stats)
        stats.total_matches = (stats.total_matches or 0) + 1
        stats.total_wins = (stats.total_wins or 0) + (1 if report.placement == 1 else 0)
        stats.total_kills = (stats.total_kills or 0) + report.kills
        stats.total_deaths = (stats.total_deaths or 0) + report.deaths
        stats.total_playtime_seconds = (stats.total_playtime_seconds or 0) + report.fight_time_seconds


def _add_match(row: GatewayBattleRecord, report: GatewayMatchReport) -> None:
    for column, field in _SUMS:
        setattr(row, column, getattr(row, column) + (1 if field is None else getattr(report, field)))
    row.win_count += 1 if report.placement == 1 else 0
    row.top5_count += 1 if report.placement <= 5 else 0
    for column, field in _MAXES:
        setattr(row, column, max(getattr(row, column), getattr(report, field)))


def _record_view(row: GatewayBattleRecord) -> GatewayBattleRecordView:
    return GatewayBattleRecordView(**{name: getattr(row, name) for name in GatewayBattleRecordView.model_fields})
