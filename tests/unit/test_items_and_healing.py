"""Weapon slots, timed healing, attachments, kill feed, supplies and nearby loot.

Independent design numbers, not original Rules of Survival values.
"""

from app.game.engine import GameEngine
from app.game.items import HEAL_TIME, LOOT_TABLE, WEAPONS, can_attach
from app.game.rules import MatchRules
from app.game.simulate import snapshot
from app.game.state import LootNode


def _rules(**overrides) -> MatchRules:
    values = dict(bot_fill=0, queue_wait=0, countdown=0, drop_time=0, phase_duration=100, result_time=100, loot_count=0)
    values.update(overrides)
    return MatchRules(**values)


async def _start(engine: GameEngine, *player_ids: str):
    for player_id in player_ids:
        await engine.join_queue(player_id)
    await engine.step(0.05)
    return next(iter(engine.world.matches.values()))


def _place(match, player, item_id: str, quantity: int = 1) -> str:
    node = LootNode(loot_id=f"t:{item_id}:{len(match.loot)}", x=player.x, y=player.y, item_id=item_id, quantity=quantity)
    match.loot.append(node)
    return node.loot_id


async def _pick(engine, match, player_id: str, item_id: str, quantity: int = 1):
    player = engine.world.players[player_id]
    return await engine.perform(player_id, "pickup", _place(match, player, item_id, quantity), None)


async def test_loadout_has_two_primary_weapons_and_one_pistol():
    engine = GameEngine(_rules())
    match = await _start(engine, "human")
    ok, _ = await _pick(engine, match, "human", "rifle")
    assert ok
    ok, _ = await _pick(engine, match, "human", "awm")
    assert ok
    ok, detail = await _pick(engine, match, "human", "vector")
    assert not ok and detail == "Weapon slots full"
    ok, detail = await _pick(engine, match, "human", "desert_eagle")
    assert not ok and detail == "Weapon slots full"  # the starter pistol holds the pistol slot
    await engine.perform("human", "discard", None, "pistol")
    ok, _ = await _pick(engine, match, "human", "desert_eagle")
    assert ok
    slots = snapshot(engine.world, engine.world.players["human"], engine.rules)["match"]["self"]["slots"]
    assert slots == {"primary": ["rifle", "awm"], "pistol": ["desert_eagle"]}


async def test_picking_up_a_primary_weapon_switches_from_the_pistol():
    engine = GameEngine(_rules())
    match = await _start(engine, "human")
    player = engine.world.players["human"]
    assert player.weapon == "pistol"
    await _pick(engine, match, "human", "rifle")
    assert player.weapon == "rifle"
    await _pick(engine, match, "human", "awm")
    assert player.weapon == "rifle"  # a second primary does not steal the hands


async def test_healing_takes_time_and_can_be_cancelled():
    engine = GameEngine(_rules())
    match = await _start(engine, "human")
    player = engine.world.players["human"]
    player.inventory["medkit"] = 2
    player.health = 30
    ok, detail = await engine.perform("human", "use", None, "medkit")
    assert ok and detail == "Using medkit"
    await engine.step(1.0)
    view = snapshot(engine.world, player, engine.rules)["match"]["self"]
    assert view["healing"] == "medkit" and 2.1 < view["heal_left"] < 2.3
    assert player.health == 30
    ok, detail = await engine.perform("human", "use", None, "medkit")
    assert ok and detail == "Heal cancelled"
    assert player.inventory["medkit"] == 2
    await engine.perform("human", "use", None, "medkit")
    await engine.step(HEAL_TIME["medkit"] + 0.1)
    assert (player.health, player.inventory["medkit"], player.healing) == (90, 1, None)
    assert match.phase == "playing"


async def test_being_hit_or_shooting_cancels_healing():
    engine = GameEngine(_rules())
    await _start(engine, "alpha", "bravo")
    alpha, bravo = engine.world.players["alpha"], engine.world.players["bravo"]
    bravo.x, bravo.y, alpha.x, alpha.y = 100, 100, 90, 100
    alpha.aim_x, alpha.aim_y = 1.0, 0.0
    bravo.inventory["bandage"] = 1
    bravo.health = 50
    await engine.perform("bravo", "use", None, "bandage")
    assert bravo.healing == "bandage"
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert detail == "Hit" and bravo.healing is None
    alpha.inventory["bandage"] = 1
    alpha.health = 50
    await engine.perform("alpha", "use", None, "bandage")
    await engine.step(0.4)
    await engine.perform("alpha", "shoot", None, None)
    assert alpha.healing is None


async def test_scope_and_extended_mag_change_range_and_magazine():
    engine = GameEngine(_rules())
    match = await _start(engine, "human")
    player = engine.world.players["human"]
    await _pick(engine, match, "human", "rifle")
    await engine.perform("human", "equip", None, "rifle")
    player.inventory.update({"scope_4x": 2, "ext_mag": 1, "medium": 60})
    assert can_attach("ext_mag", "rifle") and not can_attach("ext_mag", "awm") and not can_attach("scope_4x", "pistol")
    ok, detail = await engine.perform("human", "attach", None, "scope_4x")
    assert ok and detail == "Fitted scope_4x"
    ok, detail = await engine.perform("human", "attach", None, "scope_4x")
    assert not ok and detail == "Already fitted"
    ok, _ = await engine.perform("human", "attach", None, "ext_mag")
    assert ok
    view = snapshot(engine.world, player, engine.rules)["match"]["self"]
    assert view["attachments"] == ["scope_4x", "ext_mag"] and view["mag_size"] == 40
    player.mag = 0
    await engine.perform("human", "reload", None, None)
    await engine.step(WEAPONS["rifle"]["reload"] + 0.1)
    assert player.mag == 40
    ok, detail = await engine.perform("human", "attach", None, "ext_mag")
    assert not ok and detail == "Item not carried"


async def test_scope_extends_the_shot_range():
    engine = GameEngine(_rules())
    await _start(engine, "alpha", "bravo")
    alpha, bravo = engine.world.players["alpha"], engine.world.players["bravo"]
    alpha.inventory.update({"rifle": 1, "scope_4x": 1})
    alpha.mags["rifle"] = 30
    await engine.perform("alpha", "equip", None, "rifle")
    alpha.x, alpha.y, bravo.x, bravo.y = 10, 100, 85, 100  # 75 away, rifle range is 70
    alpha.aim_x, alpha.aim_y = 1.0, 0.0
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert detail == "Missed"
    await engine.step(0.2)
    await engine.perform("alpha", "attach", None, "scope_4x")
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert detail == "Hit"


async def test_kill_feed_names_the_weapon_and_supplies_count_pickups():
    engine = GameEngine(_rules())
    match = await _start(engine, "alpha", "bravo")
    alpha, bravo = engine.world.players["alpha"], engine.world.players["bravo"]
    await _pick(engine, match, "alpha", "bandage")
    await _pick(engine, match, "alpha", "armor_1")
    assert alpha.supplies == 2
    bravo.health = 10
    alpha.x, alpha.y, bravo.x, bravo.y = 90, 100, 100, 100
    alpha.aim_x, alpha.aim_y = 1.0, 0.0
    await engine.perform("alpha", "shoot", None, None)
    kill = next(event for event in match.events if event["kind"] == "elimination")
    assert (kill["weapon"], kill["killer_id"], kill["cause"]) == ("pistol", "alpha", "shot")
    hit = next(event for event in match.events if event["kind"] == "hit")
    assert hit["weapon"] == "pistol"
    assert snapshot(engine.world, alpha, engine.rules)["match"]["self"]["supplies"] == 2


async def test_nearby_lists_only_loot_within_reach():
    engine = GameEngine(_rules())
    match = await _start(engine, "human")
    player = engine.world.players["human"]
    near = _place(match, player, "scope_4x")
    match.loot.append(LootNode(loot_id="far", x=player.x + 50, y=player.y, item_id="medkit", quantity=1))
    nearby = snapshot(engine.world, player, engine.rules)["match"]["self"]["nearby"]
    assert [row["loot_id"] for row in nearby] == [near]


async def test_discarding_a_fitted_weapon_returns_its_attachments_and_death_drops_them():
    engine = GameEngine(_rules())
    match = await _start(engine, "alpha", "bravo")
    bravo = engine.world.players["bravo"]
    bravo.inventory.update({"vector": 1, "ext_mag": 1})
    await engine.perform("bravo", "equip", None, "vector")
    ok, _ = await engine.perform("bravo", "attach", None, "ext_mag")
    assert ok
    ok, _ = await engine.perform("bravo", "discard", None, "vector")
    assert ok and bravo.inventory.get("ext_mag") == 1 and bravo.attachments == {}
    bravo.inventory.update({"m14ebr": 1, "scope_4x": 1})
    await engine.perform("bravo", "equip", None, "m14ebr")
    await engine.perform("bravo", "attach", None, "scope_4x")
    from app.game.simulate import _eliminate

    _eliminate(engine.world, match, bravo, "alpha", "shot")
    crate = {node.item_id for node in match.loot if node.crate_id and not node.taken}
    assert {"scope_4x", "ext_mag", "m14ebr"} <= crate


def test_new_items_are_in_the_loot_table():
    ids = {item for item, _qty, _weight in LOOT_TABLE}
    assert {"awm", "m14ebr", "aa12", "vector", "desert_eagle", "first_aid", "scope_4x", "ext_mag"} <= ids
    assert HEAL_TIME["first_aid"] > HEAL_TIME["medkit"] > HEAL_TIME["bandage"]
