"""Attach shared PlayerRuntimeState to MatchSession and drive lifecycle hooks (P0 player seam).

Does not send Mercury bytes. Does **not** start its own MatchTimeline — hooks attach to
the space/plane timeline after other modules load (deferred register).
"""

from __future__ import annotations

from battle import player_entity as pe


class PlayerRuntimeModule:
    """Owns the human player record and combatant registry for one session."""

    def __init__(self, session):
        self.session = session
        if getattr(session, "player", None) is None:
            session.player = pe.new_human_player()
        if not hasattr(session, "combatants"):
            session.combatants = {}
        session.combatants[session.player.player_id] = session.player
        session.player.reset_battle_loadout()
        session.player.lifecycle = pe.LIFECYCLE_MATCH_LOADING
        self._hooks_attached = False

    def register_bot(self, runtime: pe.PlayerRuntimeState) -> None:
        self.session.combatants[runtime.player_id] = runtime

    def attach_timeline_hooks(self) -> None:
        if self._hooks_attached or self.session.closed:
            return
        timeline = self._shared_timeline()
        if timeline is None:
            return
        timeline.on_phase("boarding", self._on_boarding)
        timeline.on_phase("flight", self._on_flight)
        timeline.on_phase("play", self._on_play)
        self._hooks_attached = True
        self.session.player_runtime_module = self
        self.session._log(
            "      [BATTLE] player_runtime id=%s nick=%s (timeline hooks)"
            % (self.session.player.player_id, self.session.player.nickname)
        )

    def _shared_timeline(self):
        for attr in (
            "space_module",
            "plane_module",
            "jump_module",
            "zone_module",
            "props_module",
        ):
            mod = getattr(self.session, attr, None)
            if mod is None:
                continue
            tl = getattr(mod, "timeline", None)
            if tl is not None:
                return tl
        return None

    def _on_boarding(self, _phase):
        if self.session.closed:
            return
        self.session.player.lifecycle = pe.LIFECYCLE_PREP

    def _on_flight(self, _phase):
        if self.session.closed:
            return
        self.session.player.lifecycle = pe.LIFECYCLE_AIRCRAFT

    def _on_play(self, _phase):
        if self.session.closed:
            return
        jump = getattr(self.session, "jump_module", None)
        if jump is not None and getattr(jump, "landed", False):
            self.session.player.lifecycle = pe.LIFECYCLE_GROUND
        elif jump is not None and getattr(jump, "off_plane", False):
            self.session.player.lifecycle = pe.LIFECYCLE_PARACHUTE
        else:
            self.session.player.lifecycle = pe.LIFECYCLE_GROUND


def register(session):
    mod = PlayerRuntimeModule(session)
    session.schedule(0.0, _deferred_attach, mod)
    session.schedule(0.05, _deferred_attach, mod)
    return mod


def _deferred_attach(mod):
    if mod.session.closed or mod._hooks_attached:
        return
    mod.attach_timeline_hooks()