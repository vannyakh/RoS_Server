"""Authoritative in-memory player, match, and world state."""

from dataclasses import dataclass, field
from time import monotonic


@dataclass
class PlayerState:
    player_id: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    health: float = 100.0
    connected: bool = True
    move_x: float = 0.0
    move_y: float = 0.0
    aim_x: float = 1.0
    aim_y: float = 0.0
    is_bot: bool = False
    match_id: str | None = None
    status: str = "roaming"
    queued_at: float = 0.0
    on_plane: bool = False
    drop_at: float = 0.0
    weapon: str | None = None
    mag: int = 0
    fire_cooldown: float = 0.0
    reload_left: float = 0.0
    kills: int = 0
    inventory: dict[str, int] = field(default_factory=dict)
    mags: dict[str, int] = field(default_factory=dict)
    vehicle: str | None = None
    nickname: str | None = None
    skin: str = "recruit"
    attachments: dict[str, list[str]] = field(default_factory=dict)
    supplies: int = 0
    healing: str | None = None
    heal_left: float = 0.0
    team_id: str | None = None
    bleed_left: float = 0.0
    knocked_by: str | None = None
    reviving: str | None = None
    revive_progress: float = 0.0
    armor: int = 0
    helmet: int = 0
    backpack: int = 0
    distance: float = 0.0
    damage_dealt: float = 0.0


@dataclass(frozen=True)
class Blocker:
    minimum_x: float
    minimum_y: float
    maximum_x: float
    maximum_y: float
    kind: str = "cover"
    name: str = ""


@dataclass
class VehicleNode:
    vehicle_id: str
    kind: str
    x: float
    y: float
    occupant: str | None = None


@dataclass
class LootNode:
    loot_id: str
    x: float
    y: float
    item_id: str
    quantity: int
    taken: bool = False
    # Set when the node came out of an eliminated player's crate ("Heritage" in the original UI).
    crate_id: str | None = None


@dataclass
class MatchResult:
    player_id: str
    kills: int
    win: bool
    placement: int


@dataclass
class Match:
    match_id: str
    player_ids: list[str]
    phase: str = "countdown"
    clock: float = 0.0
    zone_x: float = 100.0
    zone_y: float = 100.0
    zone_radius: float = 110.0
    next_x: float = 100.0
    next_y: float = 100.0
    next_radius: float = 70.0
    zone_index: int = 0
    zone_dps: float = 1.0
    winner_id: str | None = None
    recorded: bool = False
    loot: list[LootNode] = field(default_factory=list)
    vehicles: list[VehicleNode] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    elimination_order: list[str] = field(default_factory=list)
    # Kills scored in this match; a player who re-queues keeps this match's count here.
    kills: dict[str, int] = field(default_factory=dict)
    drop_serial: int = 0
    winner_ids: list[str] = field(default_factory=list)
    mode: str = "standard"
    spawns: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class WorldState:
    players: dict[str, PlayerState] = field(default_factory=dict)
    matches: dict[str, Match] = field(default_factory=dict)
    pending_results: list[MatchResult] = field(default_factory=list)
    tick: int = 0
    time: float = 0.0
    created_at: float = field(default_factory=monotonic)
