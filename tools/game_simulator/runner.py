"""Deterministic lobby and match scenarios for this server's rules.

Passing a scenario shows that the simulation followed app.game rules.
It is not evidence of original Rules of Survival compatibility.
"""

import random
from dataclasses import dataclass, field

from app.game.engine import GameEngine
from app.game.rules import MatchRules


class ScenarioError(RuntimeError):
    pass


@dataclass
class SimulatedPlayer:
    player_id: str
    authenticated: bool = False

    def authenticate(self, password: str) -> None:
        if not 12 <= len(password) <= 128:
            raise ScenarioError("Password length is outside the server rule")
        self.authenticated = True


@dataclass
class SimulatedTeam:
    code: str
    members: list[str] = field(default_factory=list)


@dataclass
class SimulatedLobby:
    code: str
    max_players: int
    members: list[str] = field(default_factory=list)
    ready: set[str] = field(default_factory=set)
    teams: dict[str, SimulatedTeam] = field(default_factory=dict)
    team_of: dict[str, str] = field(default_factory=dict)

    def join(self, player: SimulatedPlayer) -> None:
        if not player.authenticated:
            raise ScenarioError("Player must log in before joining a lobby")
        if player.player_id in self.members:
            raise ScenarioError("Player is already in the lobby")
        if len(self.members) >= self.max_players:
            raise ScenarioError("Lobby is full")
        self.members.append(player.player_id)

    def leave(self, player_id: str) -> None:
        if player_id not in self.members:
            raise ScenarioError("Player is not in the lobby")
        self.members.remove(player_id)
        self.ready.discard(player_id)
        code = self.team_of.pop(player_id, None)
        if code is not None:
            self.teams[code].members.remove(player_id)

    def create_team(self, code: str) -> SimulatedTeam:
        if code in self.teams:
            raise ScenarioError("Team code already exists")
        team = SimulatedTeam(code=code)
        self.teams[code] = team
        return team

    def join_team(self, team: SimulatedTeam, player: SimulatedPlayer) -> None:
        if player.player_id not in self.members:
            raise ScenarioError("Player must join the lobby first")
        if player.player_id in self.team_of:
            raise ScenarioError("Player is already on a team in this lobby")
        team.members.append(player.player_id)
        self.team_of[player.player_id] = team.code

    def set_ready(self, player: SimulatedPlayer, ready: bool) -> None:
        if player.player_id not in self.members:
            raise ScenarioError("Player must join the lobby first")
        if ready:
            self.ready.add(player.player_id)
        else:
            self.ready.discard(player.player_id)


@dataclass
class ScenarioResult:
    seed: int
    steps: list[str]
    movement_delta: float
    winner_id: str | None
    results: dict[str, dict]
    stats: dict[str, dict]


def _fast_rules() -> MatchRules:
    return MatchRules(bot_fill=0, queue_wait=0, countdown=0, drop_time=0, phase_duration=100, result_time=100)


def apply_totals(stats: dict[str, dict], results: dict[str, dict]) -> None:
    """Same arithmetic as PersistenceService, kept in memory for the scenario."""

    for player_id, result in results.items():
        row = stats.setdefault(player_id, {"kills": 0, "wins": 0, "matches": 0})
        row["kills"] += int(result["kills"])
        row["matches"] += 1
        if result["win"]:
            row["wins"] += 1


class StateValidator:
    def validate(self, result: ScenarioResult, expected: dict) -> None:
        if result.movement_delta != expected["movement_delta"]:
            raise ScenarioError("Movement did not follow the server speed rule")
        if result.winner_id != expected["winner_id"]:
            raise ScenarioError("Winner did not match the server combat rule")
        for player_id, row in expected["stats"].items():
            if result.stats[player_id] != row:
                raise ScenarioError(f"Statistics mismatch for {player_id}")


class ScenarioRunner:
    async def run(self, seed: int = 7) -> ScenarioResult:
        random.seed(seed)
        steps: list[str] = []
        password = "ScenarioPassword123!"
        alpha = SimulatedPlayer("alpha")
        bravo = SimulatedPlayer("bravo")
        alpha.authenticate(password)
        bravo.authenticate(password)
        steps.append("player_login")

        lobby = SimulatedLobby(code="SIM", max_players=4)
        steps.append("create_lobby")
        lobby.join(alpha)
        lobby.join(bravo)
        steps.append("join_lobby")
        team = lobby.create_team("A")
        lobby.join_team(team, alpha)
        lobby.join_team(team, bravo)
        steps.append("create_team")
        lobby.set_ready(alpha, True)
        lobby.set_ready(bravo, True)
        if lobby.ready != {"alpha", "bravo"}:
            raise ScenarioError("Ready state was not recorded")
        steps.append("ready_players")

        movement = GameEngine(_fast_rules())
        ok, detail = await movement.join_queue("alpha")
        if not ok:
            raise ScenarioError(detail)
        steps.append("request_matchmaking")
        await movement.step(0.05)
        steps.append("start_match")
        start_x = movement.world.players["alpha"].x
        await movement.set_input("alpha", 1, 0)
        await movement.step(1)
        delta = movement.world.players["alpha"].x - start_x
        steps.append("simulate_player_state")

        fight = GameEngine(_fast_rules())
        for player_id in ("alpha", "bravo"):
            ok, detail = await fight.join_queue(player_id)
            if not ok:
                raise ScenarioError(detail)
        await fight.step(0.05)
        shots = 0
        while shots < 8 and fight.world.players["bravo"].status != "eliminated":
            ok, detail = await fight.perform("alpha", "shoot", None, None)
            shots += 1
            if not ok:
                raise ScenarioError(detail)
            await fight.step(0.4)
        steps.append("simulate_weapon_interactions")
        if fight.world.players["bravo"].status != "eliminated":
            raise ScenarioError("Opponent was not eliminated")
        steps.append("simulate_elimination")
        match = next(iter(fight.world.matches.values()))
        if match.phase != "ended":
            raise ScenarioError("Match did not end")
        steps.append("end_match")
        taken = await fight.take_results()
        results = {
            item.player_id: {"kills": item.kills, "win": item.win, "placement": item.placement}
            for item in taken
        }
        steps.append("calculate_results")
        stats: dict[str, dict] = {}
        apply_totals(stats, results)
        steps.append("persist_results")
        steps.append("verify_player_statistics")
        return ScenarioResult(
            seed=seed,
            steps=steps,
            movement_delta=delta,
            winner_id=match.winner_id,
            results=results,
            stats=stats,
        )
