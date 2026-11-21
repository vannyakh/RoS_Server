"""Match simulation. Callers hold the world lock. This module does no I/O."""

import logging
import math
import random
from uuid import uuid4

from app.game.collision import slide
from app.game.items import (
    ATTACHMENTS,
    HEAL_TIME,
    HEALS,
    LOOT_TABLE,
    PISTOLS,
    SLOT_LIMITS,
    VEHICLES,
    WEAPONS,
    damage_after_gear,
    gear_of,
    is_weapon,
    stack_limit,
    can_attach,
    slot_count,
    slot_of,
)
from app.game.rules import MatchRules
from app.game.state import Blocker, LootNode, Match, MatchResult, PlayerState, VehicleNode, WorldState

logger = logging.getLogger(__name__)


def simulate(world: WorldState, dt: float, rules: MatchRules) -> None:
    if dt < 0:
        return
    world.time += dt
    _form_matches(world, rules)
    for match in list(world.matches.values()):
        _tick_match(world, match, dt, rules)
    for player in world.players.values():
        if player.match_id is None and player.status == "roaming" and player.connected:
            _move(player, dt, rules)


def queue_player(world: WorldState, player_id: str) -> tuple[bool, str]:
    player = world.players.setdefault(player_id, PlayerState(player_id=player_id))
    if player.status == "queued":
        return True, "Already queued"
    if player.status in {"countdown", "dropping", "alive", "knocked"}:
        return False, "Already in a match"
    _clear_loadout(player)
    player.status = "queued"
    player.queued_at = world.time
    player.match_id = None
    player.health = 100.0
    player.move_x = 0.0
    player.move_y = 0.0
    player.on_plane = False
    player.kills = 0
    return True, "Queued"


def leave_queue(world: WorldState, player_id: str) -> tuple[bool, str]:
    player = world.players.get(player_id)
    if player is None or player.status != "queued":
        return False, "Not in the lobby"
    player.status = "roaming"
    return True, "Left the lobby"


def forfeit(world: WorldState, player_id: str) -> tuple[bool, str]:
    player = world.players.get(player_id)
    match = _match_for(world, player)
    if player is None or match is None or player.status not in {"countdown", "dropping", "alive", "knocked"}:
        return False, "Not in a match"
    if match.mode == "training":
        _dissolve(world, match)
        return True, "Left training"
    _eliminate(world, match, player, None, "forfeit")
    _maybe_finish(world, match)
    return True, "Left the match"


def apply_action(
    world: WorldState,
    player: PlayerState,
    action: str,
    loot_id: str | None,
    item_id: str | None,
    rules: MatchRules,
) -> tuple[bool, str]:
    match = _match_for(world, player)
    if action == "jump":
        return _jump_action(player, match)
    if match is not None and player.status == "dropping" and not player.on_plane:
        return False, "Still parachuting"
    if player.status == "knocked" and action in {"use", "reload", "shoot"} and match is not None:
        return False, "Knocked down"
    if match is None or player.status != "alive" or player.on_plane or match.phase not in {"dropping", "playing"}:
        return False, "Not in a match"
    if action == "revive":
        return _start_revive(world, match, player, rules)
    if action == "shoot":
        return _shoot(world, match, player, rules)
    if action == "reload":
        return _start_reload(player)
    if action == "pickup":
        return _pickup(world, match, player, loot_id, rules)
    if action == "use":
        return _use_item(match, player, item_id, rules)
    if action == "attach":
        return _attach(player, item_id)
    if action == "equip":
        return _equip(player, item_id)
    if action == "discard":
        return _discard(match, player, item_id)
    if action == "board":
        return _board(match, player, rules)
    if action == "exit":
        return _exit_vehicle(match, player)
    return False, "Unknown action"


def lobby_view(world: WorldState) -> dict:
    queued = [
        {"player_id": player.player_id, "waited": round(world.time - player.queued_at, 2)}
        for player in world.players.values()
        if player.status == "queued" and not player.is_bot
    ]
    status = "waiting" if queued or world.matches else "idle"
    return {"status": status, "players": queued}


def matches_view(world: WorldState) -> dict:
    return {"matches": [_summary(world, match) for match in world.matches.values()]}


def match_view(world: WorldState, match_id: str) -> dict | None:
    match = world.matches.get(match_id)
    if match is None:
        return None
    return _summary(world, match)


def snapshot(world: WorldState, player: PlayerState, rules: MatchRules) -> dict:
    payload = {
        "player_id": player.player_id,
        "nickname": player.nickname,
        "skin": player.skin,
        "tick": world.tick,
        "x": round(player.x, 3),
        "y": round(player.y, 3),
        "z": round(player.z, 3),
        "health": round(player.health, 1),
        "status": player.status,
        "match_id": player.match_id,
        "aim_x": round(player.aim_x, 3),
        "aim_y": round(player.aim_y, 3),
        "kills": player.kills,
        "map_size": rules.map_size,
        "vehicle": player.vehicle,
        "armor": player.armor,
        "helmet": player.helmet,
        "backpack": player.backpack,
    }
    match = world.matches.get(player.match_id) if player.match_id else None
    if match is not None:
        payload["match"] = _match_payload(world, match, player, rules)
    return payload


def _form_matches(world: WorldState, rules: MatchRules) -> None:
    queued = [player for player in world.players.values() if player.status == "queued" and not player.is_bot]
    if not queued:
        return
    queued.sort(key=lambda player: (player.queued_at, player.player_id))
    waited = world.time - queued[0].queued_at
    if waited < rules.queue_wait and len(queued) < rules.max_players:
        return
    humans = queued[: max(1, rules.max_players)]
    _create_match(world, humans, rules)


def _create_match(world: WorldState, humans: list[PlayerState], rules: MatchRules) -> None:
    match_id = str(uuid4())
    room = max(0, rules.max_players - len(humans))
    bot_count = min(rules.bot_fill, room)
    bots = [_make_bot(world, match_id, index) for index in range(bot_count)]
    players = humans + bots
    _assign_teams(humans, rules, match_id)
    rng = random.Random(match_id)
    match = Match(match_id=match_id, player_ids=[player.player_id for player in players])
    _arm_zone(match, rules, rng, first=True)
    match.blockers = _spawn_objects(rules) if rules.loot_count > 0 else []
    match.loot = _spawn_loot(match_id, rng, rules, match.blockers)
    match.vehicles = _spawn_vehicles(match_id, rules, match.blockers)
    for index, player in enumerate(players):
        player.match_id = match_id
        player.status = "countdown"
        player.health = 100.0
        player.on_plane = True
        player.z = 40.0
        player.x = 0.0
        player.y = rules.map_size * (index + 1) / (len(players) + 1)
        if rules.warmup_island:
            _place_on_island(player, rules, rng)
        player.move_x = 0.0
        player.move_y = 0.0
        player.kills = 0
        player.distance = 0.0
        player.damage_dealt = 0.0
        player.drop_at = math.inf
        if player.is_bot and rules.drop_time > 0:
            player.drop_at = rules.drop_time * rng.uniform(0.2, 0.85)
        if rules.warmup_island:
            _clear_loadout(player)  # fists until the plane
        else:
            _give_starter(player)
    world.matches[match_id] = match
    match.events.append({"kind": "phase", "phase": "countdown"})
    logger.info("Match %s started with %s players", match_id, len(players))


def _assign_teams(humans: list[PlayerState], rules: MatchRules, match_id: str) -> None:
    """Players with no team are grouped in queue order into squads of `team_size`."""
    if rules.team_size <= 1:
        return
    loose = [player for player in humans if player.team_id is None]
    for index, player in enumerate(loose):
        player.team_id = f"{match_id}:squad:{index // rules.team_size}"


def _has_living_teammate(world: WorldState, match: Match, player: PlayerState) -> bool:
    if player.team_id is None:
        return False
    return any(
        other.team_id == player.team_id and other.player_id != player.player_id and other.status == "alive"
        for other in _combatants(world, match)
    )


def _knock(match: Match, target: PlayerState, killer_id: str | None, rules: MatchRules) -> None:
    target.status = "knocked"
    target.health = rules.knock_health
    target.bleed_left = rules.bleed_time
    target.knocked_by = killer_id
    target.move_x = 0.0
    target.move_y = 0.0
    target.reload_left = 0.0
    target.reviving = None
    target.revive_progress = 0.0
    _release_vehicle(match, target)
    match.events.append({"kind": "knock", "player_id": target.player_id, "killer_id": killer_id})


def _start_revive(world: WorldState, match: Match, player: PlayerState, rules: MatchRules) -> tuple[bool, str]:
    if player.team_id is None:
        return False, "No teammates"
    if player.reviving is not None:
        player.reviving = None
        player.revive_progress = 0.0
        return True, "Revive cancelled"
    nearest = None
    best = rules.pickup_radius
    for other in _combatants(world, match):
        if other.team_id != player.team_id or other.status != "knocked":
            continue
        distance = _distance(player, other)
        if distance <= best:
            nearest, best = other, distance
    if nearest is None:
        return False, "No teammate to revive"
    player.reviving = nearest.player_id
    player.revive_progress = 0.0
    player.move_x = 0.0
    player.move_y = 0.0
    return True, "Reviving"


def _tick_downed(world: WorldState, match: Match, dt: float, rules: MatchRules) -> None:
    for player in _combatants(world, match):
        if player.status == "knocked":
            if not _has_living_teammate(world, match, player):
                _eliminate(world, match, player, player.knocked_by, "team_wiped")
                continue
            player.bleed_left -= dt
            if player.bleed_left <= 0:
                _eliminate(world, match, player, player.knocked_by, "bleed_out")
        elif player.reviving is not None:
            target = world.players.get(player.reviving)
            if (
                player.status != "alive"
                or target is None
                or target.status != "knocked"
                or _distance(player, target) > rules.pickup_radius
                or math.hypot(player.move_x, player.move_y) > 0
            ):
                player.reviving = None
                player.revive_progress = 0.0
                continue
            player.revive_progress += dt
            if player.revive_progress >= rules.revive_time:
                target.status = "alive"
                target.health = rules.revive_health
                target.bleed_left = 0.0
                target.knocked_by = None
                player.reviving = None
                player.revive_progress = 0.0
                match.events.append({"kind": "revive", "player_id": target.player_id, "by": player.player_id})


def _starts_in(match: Match, rules: MatchRules) -> float | None:
    """Seconds until the plane, only while the warm-up countdown runs."""
    if match.phase != "countdown":
        return None
    return round(max(0.0, rules.countdown - match.clock), 1)


def _place_on_island(player: PlayerState, rules: MatchRules, rng: random.Random) -> None:
    """Warm-up spawn: on the ground near the map centre, not on the plane."""
    angle = rng.random() * math.tau
    dist = math.sqrt(rng.random()) * rules.island_radius
    player.x = rules.map_size / 2 + math.cos(angle) * dist
    player.y = rules.map_size / 2 + math.sin(angle) * dist
    player.on_plane = False
    player.z = 0.0


def start_training(world: WorldState, player_id: str, rules: MatchRules) -> tuple[bool, str]:
    """Solo practice range: no zone, no winner, nothing stored. Dummies stand still and respawn."""
    player = world.players.setdefault(player_id, PlayerState(player_id=player_id))
    if player.status in {"countdown", "dropping", "alive", "knocked"}:
        return False, "Already in a match"
    match_id = str(uuid4())
    rng = random.Random(match_id)
    match = Match(match_id=match_id, player_ids=[player_id], phase="playing", mode="training")
    match.zone_radius = rules.map_size * 2  # nothing is outside
    match.next_radius = match.zone_radius
    match.zone_dps = 0.0
    match.blockers = _spawn_objects(rules)
    match.loot = _spawn_loot(match_id, rng, rules, match.blockers) if rules.loot_count > 0 else []
    centre = rules.map_size / 2
    player.match_id = match_id
    player.status = "alive"
    player.on_plane = False
    player.z = 0.0
    player.health = 100.0
    player.x, player.y = centre, centre
    player.move_x = player.move_y = 0.0
    player.kills = 0
    player.distance = 0.0
    player.damage_dealt = 0.0
    player.team_id = None
    _give_training_kit(player)
    match.spawns[player_id] = (player.x, player.y)
    for index in range(max(0, rules.training_dummies)):
        dummy = _make_bot(world, match_id, index)
        dummy.nickname = f"Target {index + 1}"
        dummy.match_id = match_id
        dummy.status = "alive"
        dummy.on_plane = False
        dummy.z = 0.0
        angle = math.tau * index / max(1, rules.training_dummies)
        dummy.x = centre + math.cos(angle) * (12 + 6 * (index % 3))
        dummy.y = centre + math.sin(angle) * (12 + 6 * (index % 3))
        dummy.weapon = None
        match.player_ids.append(dummy.player_id)
        match.spawns[dummy.player_id] = (dummy.x, dummy.y)
    world.matches[match_id] = match
    match.events.append({"kind": "phase", "phase": "training"})
    return True, "Training started"


def _give_training_kit(player: PlayerState) -> None:
    _clear_loadout(player)
    player.inventory = {
        "rifle": 1,
        "m14ebr": 1,
        "pistol": 1,
        "medium": 120,
        "light": 120,
        "bandage": 5,
        "medkit": 2,
        "first_aid": 1,
        "scope_4x": 2,
        "ext_mag": 1,
    }
    player.weapon = "rifle"
    player.mag = int(WEAPONS["rifle"]["mag"])
    player.mags = {"rifle": player.mag, "pistol": int(WEAPONS["pistol"]["mag"])}
    player.armor = 1
    player.helmet = 1


def _training_respawn(world: WorldState, match: Match, victim: PlayerState, killer_id: str | None) -> None:
    if killer_id and killer_id != victim.player_id:
        killer = world.players.get(killer_id)
        if killer is not None:
            killer.kills += 1
    match.events.append(
        {
            "kind": "elimination",
            "player_id": victim.player_id,
            "killer_id": killer_id,
            "cause": "training",
            "weapon": _killer_weapon(world, killer_id),
        }
    )
    victim.health = 100.0
    victim.status = "alive"
    victim.reload_left = 0.0
    victim.fire_cooldown = 0.0
    spawn = match.spawns.get(victim.player_id)
    if spawn is not None:
        victim.x, victim.y = spawn
    if not victim.is_bot:
        _give_training_kit(victim)


_BOT_SKINS = ("recruit", "field_jacket", "ghillie_recon", "desert_striker", "night_ops")


def _make_bot(world: WorldState, match_id: str, index: int) -> PlayerState:
    bot = PlayerState(
        player_id=f"bot-{match_id}-{index}",
        nickname=f"Bot {index + 1}",
        skin=_BOT_SKINS[index % len(_BOT_SKINS)],
        is_bot=True,
        connected=False,
    )
    world.players[bot.player_id] = bot
    return bot


def _tick_match(world: WorldState, match: Match, dt: float, rules: MatchRules) -> None:
    if match.phase == "ended":
        match.clock += dt
        if match.clock >= rules.result_time:
            _dissolve(world, match)
        return
    _advance(world, match, dt, rules)
    if match.phase == "ended":
        return
    combatants = _combatants(world, match)
    for player in combatants:
        _tick_heal(match, player, dt)
        player.fire_cooldown = max(0.0, player.fire_cooldown - dt)
        if player.reload_left > 0:
            player.reload_left = max(0.0, player.reload_left - dt)
            if player.reload_left == 0:
                _finish_reload(player)
    if match.phase == "dropping":
        progress = 1.0 if rules.drop_time <= 0 else min(1.0, match.clock / rules.drop_time)
        plane_x = progress * rules.map_size
        for player in combatants:
            if player.on_plane:
                player.x = plane_x
                player.z = 40.0
            if player.is_bot and player.on_plane and match.clock >= player.drop_at:
                _leave_plane(player)
            elif not player.on_plane and player.status == "dropping":
                _glide(player, dt, rules)
    if match.phase == "countdown" and rules.warmup_island:
        for player in combatants:
            if not player.on_plane and player.status == "countdown":
                _move(player, dt, rules, match)
    if match.phase in {"dropping", "playing"}:
        if match.mode != "training":
            _bot_act(world, match, rules)
        for player in combatants:
            grounded = not player.on_plane and player.status in {"alive", "knocked"}
            _move(player, dt, rules, match) if grounded else None
    if match.phase == "playing" and match.mode != "training":
        _apply_zone(world, match, dt)
        _tick_downed(world, match, dt, rules)
        _maybe_finish(world, match)


def _advance(world: WorldState, match: Match, dt: float, rules: MatchRules) -> None:
    match.clock += dt
    if match.phase == "countdown" and match.clock >= rules.countdown:
        match.clock -= rules.countdown
        _enter_dropping(world, match, rules)
    if match.phase == "dropping" and match.clock >= rules.drop_time:
        match.clock -= rules.drop_time
        _enter_playing(world, match, rules)
    if match.phase != "playing" or rules.phase_duration <= 0 or match.mode == "training":
        return
    while match.clock >= rules.phase_duration:
        if match.zone_radius <= 0:
            match.clock = rules.phase_duration
            break
        match.clock -= rules.phase_duration
        _shrink_zone(match, rules)


def _enter_dropping(world: WorldState, match: Match, rules: MatchRules) -> None:
    match.phase = "dropping"
    players = _combatants(world, match)
    for index, player in enumerate(players):
        if player.status == "countdown":
            player.status = "dropping"
        if rules.warmup_island and not player.on_plane:
            # Everyone boards the plane when the warm-up ends and is armed for the jump.
            player.on_plane = True
            player.z = 40.0
            player.x = 0.0
            player.y = rules.map_size * (index + 1) / (len(players) + 1)
            player.move_x = 0.0
            player.move_y = 0.0
            _give_starter(player)
    match.events.append({"kind": "phase", "phase": "dropping"})


def _enter_playing(world: WorldState, match: Match, rules: MatchRules) -> None:
    match.phase = "playing"
    players = _combatants(world, match)
    if rules.drop_time <= 0:
        count = len(players)
        for index, player in enumerate(players):
            player.x = rules.map_size / 2 + (index - (count - 1) / 2) * 12
            player.y = rules.map_size / 2
            _land(player)
    else:
        for player in players:
            if player.on_plane or player.status in {"countdown", "dropping"}:
                _land(player)
    match.events.append({"kind": "phase", "phase": "playing"})
    _maybe_finish(world, match)


def _land(player: PlayerState) -> None:
    player.on_plane = False
    player.z = 0.0
    if player.status not in {"eliminated", "winner"}:
        player.status = "alive"


def _leave_plane(player: PlayerState) -> None:
    """Start the parachute descent. The player keeps status `dropping` until z reaches 0."""
    player.on_plane = False
    player.move_x = 0.0
    player.move_y = 0.0
    if player.z <= 0:
        _land(player)


def _glide(player: PlayerState, dt: float, rules: MatchRules) -> None:
    move_x, move_y = player.move_x, player.move_y
    magnitude = math.hypot(move_x, move_y)
    if magnitude > 1:
        move_x /= magnitude
        move_y /= magnitude
    player.x = min(rules.map_size, max(0.0, player.x + move_x * rules.glide_speed * dt))
    player.y = min(rules.map_size, max(0.0, player.y + move_y * rules.glide_speed * dt))
    if rules.fall_speed <= 0:
        _land(player)
        return
    player.z = max(0.0, player.z - rules.fall_speed * dt)
    if player.z <= 0:
        _land(player)


def _arm_zone(match: Match, rules: MatchRules, rng: random.Random, first: bool) -> None:
    radii = rules.zone_radii
    if first:
        match.zone_index = 0
        match.zone_radius = radii[0]
        match.zone_x = rules.map_size / 2
        match.zone_y = rules.map_size / 2
        match.zone_dps = rules.zone_dps[0]
        match.next_radius = radii[1] if len(radii) > 1 else 0.0
        match.next_x, match.next_y = _pick_next_zone(rng, match, rules)
        return
    match.zone_x = match.next_x
    match.zone_y = match.next_y
    match.zone_radius = match.next_radius
    match.zone_index += 1
    match.zone_dps = rules.zone_dps[min(match.zone_index, len(rules.zone_dps) - 1)]
    if match.zone_index + 1 < len(radii):
        match.next_radius = radii[match.zone_index + 1]
    else:
        match.next_radius = 0.0
    match.next_x, match.next_y = _pick_next_zone(rng, match, rules)


def _shrink_zone(match: Match, rules: MatchRules) -> None:
    rng = random.Random(f"{match.match_id}:{match.zone_index}")
    _arm_zone(match, rules, rng, first=False)
    match.events.append({"kind": "zone", "radius": round(match.zone_radius, 1)})


def _pick_next_zone(rng: random.Random, match: Match, rules: MatchRules) -> tuple[float, float]:
    margin = match.zone_radius - match.next_radius
    if margin <= 0:
        return match.zone_x, match.zone_y
    angle = rng.random() * math.tau
    dist = rng.random() * margin
    next_x = match.zone_x + math.cos(angle) * dist
    next_y = match.zone_y + math.sin(angle) * dist
    limit = match.next_radius
    next_x = min(max(next_x, limit), rules.map_size - limit)
    next_y = min(max(next_y, limit), rules.map_size - limit)
    return next_x, next_y


def _spawn_objects(rules: MatchRules) -> list[Blocker]:
    s = rules.map_size
    specs = (
        (0.22, 0.10, 0.28, 0.17, "warehouse", "North Warehouse"),
        (0.68, 0.16, 0.74, 0.23, "watchtower", "Timber Watchtower"),
        (0.18, 0.40, 0.24, 0.46, "container", "West Containers"),
        (0.18, 0.54, 0.24, 0.60, "container", "South Containers"),
        (0.74, 0.44, 0.81, 0.56, "bunker", "Echo Bunker"),
        (0.26, 0.72, 0.33, 0.80, "outpost", "Harbor Outpost"),
        (0.64, 0.74, 0.72, 0.82, "ruins", "Harbor Ruins"),
        (0.46, 0.25, 0.53, 0.31, "rock", "Highground Ridge"),
        (0.47, 0.68, 0.54, 0.73, "barricade", "Bridge Barricade"),
        (0.84, 0.72, 0.89, 0.78, "watchtower", "Beacon Tower"),
    )
    return [Blocker(s * x0, s * y0, s * x1, s * y1, kind=kind, name=name) for x0, y0, x1, y1, kind, name in specs]


def _point_blocked(x: float, y: float, blockers: list[Blocker], pad: float = 1.5) -> bool:
    return any(
        b.minimum_x - pad <= x <= b.maximum_x + pad and b.minimum_y - pad <= y <= b.maximum_y + pad
        for b in blockers
    )


def _open_point(rng: random.Random, margin: float, span: float, blockers: list[Blocker]) -> tuple[float, float]:
    for _ in range(20):
        x = margin + rng.random() * span
        y = margin + rng.random() * span
        if not _point_blocked(x, y, blockers):
            return x, y
    return margin + rng.random() * span, margin + rng.random() * span


def _spawn_loot(
    match_id: str,
    rng: random.Random,
    rules: MatchRules,
    blockers: list[Blocker] | None = None,
) -> list[LootNode]:
    pool: list[tuple[str, int]] = []
    for item_id, quantity, weight in LOOT_TABLE:
        pool.extend([(item_id, quantity)] * weight)
    rng.shuffle(pool)
    margin = 10.0
    span = max(1.0, rules.map_size - margin * 2)
    nodes = []
    obstacles = blockers or []
    for index, (item_id, quantity) in enumerate(pool[: rules.loot_count]):
        lx, ly = _open_point(rng, margin, span, obstacles)
        nodes.append(
            LootNode(
                loot_id=f"{match_id}:{index}",
                x=lx,
                y=ly,
                item_id=item_id,
                quantity=quantity,
            )
        )
    return nodes


def _bot_act(world: WorldState, match: Match, rules: MatchRules) -> None:
    if match.phase not in {"dropping", "playing"}:
        return
    enemies = [player for player in _combatants(world, match) if player.status == "alive" and not player.on_plane]
    for bot in _combatants(world, match):
        if not bot.is_bot or bot.status != "alive" or bot.on_plane:
            continue
        if bot.health < 45:
            heal = "medkit" if bot.inventory.get("medkit", 0) else "bandage" if bot.inventory.get("bandage", 0) else None
            if heal:
                _apply_heal(match, bot, heal)
                continue
        if bot.mag <= 0 and bot.weapon:
            _start_reload(bot)
        target = _nearest(bot, [player for player in enemies if player.player_id != bot.player_id])
        if target is not None and _distance(bot, target) <= _weapon_range(bot):
            bot.aim_x, bot.aim_y = _direction(bot, target)
            bot.move_x = 0.0
            bot.move_y = 0.0
            _shoot(world, match, bot, rules)
            continue
        loot = _nearest_loot(bot, match)
        goal = None
        if bot.weapon is None and loot is not None:
            goal = (loot.x, loot.y)
            if _distance_xy(bot, loot.x, loot.y) <= rules.pickup_radius:
                _pickup(world, match, bot, loot.loot_id, rules)
        elif target is not None:
            goal = (target.x, target.y)
        elif _outside(bot, match):
            goal = (match.zone_x, match.zone_y)
        if goal is None:
            bot.move_x = 0.0
            bot.move_y = 0.0
            continue
        bot.move_x, bot.move_y = _direction_xy(bot, goal[0], goal[1])


def _apply_zone(world: WorldState, match: Match, dt: float) -> None:
    for player in _combatants(world, match):
        if player.status not in {"alive", "knocked"} or player.on_plane or not _outside(player, match):
            continue
        player.health = max(0.0, player.health - match.zone_dps * dt)
    for player in _combatants(world, match):
        if player.status in {"alive", "knocked"} and player.health <= 0:
            _eliminate(world, match, player, player.knocked_by, "zone")


def _shoot(world: WorldState, match: Match, shooter: PlayerState, rules: MatchRules) -> tuple[bool, str]:
    if shooter.vehicle:
        return False, "Leave the vehicle first"
    if shooter.reload_left > 0:
        return False, "Reloading"
    weapon = WEAPONS.get(shooter.weapon or "")
    if weapon is None:
        return False, "No weapon"
    if shooter.mag <= 0:
        return False, "Reload"
    if shooter.fire_cooldown > 0:
        return False, "Cooling down"
    aim_x, aim_y = shooter.aim_x, shooter.aim_y
    length = math.hypot(aim_x, aim_y)
    if length <= 0:
        return False, "Aim first"
    aim_x /= length
    aim_y /= length
    shooter.mag -= 1
    shooter.fire_cooldown = weapon["cooldown"]
    target = None
    reach = _reach(shooter)
    shooter.healing = None
    closest = reach
    for other in _combatants(world, match):
        if other.player_id == shooter.player_id or other.status not in {"alive", "knocked"} or other.on_plane:
            continue
        if shooter.team_id is not None and other.team_id == shooter.team_id:
            continue
        offset_x = other.x - shooter.x
        offset_y = other.y - shooter.y
        forward = offset_x * aim_x + offset_y * aim_y
        if forward < 0 or forward > reach:
            continue
        side = abs(offset_x * aim_y - offset_y * aim_x)
        if side <= rules.hit_radius and forward < closest:
            target = other
            closest = forward
    if target is None:
        return True, "Missed"
    damage = damage_after_gear(float(weapon["damage"]), target.armor, target.helmet)
    target.healing = None
    dealt = min(damage, target.health)
    target.health = max(0.0, target.health - damage)
    shooter.damage_dealt += dealt
    match.events.append(
        {
            "kind": "hit",
            "attacker_id": shooter.player_id,
            "target_id": target.player_id,
            "damage": round(damage, 1),
            "weapon": shooter.weapon,
            "health": round(target.health, 1),
        }
    )
    if target.health <= 0:
        if target.status == "alive" and _has_living_teammate(world, match, target):
            _knock(match, target, shooter.player_id, rules)
            return True, "Knocked"
        _eliminate(world, match, target, target.knocked_by or shooter.player_id, "shot")
        _maybe_finish(world, match)
        return True, "Eliminated"
    return True, "Hit"


def _start_reload(player: PlayerState) -> tuple[bool, str]:
    weapon = WEAPONS.get(player.weapon or "")
    if weapon is None:
        return False, "No weapon"
    if player.reload_left > 0:
        return False, "Reloading"
    ammo = str(weapon["ammo"])
    if player.mag >= _mag_size(player):
        return False, "Magazine full"
    if player.inventory.get(ammo, 0) <= 0:
        return False, "No ammo"
    player.reload_left = float(weapon["reload"])
    return True, "Reloading"


def _finish_reload(player: PlayerState) -> None:
    weapon = WEAPONS.get(player.weapon or "")
    if weapon is None:
        return
    ammo = str(weapon["ammo"])
    need = _mag_size(player) - player.mag
    take = min(need, player.inventory.get(ammo, 0))
    if take <= 0:
        return
    player.inventory[ammo] = player.inventory.get(ammo, 0) - take
    if player.inventory[ammo] <= 0:
        player.inventory.pop(ammo, None)
    player.mag += take
    player.mags[player.weapon or ""] = player.mag


def _pickup(
    world: WorldState,
    match: Match,
    player: PlayerState,
    loot_id: str | None,
    rules: MatchRules,
) -> tuple[bool, str]:
    node = next((item for item in match.loot if item.loot_id == loot_id and not item.taken), None)
    if node is None:
        return False, "Loot is gone"
    if _distance_xy(player, node.x, node.y) > rules.pickup_radius:
        return False, "Too far"
    gear = gear_of(node.item_id)
    if gear is not None:
        return _wear(match, player, node, gear)
    if is_weapon(node.item_id):
        slot = slot_of(node.item_id)
        if slot_count(player.inventory, slot) >= SLOT_LIMITS[slot]:
            return False, "Weapon slots full"
    held = player.inventory.get(node.item_id, 0)
    if is_weapon(node.item_id):
        take = node.quantity
    else:
        take = min(node.quantity, stack_limit(player.backpack) - held)
        if take <= 0:
            return False, "Stack full"
    player.inventory[node.item_id] = held + take
    node.quantity -= take
    if node.quantity <= 0:
        node.taken = True
    if is_weapon(node.item_id) and _should_auto_equip(player, node.item_id):
        _equip(player, node.item_id)
    player.supplies += 1
    match.events.append(
        {"kind": "pickup", "player_id": player.player_id, "item_id": node.item_id, "quantity": take}
    )
    return True, f"Picked up {node.item_id}"


def _should_auto_equip(player: PlayerState, item_id: str) -> bool:
    """Empty hands, or a pistol in hand and a primary weapon picked up, switch to the new weapon."""
    if player.weapon is None:
        return True
    return player.weapon in PISTOLS and slot_of(item_id) == "primary"


def _wear(match: Match, player: PlayerState, node: LootNode, gear: tuple[str, int]) -> tuple[bool, str]:
    slot, level = gear
    current = getattr(player, slot)
    if current >= level:
        return False, f"Already wearing a level {current} {slot}"
    setattr(player, slot, level)
    player.supplies += 1
    node.taken = True
    if current > 0:
        # The worn piece goes back on the ground where the new one was.
        _drop_node(match, f"{slot}_{current}", 1, node.x, node.y, None)
    match.events.append({"kind": "pickup", "player_id": player.player_id, "item_id": node.item_id, "quantity": 1})
    return True, f"Equipped {node.item_id}"


def _drop_node(match: Match, item_id: str, quantity: int, x: float, y: float, crate_id: str | None) -> LootNode:
    match.drop_serial += 1
    node = LootNode(
        loot_id=f"{match.match_id}:drop:{match.drop_serial}",
        x=x,
        y=y,
        item_id=item_id,
        quantity=quantity,
        crate_id=crate_id,
    )
    match.loot.append(node)
    return node


def _drop_crate(match: Match, victim: PlayerState) -> None:
    """Leave the victim's inventory and worn gear on the ground as one crate."""
    items = [(item_id, qty) for item_id, qty in victim.inventory.items() if qty > 0]
    items += [(f"{slot}_{getattr(victim, slot)}", 1) for slot in ("armor", "helmet", "backpack") if getattr(victim, slot)]
    items += [(name, 1) for fitted in victim.attachments.values() for name in fitted]
    if not items:
        return
    crate_id = f"{match.match_id}:crate:{victim.player_id}"
    for item_id, quantity in items:
        _drop_node(match, item_id, quantity, victim.x, victim.y, crate_id)
    match.events.append(
        {
            "kind": "crate",
            "player_id": victim.player_id,
            "crate_id": crate_id,
            "x": round(victim.x, 2),
            "y": round(victim.y, 2),
            "items": len(items),
        }
    )


def _use_item(match: Match, player: PlayerState, item_id: str | None, rules: MatchRules) -> tuple[bool, str]:
    """Start using a healing item. Using the item again, or shooting or being hit, cancels it."""
    if player.healing is not None:
        player.healing = None
        player.heal_left = 0.0
        return True, "Heal cancelled"
    if not item_id or item_id not in HEALS:
        return False, "Not a healing item"
    if player.inventory.get(item_id, 0) <= 0:
        return False, "Item not carried"
    if player.health >= 100:
        return False, "Health is full"
    duration = HEAL_TIME.get(item_id, 0.0) * rules.heal_time_scale
    if duration <= 0:
        return _apply_heal(match, player, item_id)
    if player.vehicle:
        return False, "Leave the vehicle first"
    player.healing = item_id
    player.heal_left = duration
    return True, f"Using {item_id}"


def _apply_heal(match: Match, player: PlayerState, item_id: str) -> tuple[bool, str]:
    player.healing = None
    player.heal_left = 0.0
    if player.inventory.get(item_id, 0) <= 0 or player.health >= 100:
        return False, "Heal cancelled"
    player.inventory[item_id] -= 1
    if player.inventory[item_id] <= 0:
        del player.inventory[item_id]
    player.health = min(100.0, player.health + HEALS[item_id])
    match.events.append({"kind": "heal", "player_id": player.player_id, "item_id": item_id})
    return True, "Healed"


def _tick_heal(match: Match, player: PlayerState, dt: float) -> None:
    if player.healing is None:
        return
    if player.status != "alive" or player.on_plane:
        player.healing = None
        return
    player.heal_left -= dt
    if player.heal_left <= 0:
        _apply_heal(match, player, player.healing)


def _mag_size(player: PlayerState) -> int:
    weapon = WEAPONS.get(player.weapon or "")
    if weapon is None:
        return 0
    bonus = sum(
        int(ATTACHMENTS[name].get("mag_bonus", 0)) for name in player.attachments.get(player.weapon or "", [])
    )
    return int(weapon["mag"]) + bonus


def _reach(player: PlayerState) -> float:
    weapon = WEAPONS.get(player.weapon or "")
    if weapon is None:
        return 0.0
    mult = 1.0
    for name in player.attachments.get(player.weapon or "", []):
        mult *= float(ATTACHMENTS[name].get("range_mult", 1.0))
    return float(weapon["range"]) * mult


def _killer_weapon(world: WorldState, killer_id: str | None) -> str | None:
    killer = world.players.get(killer_id) if killer_id else None
    return (killer.weapon or "fist") if killer is not None else None


def _attach(player: PlayerState, item_id: str | None) -> tuple[bool, str]:
    if not item_id or item_id not in ATTACHMENTS:
        return False, "Not an attachment"
    if player.inventory.get(item_id, 0) <= 0:
        return False, "Item not carried"
    if player.weapon is None:
        return False, "No weapon"
    if not can_attach(item_id, player.weapon):
        return False, f"{item_id} does not fit {player.weapon}"
    fitted = player.attachments.setdefault(player.weapon, [])
    if item_id in fitted:
        return False, "Already fitted"
    player.inventory[item_id] -= 1
    if player.inventory[item_id] <= 0:
        del player.inventory[item_id]
    fitted.append(item_id)
    return True, f"Fitted {item_id}"


def _equip(player: PlayerState, item_id: str | None) -> tuple[bool, str]:
    if not item_id or not is_weapon(item_id):
        return False, "Not a weapon"
    if player.inventory.get(item_id, 0) <= 0:
        return False, "Item not carried"
    if player.weapon:
        player.mags[player.weapon] = player.mag
    player.weapon = item_id
    player.mag = player.mags.get(item_id, 0)
    player.reload_left = 0.0
    return True, f"Equipped {item_id}"


def _discard(match: Match, player: PlayerState, item_id: str | None) -> tuple[bool, str]:
    if not item_id or player.inventory.get(item_id, 0) <= 0:
        return False, "Item not carried"
    if player.vehicle:
        return False, "Leave the vehicle first"
    player.inventory[item_id] -= 1
    if player.inventory[item_id] <= 0:
        del player.inventory[item_id]
        player.mags.pop(item_id, None)
    if item_id not in player.inventory:
        for name in player.attachments.pop(item_id, []):
            player.inventory[name] = player.inventory.get(name, 0) + 1
    if item_id == player.weapon and item_id not in player.inventory:
        player.weapon = None
        player.mag = 0
        player.reload_left = 0.0
    # Dropped items stay in the match so anyone can pick them up again.
    _drop_node(match, item_id, 1, player.x, player.y, None)
    return True, "Discarded"


def _jump_action(player: PlayerState, match: Match | None) -> tuple[bool, str]:
    if match is None or not player.on_plane:
        return False, "Not on the plane"
    if match.phase != "dropping":
        return False, "Wait for the drop"
    _leave_plane(player)
    return True, "Jumped"


def _eliminate(
    world: WorldState,
    match: Match,
    victim: PlayerState,
    killer_id: str | None,
    cause: str,
) -> None:
    if victim.status in {"eliminated", "winner"}:
        return
    if match.mode == "training":
        _training_respawn(world, match, victim, killer_id)
        return
    landed = victim.status in {"alive", "knocked"} and not victim.on_plane
    victim.bleed_left = 0.0
    victim.reviving = None
    victim.revive_progress = 0.0
    for other in world.players.values():
        if other.reviving == victim.player_id:
            other.reviving = None
            other.revive_progress = 0.0
    victim.status = "eliminated"
    victim.health = 0.0
    victim.move_x = 0.0
    victim.move_y = 0.0
    victim.on_plane = False
    _release_vehicle(match, victim)
    if landed:
        _drop_crate(match, victim)
    _clear_loadout(victim)
    if killer_id and killer_id != victim.player_id:
        killer = world.players.get(killer_id)
        if killer is not None:
            killer.kills += 1
            match.kills[killer_id] = match.kills.get(killer_id, 0) + 1
    match.elimination_order.append(victim.player_id)
    match.events.append(
        {
            "kind": "elimination",
            "player_id": victim.player_id,
            "killer_id": killer_id,
            "cause": cause,
            "weapon": _killer_weapon(world, killer_id) if cause == "shot" else None,
        }
    )


def _maybe_finish(world: WorldState, match: Match) -> None:
    if match.phase != "playing" or match.recorded or match.mode == "training":
        return
    living = [player for player in _combatants(world, match) if player.status == "alive"]
    teams = {player.team_id or player.player_id for player in living}
    if len(match.player_ids) <= 1:
        if living:
            return
        match.phase = "ended"
        match.winner_id = None
        match.clock = 0.0
        _record_results(world, match)
        return
    if len(teams) > 1:
        return
    match.phase = "ended"
    match.clock = 0.0
    match.winner_id = living[0].player_id if living else None
    match.winner_ids = [player.player_id for player in living]
    for winner in living:
        winner.status = "winner"
        winner.move_x = 0.0
        winner.move_y = 0.0
    match.events.append({"kind": "match_end", "winner_id": match.winner_id})
    logger.info("Match %s ended, winner %s", match.match_id, match.winner_id)
    _record_results(world, match)


def _record_results(world: WorldState, match: Match) -> None:
    if match.recorded:
        return
    match.recorded = True
    placement: dict[str, int] = {}
    next_place = 1
    if match.winner_id:
        placement[match.winner_id] = 1
        for winner_id in match.winner_ids:
            placement[winner_id] = 1
        next_place = 2
    for player_id in reversed(match.elimination_order):
        if player_id not in placement:
            placement[player_id] = next_place
            next_place += 1
    for player_id in match.player_ids:
        player = world.players.get(player_id)
        if player is None or player.is_bot:
            continue
        world.pending_results.append(
            MatchResult(
                player_id=player_id,
                kills=match.kills.get(player_id, 0),
                win=player_id in (match.winner_ids or [match.winner_id]),
                placement=placement.get(player_id, next_place),
            )
        )


def _dissolve(world: WorldState, match: Match) -> None:
    for player_id in match.player_ids:
        player = world.players.get(player_id)
        if player is None:
            continue
        if player.is_bot:
            world.players.pop(player_id, None)
            continue
        if player.match_id == match.match_id:
            player.match_id = None
            player.status = "roaming"
            player.on_plane = False
            player.health = 100.0
            player.kills = 0
            player.bleed_left = 0.0
            player.reviving = None
            if player.team_id and ":squad:" in player.team_id:
                player.team_id = None
            _clear_loadout(player)
    world.matches.pop(match.match_id, None)


def _move(player: PlayerState, dt: float, rules: MatchRules, match: Match | None = None) -> None:
    move_x, move_y = player.move_x, player.move_y
    magnitude = math.hypot(move_x, move_y)
    if magnitude > 1:
        move_x /= magnitude
        move_y /= magnitude
    speed = rules.crawl_speed if player.status == "knocked" else rules.speed
    occupied = _occupied_vehicle(match, player) if match is not None else None
    if occupied is not None:
        speed = float(VEHICLES[occupied.kind]["speed"])
    next_x = min(rules.map_size, max(0.0, player.x + move_x * speed * dt))
    next_y = min(rules.map_size, max(0.0, player.y + move_y * speed * dt))
    if match is not None:
        next_x, next_y = slide(player.x, player.y, next_x, next_y, match.blockers)
        player.distance += math.hypot(next_x - player.x, next_y - player.y)
    player.x = next_x
    player.y = next_y
    if occupied is not None:
        occupied.x = player.x
        occupied.y = player.y


def _spawn_vehicles(
    match_id: str,
    rules: MatchRules,
    blockers: list[Blocker] | None = None,
) -> list[VehicleNode]:
    rng = random.Random(f"{match_id}:vehicles")
    margin = 20.0
    span = max(1.0, rules.map_size - margin * 2)
    obstacles = blockers or []
    kinds = ("buggy", "jeep", "buggy")
    nodes = []
    for index, kind in enumerate(kinds):
        vx, vy = _open_point(rng, margin, span, obstacles)
        nodes.append(
            VehicleNode(
                vehicle_id=f"{match_id}:vehicle:{index}",
                kind=kind,
                x=vx,
                y=vy,
            )
        )
    return nodes


def _board(match: Match, player: PlayerState, rules: MatchRules) -> tuple[bool, str]:
    if player.vehicle:
        return False, "Already in a vehicle"
    nearest = None
    nearest_distance = rules.pickup_radius
    for node in match.vehicles:
        if node.occupant is not None:
            continue
        distance = _distance_xy(player, node.x, node.y)
        if distance <= nearest_distance:
            nearest = node
            nearest_distance = distance
    if nearest is None:
        return False, "No vehicle nearby"
    nearest.occupant = player.player_id
    player.vehicle = nearest.vehicle_id
    return True, "Boarded"


def _exit_vehicle(match: Match, player: PlayerState) -> tuple[bool, str]:
    if _occupied_vehicle(match, player) is None:
        return False, "Not in a vehicle"
    _release_vehicle(match, player)
    return True, "Left the vehicle"


def _occupied_vehicle(match: Match | None, player: PlayerState) -> VehicleNode | None:
    if match is None or not player.vehicle:
        return None
    return next((node for node in match.vehicles if node.vehicle_id == player.vehicle), None)


def _release_vehicle(match: Match, player: PlayerState) -> None:
    node = _occupied_vehicle(match, player)
    if node is not None:
        node.occupant = None
    player.vehicle = None


def _give_starter(player: PlayerState) -> None:
    _clear_loadout(player)
    player.inventory = {"pistol": 1, "light": 24}
    player.weapon = "pistol"
    player.mag = int(WEAPONS["pistol"]["mag"])
    player.mags = {"pistol": player.mag}


def _clear_loadout(player: PlayerState) -> None:
    player.inventory = {}
    player.mags = {}
    player.weapon = None
    player.mag = 0
    player.fire_cooldown = 0.0
    player.reload_left = 0.0
    player.vehicle = None
    player.attachments = {}
    player.healing = None
    player.heal_left = 0.0
    player.armor = 0
    player.helmet = 0
    player.backpack = 0


def _match_for(world: WorldState, player: PlayerState | None) -> Match | None:
    if player is None or not player.match_id:
        return None
    return world.matches.get(player.match_id)


def _combatants(world: WorldState, match: Match) -> list[PlayerState]:
    # A player eliminated here may already be queued or playing elsewhere; this match leaves them alone.
    return [
        world.players[player_id]
        for player_id in match.player_ids
        if player_id in world.players and world.players[player_id].match_id == match.match_id
    ]


def _outside(player: PlayerState, match: Match) -> bool:
    return math.hypot(player.x - match.zone_x, player.y - match.zone_y) > match.zone_radius


def _distance(left: PlayerState, right: PlayerState) -> float:
    return _distance_xy(left, right.x, right.y)


def _distance_xy(player: PlayerState, x: float, y: float) -> float:
    return math.hypot(player.x - x, player.y - y)


def _direction(origin: PlayerState, target: PlayerState) -> tuple[float, float]:
    return _direction_xy(origin, target.x, target.y)


def _direction_xy(origin: PlayerState, x: float, y: float) -> tuple[float, float]:
    dx = x - origin.x
    dy = y - origin.y
    length = math.hypot(dx, dy)
    if length <= 0:
        return 1.0, 0.0
    return dx / length, dy / length


def _nearest(origin: PlayerState, others: list[PlayerState]) -> PlayerState | None:
    living = [other for other in others if other.status == "alive"]
    if not living:
        return None
    return min(living, key=lambda other: _distance(origin, other))


def _nearest_loot(player: PlayerState, match: Match) -> LootNode | None:
    available = [node for node in match.loot if not node.taken]
    if not available:
        return None
    return min(available, key=lambda node: _distance_xy(player, node.x, node.y))


def _weapon_range(player: PlayerState) -> float:
    weapon = WEAPONS.get(player.weapon or "")
    if weapon is None:
        return 0.0
    return float(weapon["range"])


def _summary(world: WorldState, match: Match) -> dict:
    alive = sum(1 for player in _combatants(world, match) if player.status == "alive")
    return {
        "match_id": match.match_id,
        "status": match.phase,
        "player_ids": list(match.player_ids),
        "alive": alive,
        "winner_id": match.winner_id,
        "mode": match.mode,
    }


def _match_payload(world: WorldState, match: Match, player: PlayerState, rules: MatchRules) -> dict:
    payload = {
        "phase": match.phase,
        "mode": match.mode,
        "starts_in": _starts_in(match, rules),
        "total": len(_combatants(world, match)),
        "alive": sum(1 for other in _combatants(world, match) if other.status == "alive"),
        "winner_id": match.winner_id,
        "zone": {
            "x": round(match.zone_x, 2),
            "y": round(match.zone_y, 2),
            "radius": round(match.zone_radius, 2),
            "next_x": round(match.next_x, 2),
            "next_y": round(match.next_y, 2),
            "next_radius": round(match.next_radius, 2),
            "dps": match.zone_dps,
        },
        "players": [
            {
                "player_id": other.player_id,
                "nickname": other.nickname,
                "skin": other.skin,
                "x": round(other.x, 2),
                "y": round(other.y, 2),
                "health": round(other.health, 1),
                "status": other.status,
                "team_id": other.team_id,
                "kills": other.kills,
                "weapon": other.weapon,
                "bot": other.is_bot,
            }
            for other in _combatants(world, match)
        ],
        "objects": [
            {
                "kind": blocker.kind,
                "name": blocker.name,
                "minimum_x": round(blocker.minimum_x, 2),
                "minimum_y": round(blocker.minimum_y, 2),
                "maximum_x": round(blocker.maximum_x, 2),
                "maximum_y": round(blocker.maximum_y, 2),
            }
            for blocker in match.blockers
        ],
        "loot": [
            {
                "loot_id": node.loot_id,
                "x": round(node.x, 2),
                "y": round(node.y, 2),
                "item_id": node.item_id,
                "quantity": node.quantity,
                "crate_id": node.crate_id,
            }
            for node in match.loot
            if not node.taken
        ],
        "vehicles": [
            {
                "vehicle_id": node.vehicle_id,
                "kind": node.kind,
                "x": round(node.x, 2),
                "y": round(node.y, 2),
                "occupant": node.occupant,
            }
            for node in match.vehicles
        ],
        "self": {
            "weapon": player.weapon,
            "mag": player.mag,
            "reload": round(player.reload_left, 2),
            "on_plane": player.on_plane,
            "healing": player.healing,
            "heal_left": round(player.heal_left, 2),
            "supplies": player.supplies,
            "attachments": list(player.attachments.get(player.weapon or "", [])),
            "mag_size": _mag_size(player),
            "slots": {
                slot: [item for item, qty in player.inventory.items() if qty > 0 and item in WEAPONS and slot_of(item) == slot]
                for slot in SLOT_LIMITS
            },
            "nearby": [
                {"loot_id": node.loot_id, "item_id": node.item_id, "quantity": node.quantity}
                for node in match.loot
                if not node.taken and _distance_xy(player, node.x, node.y) <= rules.pickup_radius
            ],
            "team_id": player.team_id,
            "bleed_left": round(player.bleed_left, 1),
            "reviving": player.reviving,
            "revive_progress": round(player.revive_progress, 2),
            "z": round(player.z, 2),
            "inventory": dict(player.inventory),
            "armor": player.armor,
            "helmet": player.helmet,
            "backpack": player.backpack,
            "stack_limit": stack_limit(player.backpack),
            "distance": round(player.distance, 1),
            "damage": round(player.damage_dealt, 1),
        },
        "events": list(match.events),
    }
    if match.phase == "ended":
        payload["results"] = _standings(world, match)
    return payload


def _standings(world: WorldState, match: Match) -> list[dict]:
    """Placement table for the end-of-match screen: winner first, then reverse elimination order."""
    order = ([match.winner_id] if match.winner_id else []) + list(reversed(match.elimination_order))
    rows = []
    for place, player_id in enumerate(dict.fromkeys(order), start=1):
        player = world.players.get(player_id)
        rows.append(
            {
                "player_id": player_id,
                "nickname": player.nickname if player else None,
                "placement": place,
                "kills": match.kills.get(player_id, 0),
                "damage": round(player.damage_dealt, 1) if player and player.match_id == match.match_id else None,
                "distance": round(player.distance, 1) if player and player.match_id == match.match_id else None,
                "bot": player.is_bot if player else player_id.startswith("bot-"),
            }
        )
    return rows
