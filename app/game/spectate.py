"""Operator view of running matches: everything on the map, nothing hidden by fog or team.

Unlike the per-player `snapshot`, a spectator frame has no "self" block and carries every
combatant's position, aim, health and vehicle, for the admin live map.
"""

from app.game.rules import MatchRules
from app.game.simulate import _combatants
from app.game.state import Match, WorldState


def spectator_frame(world: WorldState, match: Match, rules: MatchRules, *, static: bool) -> dict:
    players = _combatants(world, match)
    frame = {
        "match_id": match.match_id,
        "phase": match.phase,
        "clock": round(match.clock, 2),
        "map_size": rules.map_size,
        "alive": sum(1 for player in players if player.status == "alive"),
        "total": len(players),
        "winner_id": match.winner_id,
        "zone": {
            "x": round(match.zone_x, 2),
            "y": round(match.zone_y, 2),
            "radius": round(match.zone_radius, 2),
            "next_x": round(match.next_x, 2),
            "next_y": round(match.next_y, 2),
            "next_radius": round(match.next_radius, 2),
            "index": match.zone_index,
            "dps": match.zone_dps,
        },
        "players": [
            {
                "player_id": player.player_id,
                "nickname": player.nickname,
                "x": round(player.x, 2),
                "y": round(player.y, 2),
                "aim_x": round(player.aim_x, 3),
                "aim_y": round(player.aim_y, 3),
                "health": round(player.health, 1),
                "status": player.status,
                "kills": player.kills,
                "weapon": player.weapon,
                "vehicle": player.vehicle,
                "on_plane": player.on_plane,
                "bot": player.is_bot,
                "connected": player.connected,
            }
            for player in players
        ],
        "vehicles": [
            {"vehicle_id": node.vehicle_id, "kind": node.kind, "x": round(node.x, 2), "y": round(node.y, 2), "occupant": node.occupant}
            for node in match.vehicles
        ],
        "loot": [[round(node.x, 1), round(node.y, 1)] for node in match.loot if not node.taken],
    }
    if static:
        # Cover does not move; send it on the first frame of a watch only.
        frame["blockers"] = [
            {
                "kind": blocker.kind,
                "name": blocker.name,
                "minimum_x": round(blocker.minimum_x, 2),
                "minimum_y": round(blocker.minimum_y, 2),
                "maximum_x": round(blocker.maximum_x, 2),
                "maximum_y": round(blocker.maximum_y, 2),
            }
            for blocker in match.blockers
        ]
    return frame
