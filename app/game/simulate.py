"""Match simulation. Callers hold the world lock. This module does no I/O."""

import logging
import math
import random
from uuid import uuid4

from app.game.items import HEALS, LOOT_TABLE, MAX_STACK, MAX_WEAPONS, WEAPONS, is_weapon, weapon_count
from app.game.rules import MatchRules
from app.game.state import LootNode, Match, MatchResult, PlayerState, WorldState

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
    if player.status in {"countdown", "dropping", "alive"}:
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
    if player is None or match is None or player.status not in {"countdown", "dropping", "alive"}:
        return False, "Not in a match"
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
    if match is None or player.status != "alive" or player.on_plane or match.phase not in {"dropping", "playing"}:
        return False, "Not in a match"
    if action == "shoot":
        return _shoot(world, match, player, rules)
    if action == "reload":
        return _start_reload(player)
    if action == "pickup":
        return _pickup(world, match, player, loot_id, rules)
    if action == "use":
        return _use_item(match, player, item_id)
    if action == "equip":
        return _equip(player, item_id)
    if action == "discard":
        return _discard(player, item_id)
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
    }
    match = world.matches.get(player.match_id) if player.match_id else None
    if match is not None:
        payload["match"] = _match_payload(world, match, player)
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
    rng = random.Random(match_id)
    match = Match(match_id=match_id, player_ids=[player.player_id for player in players])
    _arm_zone(match, rules, rng, first=True)
    match.loot = _spawn_loot(match_id, rng, rules)
    for index, player in enumerate(players):
        player.match_id = match_id
        player.status = "countdown"
        player.health = 100.0
        player.on_plane = True
        player.z = 40.0
        player.x = 0.0
        player.y = rules.map_size * (index + 1) / (len(players) + 1)
        player.move_x = 0.0
        player.move_y = 0.0
        player.kills = 0
        player.drop_at = math.inf
        if player.is_bot and rules.drop_time > 0:
            player.drop_at = rules.drop_time * rng.uniform(0.2, 0.85)
        _give_starter(player)
    world.matches[match_id] = match
    match.events.append({"kind": "phase", "phase": "countdown"})
    logger.info("Match %s started with %s players", match_id, len(players))


def _make_bot(world: WorldState, match_id: str, index: int) -> PlayerState:
    bot = PlayerState(player_id=f"bot-{match_id}-{index}", is_bot=True, connected=False)
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
                _land(player)
    if match.phase in {"dropping", "playing"}:
        _bot_act(world, match, rules)
        for player in combatants:
            grounded = not player.on_plane and player.status == "alive"
            _move(player, dt, rules) if grounded else None
    if match.phase == "playing":
        _apply_zone(world, match, dt)
        _maybe_finish(world, match)


def _advance(world: WorldState, match: Match, dt: float, rules: MatchRules) -> None:
    match.clock += dt
    if match.phase == "countdown" and match.clock >= rules.countdown:
        match.clock -= rules.countdown
        _enter_dropping(world, match)
    if match.phase == "dropping" and match.clock >= rules.drop_time:
        match.clock -= rules.drop_time
        _enter_playing(world, match, rules)
    if match.phase != "playing" or rules.phase_duration <= 0:
        return
    while match.clock >= rules.phase_duration:
        if match.zone_radius <= 0:
            match.clock = rules.phase_duration
            break
        match.clock -= rules.phase_duration
        _shrink_zone(match, rules)


def _enter_dropping(world: WorldState, match: Match) -> None:
    match.phase = "dropping"
    for player in _combatants(world, match):
        if player.status == "countdown":
            player.status = "dropping"
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


def _spawn_loot(match_id: str, rng: random.Random, rules: MatchRules) -> list[LootNode]:
    pool: list[tuple[str, int]] = []
    for item_id, quantity, weight in LOOT_TABLE:
        pool.extend([(item_id, quantity)] * weight)
    rng.shuffle(pool)
    margin = 10.0
    span = max(1.0, rules.map_size - margin * 2)
    nodes = []
    for index, (item_id, quantity) in enumerate(pool[: rules.loot_count]):
        nodes.append(
            LootNode(
                loot_id=f"{match_id}:{index}",
                x=margin + rng.random() * span,
                y=margin + rng.random() * span,
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
                _use_item(match, bot, heal)
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
        if player.status != "alive" or player.on_plane or not _outside(player, match):
            continue
        player.health = max(0.0, player.health - match.zone_dps * dt)
    for player in _combatants(world, match):
        if player.status == "alive" and player.health <= 0:
            _eliminate(world, match, player, None, "zone")


def _shoot(world: WorldState, match: Match, shooter: PlayerState, rules: MatchRules) -> tuple[bool, str]:
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
    closest = weapon["range"]
    for other in _combatants(world, match):
        if other.player_id == shooter.player_id or other.status != "alive" or other.on_plane:
            continue
        offset_x = other.x - shooter.x
        offset_y = other.y - shooter.y
        forward = offset_x * aim_x + offset_y * aim_y
        if forward < 0 or forward > weapon["range"]:
            continue
        side = abs(offset_x * aim_y - offset_y * aim_x)
        if side <= rules.hit_radius and forward < closest:
            target = other
            closest = forward
    if target is None:
        return True, "Missed"
    target.health = max(0.0, target.health - weapon["damage"])
    match.events.append(
        {
            "kind": "hit",
            "attacker_id": shooter.player_id,
            "target_id": target.player_id,
            "damage": weapon["damage"],
            "health": round(target.health, 1),
        }
    )
    if target.health <= 0:
        _eliminate(world, match, target, shooter.player_id, "shot")
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
    if player.mag >= int(weapon["mag"]):
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
    need = int(weapon["mag"]) - player.mag
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
    if is_weapon(node.item_id) and weapon_count(player.inventory) >= MAX_WEAPONS:
        return False, "Weapon slots full"
    held = player.inventory.get(node.item_id, 0)
    if not is_weapon(node.item_id) and held >= MAX_STACK:
        return False, "Stack full"
    player.inventory[node.item_id] = held + node.quantity
    node.taken = True
    if is_weapon(node.item_id) and player.weapon is None:
        _equip(player, node.item_id)
    match.events.append({"kind": "pickup", "player_id": player.player_id, "item_id": node.item_id})
    return True, f"Picked up {node.item_id}"


def _use_item(match: Match, player: PlayerState, item_id: str | None) -> tuple[bool, str]:
    if not item_id or item_id not in HEALS:
        return False, "Not a healing item"
    if player.inventory.get(item_id, 0) <= 0:
        return False, "Item not carried"
    if player.health >= 100:
        return False, "Health is full"
    player.inventory[item_id] -= 1
    if player.inventory[item_id] <= 0:
        del player.inventory[item_id]
    player.health = min(100.0, player.health + HEALS[item_id])
    match.events.append({"kind": "heal", "player_id": player.player_id, "item_id": item_id})
    return True, "Healed"


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


def _discard(player: PlayerState, item_id: str | None) -> tuple[bool, str]:
    if not item_id or player.inventory.get(item_id, 0) <= 0:
        return False, "Item not carried"
    player.inventory[item_id] -= 1
    if player.inventory[item_id] <= 0:
        del player.inventory[item_id]
    if item_id == player.weapon:
        player.weapon = None
        player.mag = 0
    return True, "Discarded"


def _jump_action(player: PlayerState, match: Match | None) -> tuple[bool, str]:
    if match is None or not player.on_plane:
        return False, "Not on the plane"
    if match.phase != "dropping":
        return False, "Wait for the drop"
    _land(player)
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
    victim.status = "eliminated"
    victim.health = 0.0
    victim.move_x = 0.0
    victim.move_y = 0.0
    victim.on_plane = False
    if killer_id and killer_id != victim.player_id:
        killer = world.players.get(killer_id)
        if killer is not None:
            killer.kills += 1
    match.elimination_order.append(victim.player_id)
    match.events.append(
        {"kind": "elimination", "player_id": victim.player_id, "killer_id": killer_id, "cause": cause}
    )


def _maybe_finish(world: WorldState, match: Match) -> None:
    if match.phase != "playing" or match.recorded:
        return
    living = [player for player in _combatants(world, match) if player.status == "alive"]
    if len(match.player_ids) <= 1:
        if living:
            return
        match.phase = "ended"
        match.winner_id = None
        match.clock = 0.0
        _record_results(world, match)
        return
    if len(living) > 1:
        return
    match.phase = "ended"
    match.clock = 0.0
    match.winner_id = living[0].player_id if living else None
    if match.winner_id:
        winner = world.players[match.winner_id]
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
                kills=player.kills,
                win=player_id == match.winner_id,
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
            _clear_loadout(player)
    world.matches.pop(match.match_id, None)


def _move(player: PlayerState, dt: float, rules: MatchRules) -> None:
    move_x, move_y = player.move_x, player.move_y
    magnitude = math.hypot(move_x, move_y)
    if magnitude > 1:
        move_x /= magnitude
        move_y /= magnitude
    player.x = min(rules.map_size, max(0.0, player.x + move_x * rules.speed * dt))
    player.y = min(rules.map_size, max(0.0, player.y + move_y * rules.speed * dt))


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


def _match_for(world: WorldState, player: PlayerState | None) -> Match | None:
    if player is None or not player.match_id:
        return None
    return world.matches.get(player.match_id)


def _combatants(world: WorldState, match: Match) -> list[PlayerState]:
    return [world.players[player_id] for player_id in match.player_ids if player_id in world.players]


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
    }


def _match_payload(world: WorldState, match: Match, player: PlayerState) -> dict:
    return {
        "phase": match.phase,
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
                "x": round(other.x, 2),
                "y": round(other.y, 2),
                "health": round(other.health, 1),
                "status": other.status,
                "kills": other.kills,
                "weapon": other.weapon,
                "bot": other.is_bot,
            }
            for other in _combatants(world, match)
        ],
        "loot": [
            {
                "loot_id": node.loot_id,
                "x": round(node.x, 2),
                "y": round(node.y, 2),
                "item_id": node.item_id,
                "quantity": node.quantity,
            }
            for node in match.loot
            if not node.taken
        ],
        "self": {
            "weapon": player.weapon,
            "mag": player.mag,
            "reload": round(player.reload_left, 2),
            "on_plane": player.on_plane,
            "inventory": dict(player.inventory),
        },
        "events": list(match.events),
    }
