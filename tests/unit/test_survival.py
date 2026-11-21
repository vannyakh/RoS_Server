"""Survival flow: parachute, gear, death crate, dropped items, stack room, results table.

These numbers are this server's independent design, not original Rules of Survival values.
"""

from app.game.engine import GameEngine
from app.game.items import MAX_STACK, damage_after_gear, gear_of
from app.game.rules import MatchRules
from app.game.simulate import snapshot
from app.game.state import LootNode


def _rules(**overrides) -> MatchRules:
    values = dict(bot_fill=0, queue_wait=0, countdown=0, drop_time=0, phase_duration=100, result_time=100)
    values.update(overrides)
    return MatchRules(**values)


async def _start(engine: GameEngine, *player_ids: str):
    for player_id in player_ids:
        ok, _detail = await engine.join_queue(player_id)
        assert ok
    await engine.step(0.05)
    return next(iter(engine.world.matches.values()))


def _place(match, player, item_id: str, quantity: int = 1) -> LootNode:
    node = LootNode(loot_id=f"test:{item_id}:{len(match.loot)}", x=player.x, y=player.y, item_id=item_id, quantity=quantity)
    match.loot.append(node)
    return node


async def _kill(engine: GameEngine, shooter: str, target: str) -> None:
    for _ in range(20):
        ok, detail = await engine.perform(shooter, "shoot", None, None)
        if detail == "Eliminated":
            return
        if detail == "Reload":
            await engine.perform(shooter, "reload", None, None)
            await engine.step(2.0)
        await engine.step(0.4)
    raise AssertionError(f"{target} survived")


async def test_jump_starts_a_parachute_descent_then_lands():
    engine = GameEngine(_rules(drop_time=20, fall_speed=10, glide_speed=8, loot_count=0))
    match = await _start(engine, "human")
    await engine.step(0.05)  # countdown 0 -> dropping
    assert match.phase == "dropping"
    ok, detail = await engine.perform("human", "jump", None, None)
    assert ok and detail == "Jumped"
    player = engine.world.players["human"]
    assert (player.on_plane, player.status, player.z) == (False, "dropping", 40.0)
    ok, detail = await engine.perform("human", "pickup", "x", None)
    assert not ok and detail == "Still parachuting"
    start_y = player.y
    await engine.set_input("human", 0, 1)
    await engine.step(1.0)
    assert player.z == 30.0
    assert player.y == start_y + 8
    for _ in range(4):
        await engine.step(1.0)
    assert (player.status, player.z) == ("alive", 0.0)


async def test_drop_phase_end_lands_players_still_in_the_air():
    engine = GameEngine(_rules(drop_time=2, fall_speed=1, loot_count=0))
    match = await _start(engine, "alpha", "bravo")
    await engine.step(0.05)
    await engine.perform("alpha", "jump", None, None)
    await engine.step(2.0)
    assert match.phase == "playing"
    assert all(engine.world.players[pid].status == "alive" for pid in ("alpha", "bravo"))


async def test_armor_and_helmet_reduce_damage():
    engine = GameEngine(_rules())
    match = await _start(engine, "alpha", "bravo")
    bravo = engine.world.players["bravo"]
    ok, detail = await engine.perform("bravo", "pickup", _place(match, bravo, "armor_2").loot_id, None)
    assert ok and detail == "Equipped armor_2"
    ok, _ = await engine.perform("bravo", "pickup", _place(match, bravo, "helmet_1").loot_id, None)
    assert ok and (bravo.armor, bravo.helmet) == (2, 1)
    alpha = engine.world.players["alpha"]
    alpha.aim_x, alpha.aim_y = bravo.x - alpha.x, bravo.y - alpha.y
    ok, detail = await engine.perform("alpha", "shoot", None, None)
    assert ok and detail == "Hit"
    expected = damage_after_gear(22.0, 2, 1)
    assert round(bravo.health, 3) == round(100 - expected, 3)
    assert round(alpha.damage_dealt, 3) == round(expected, 3)


async def test_better_gear_swaps_and_drops_the_old_piece():
    engine = GameEngine(_rules())
    match = await _start(engine, "human")
    player = engine.world.players["human"]
    await engine.perform("human", "pickup", _place(match, player, "armor_1").loot_id, None)
    ok, detail = await engine.perform("human", "pickup", _place(match, player, "armor_1").loot_id, None)
    assert not ok and "Already wearing" in detail
    ok, _ = await engine.perform("human", "pickup", _place(match, player, "armor_3").loot_id, None)
    assert ok and player.armor == 3
    swapped = [node for node in match.loot if ":drop:" in node.loot_id and not node.taken]
    assert [(node.item_id, node.x, node.y) for node in swapped] == [("armor_1", player.x, player.y)]


async def test_eliminated_player_leaves_a_crate_with_inventory_and_gear():
    engine = GameEngine(_rules())
    match = await _start(engine, "alpha", "bravo", "charlie")
    bravo = engine.world.players["bravo"]
    await engine.perform("bravo", "pickup", _place(match, bravo, "helmet_2").loot_id, None)
    bravo.inventory["bandage"] = 3
    alpha = engine.world.players["alpha"]
    alpha.aim_x, alpha.aim_y = bravo.x - alpha.x, bravo.y - alpha.y
    await _kill(engine, "alpha", "bravo")
    assert bravo.status == "eliminated"
    crate = {node.item_id: node.quantity for node in match.loot if node.crate_id and not node.taken}
    assert crate == {"pistol": 1, "light": 24, "bandage": 3, "helmet_2": 1}
    assert bravo.inventory == {} and bravo.helmet == 0
    view = snapshot(engine.world, alpha, engine.rules)["match"]
    assert any(node["crate_id"] and node["item_id"] == "helmet_2" for node in view["loot"])

    # The killer can walk over and loot it.
    alpha.x, alpha.y = bravo.x, bravo.y
    helmet = next(node for node in match.loot if node.crate_id and node.item_id == "helmet_2")
    ok, _ = await engine.perform("alpha", "pickup", helmet.loot_id, None)
    assert ok and alpha.helmet == 2


async def test_discarded_item_stays_on_the_ground():
    engine = GameEngine(_rules())
    match = await _start(engine, "human")
    player = engine.world.players["human"]
    ok, _ = await engine.perform("human", "discard", None, "pistol")
    assert ok and player.weapon is None and "pistol" not in player.mags
    node = next(node for node in match.loot if ":drop:" in node.loot_id and node.item_id == "pistol")
    ok, _ = await engine.perform("human", "pickup", node.loot_id, None)
    assert ok and player.weapon == "pistol"


async def test_pickup_fills_the_stack_and_leaves_the_rest():
    engine = GameEngine(_rules())
    match = await _start(engine, "human")
    player = engine.world.players["human"]
    player.inventory["light"] = MAX_STACK - 10
    node = _place(match, player, "light", 30)
    ok, _ = await engine.perform("human", "pickup", node.loot_id, None)
    assert ok and player.inventory["light"] == MAX_STACK
    assert (node.quantity, node.taken) == (20, False)
    ok, detail = await engine.perform("human", "pickup", node.loot_id, None)
    assert not ok and detail == "Stack full"
    await engine.perform("human", "pickup", _place(match, player, "backpack_1").loot_id, None)
    ok, _ = await engine.perform("human", "pickup", node.loot_id, None)
    assert ok and player.inventory["light"] == MAX_STACK + 20 and node.taken


async def test_requeued_player_is_not_ticked_by_the_old_match():
    engine = GameEngine(_rules())
    first = await _start(engine, "alpha", "bravo", "charlie")
    alpha, bravo = engine.world.players["alpha"], engine.world.players["bravo"]
    alpha.aim_x, alpha.aim_y = bravo.x - alpha.x, bravo.y - alpha.y
    await _kill(engine, "alpha", "bravo")
    assert first.phase == "playing"

    ok, _ = await engine.join_queue("bravo")
    assert ok
    await engine.step(0.05)
    second = next(match for match in engine.world.matches.values() if match is not first)
    assert bravo.match_id == second.match_id and bravo.status == "alive"
    start = bravo.x
    await engine.set_input("bravo", 1, 0)
    await engine.step(1.0)
    assert bravo.x == start + 5  # one match moved bravo, not two

    # The old match finishes with the right kill counts and placements.
    charlie = engine.world.players["charlie"]
    alpha.aim_x, alpha.aim_y = charlie.x - alpha.x, charlie.y - alpha.y
    await _kill(engine, "alpha", "charlie")
    assert first.phase == "ended" and first.winner_id == "alpha"
    results = {r.player_id: r for r in await engine.take_results()}
    assert (results["alpha"].kills, results["alpha"].placement) == (2, 1)
    assert results["charlie"].placement == 2
    assert results["bravo"].placement == 3


async def test_ended_match_snapshot_carries_the_results_table():
    engine = GameEngine(_rules())
    match = await _start(engine, "alpha", "bravo")
    alpha, bravo = engine.world.players["alpha"], engine.world.players["bravo"]
    alpha.aim_x, alpha.aim_y = bravo.x - alpha.x, bravo.y - alpha.y
    await engine.set_input("alpha", 0, 1)
    await engine.step(1.0)
    await engine.set_input("alpha", 0, 0)
    alpha.aim_x, alpha.aim_y = bravo.x - alpha.x, bravo.y - alpha.y
    await _kill(engine, "alpha", "bravo")
    assert match.phase == "ended"
    view = snapshot(engine.world, alpha, engine.rules)["match"]
    table = view["results"]
    assert [row["player_id"] for row in table] == ["alpha", "bravo"]
    assert table[0]["kills"] == 1 and table[0]["distance"] == 5.0
    assert table[0]["damage"] == 100.0
    assert view["self"]["distance"] == 5.0


def test_gear_ids_parse():
    assert gear_of("armor_3") == ("armor", 3)
    assert gear_of("backpack_1") == ("backpack", 1)
    assert gear_of("armor_9") is None
    assert gear_of("medkit") is None
