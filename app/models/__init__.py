"""Import every model once so Alembic and create_all see a single metadata graph."""

from app.models.account import Account, AccountDevice, AccountSession, LoginHistory
from app.models.configuration import FeatureConfiguration, GameConfiguration, ServerConfiguration
from app.models.game_data import (
    AchievementDefinition,
    EquipmentDefinition,
    GameMode,
    ItemDefinition,
    MapDefinition,
    RankDefinition,
    VehicleDefinition,
    WeaponDefinition,
)
from app.models.inventory import CurrencyTransaction, InventoryItem, PlayerCurrency, PlayerInventory
from app.models.lobby import Lobby, LobbyMember, Team, TeamMember
from app.models.match import Match, MatchParticipant, MatchResult, MatchStatistics
from app.models.player import Player, PlayerProgression, PlayerStatistics

__all__ = [
    "Account",
    "AccountDevice",
    "AccountSession",
    "AchievementDefinition",
    "CurrencyTransaction",
    "EquipmentDefinition",
    "FeatureConfiguration",
    "GameConfiguration",
    "GameMode",
    "InventoryItem",
    "ItemDefinition",
    "Lobby",
    "LobbyMember",
    "LoginHistory",
    "MapDefinition",
    "Match",
    "MatchParticipant",
    "MatchResult",
    "MatchStatistics",
    "Player",
    "PlayerCurrency",
    "PlayerInventory",
    "PlayerProgression",
    "PlayerStatistics",
    "RankDefinition",
    "ServerConfiguration",
    "Team",
    "TeamMember",
    "VehicleDefinition",
    "WeaponDefinition",
]
