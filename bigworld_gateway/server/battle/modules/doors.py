"""BattleGroundSpace door replies (RO-067).

Loads ``battle/data/doors.json`` (RO-075), answers ``openElement`` / ``closeElement`` with
``onElementOpen`` / ``onElementClose``, keeps per-match door state, and optionally mirrors
``openedElements`` (ALL_CLIENTS) for late joiners when enabled in data or ``DOORS_OPENED_ELEMENTS=1``.

Vehicle doors and ElevatorCage are out of scope (RO-074).
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path

import battle_flow as bf
from battle import requests as reqs

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DOORS_PATH = DATA_DIR / "doors.json"

DOOR_METHODS = frozenset({"openElement", "closeElement"})


def load_doors_config(path=None):
    root = Path(path) if path is not None else DEFAULT_DOORS_PATH
    cfg = {
        "map_id": 700,
        "space_entity_id": int(os.environ.get("SPACE_ENTITY_ID", "20001")),
        "default_open_state": 1,
        "default_close_state": 0,
        "opened_elements_on_reply": False,
        "unknown_elem_policy": "echo_and_log_once",
        "doors": [],
    }
    if root.is_file():
        raw = json.loads(root.read_text(encoding="utf-8"))
        for key in cfg:
            if key in raw:
                cfg[key] = raw[key]
    if "BATTLE_MAP" in os.environ:
        cfg["map_id"] = int(os.environ["BATTLE_MAP"])
    if "DOORS_OPENED_ELEMENTS" in os.environ:
        cfg["opened_elements_on_reply"] = os.environ["DOORS_OPENED_ELEMENTS"].lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    return cfg


def encode_opened_elements(opened):
    """ARRAY<DTS_ELEMENT> wire bytes: count u32 then (elemID i32, state i8) rows with state > 0."""
    rows = sorted((int(eid), int(st)) for eid, st in opened.items() if int(st) > 0)
    body = struct.pack("<I", len(rows))
    for eid, st in rows:
        body += struct.pack("<ib", eid, st & 0xFF)
    return body


class DoorsModule:
    """Owns building door state for one MatchSession."""

    def __init__(self, session, *, doors_data_path=None):
        self.session = session
        self.cfg = load_doors_config(doors_data_path)
        self.by_id = {int(row["elem_id"]): row for row in self.cfg.get("doors") or []}
        self.known_ids = frozenset(self.by_id)
        self.opened = {}
        self._unknown_logged = set()
        self.space_id = int(getattr(session, "space_id", None) or self.cfg.get("space_entity_id") or bf.SPACE_ID)
        self.default_open = int(self.cfg.get("default_open_state", 1))
        self.default_close = int(self.cfg.get("default_close_state", 0))

    def start(self):
        if self.session.closed:
            return
        self.session.on_inbound(self._is_door_request, self._on_door_request)
        self.session.doors_module = self
        self.session._log(
            "      [BATTLE] doors module started (%d table entries, openedElements=%s)"
            % (len(self.by_id), self._mirror_opened_elements())
        )

    def _mirror_opened_elements(self):
        return bool(self.cfg.get("opened_elements_on_reply"))

    def opened_values_for_create(self):
        """Fragment for ``create_entity(..., values=)`` when the space is recreated."""
        if not self.opened or not self._mirror_opened_elements():
            return {}
        return {"openedElements": encode_opened_elements(self.opened)}

    def _is_door_request(self, msgid, payload):
        if not (reqs.MSGID_MIN <= int(msgid) <= reqs.MSGID_MAX):
            return False
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        return (
            call is not None
            and call.entity == "BattleGroundSpace"
            and call.method in DOOR_METHODS
        )

    def _on_door_request(self, msgid, payload):
        call = reqs.decode(int(msgid), payload or b"", log=self.session._log)
        if call is None or call.method not in DOOR_METHODS:
            return b""
        if int(call.entity_id) != self.space_id:
            self.session._log(
                "      [BATTLE] doors reject %s on eid=%s (expected space %s)"
                % (call.method, call.entity_id, self.space_id)
            )
            return b""
        if call.method == "openElement":
            return self._handle_open(call.args)
        return self._handle_close(call.args)

    def _valid_elem_id(self, elem_id):
        if elem_id < 0 or elem_id > 0x7FFFFFFF:
            self.session._log("      [BATTLE] doors reject elem_id out of range: %s" % elem_id)
            return False
        return True

    def _handle_open(self, args):
        if len(args) < 5:
            self.session._log("      [BATTLE] doors reject openElement: short args")
            return b""
        elem_id, state = struct.unpack("<ib", args[:5])
        if not self._valid_elem_id(elem_id):
            return b""
        door = self.by_id.get(elem_id)
        if door is not None:
            allowed = door.get("open_states") or [self.default_open]
            if int(state) not in {int(s) for s in allowed}:
                self.session._log(
                    "      [BATTLE] doors reject openElement elem=%s state=%s (allowed %s)"
                    % (elem_id, state, allowed)
                )
                return b""
        elif self.cfg.get("unknown_elem_policy") == "echo_and_log_once":
            if elem_id not in self._unknown_logged:
                self._unknown_logged.add(elem_id)
                self.session._log("      [BATTLE] doors unknown elem_id=%s (echo open)" % elem_id)
        else:
            self.session._log("      [BATTLE] doors reject unknown elem_id=%s" % elem_id)
            return b""

        self.opened[int(elem_id)] = int(state)
        bodies = [
            bf.client_call(
                "BattleGroundSpace",
                "onElementOpen",
                self.space_id,
                struct.pack("<ib", int(elem_id), int(state)),
            )
        ]
        self._append_pair_opens(int(elem_id), int(state), bodies)
        self._maybe_append_opened_elements(bodies)
        for chunk in bodies:
            self.session.enqueue(chunk)
        self.session._log("      [BATTLE] doors open elem=%s state=%s" % (elem_id, state))
        return b""

    def _append_pair_opens(self, elem_id, state, bodies):
        door = self.by_id.get(elem_id)
        if not door:
            return
        for pid in door.get("pair_elem_ids") or []:
            leaf_id = int(pid)
            leaf = self.by_id.get(leaf_id)
            leaf_state = int(state)
            if leaf:
                leaf_allowed = {int(s) for s in (leaf.get("open_states") or [self.default_open])}
                if leaf_state not in leaf_allowed:
                    leaf_state = int((leaf.get("open_states") or [self.default_open])[0])
            self.opened[leaf_id] = leaf_state
            bodies.append(
                bf.client_call(
                    "BattleGroundSpace",
                    "onElementOpen",
                    self.space_id,
                    struct.pack("<ib", leaf_id, leaf_state),
                )
            )

    def _handle_close(self, args):
        if len(args) < 4:
            self.session._log("      [BATTLE] doors reject closeElement: short args")
            return b""
        elem_id = struct.unpack("<i", args[:4])[0]
        if not self._valid_elem_id(elem_id):
            return b""
        door = self.by_id.get(elem_id)
        if door is None and self.cfg.get("unknown_elem_policy") == "echo_and_log_once":
            if elem_id not in self._unknown_logged:
                self._unknown_logged.add(elem_id)
                self.session._log("      [BATTLE] doors unknown elem_id=%s (echo close)" % elem_id)
        elif door is None:
            self.session._log("      [BATTLE] doors reject close unknown elem_id=%s" % elem_id)
            return b""

        close_state = int((door or {}).get("close_state", self.default_close))
        self.opened[int(elem_id)] = close_state
        bodies = [
            bf.client_call(
                "BattleGroundSpace",
                "onElementClose",
                self.space_id,
                struct.pack("<i", int(elem_id)),
            )
        ]
        self._append_pair_closes(int(elem_id), bodies)
        self._maybe_append_opened_elements(bodies)
        for chunk in bodies:
            self.session.enqueue(chunk)
        self.session._log("      [BATTLE] doors close elem=%s" % elem_id)
        return b""

    def _append_pair_closes(self, elem_id, bodies):
        door = self.by_id.get(elem_id)
        if not door:
            return
        for pid in door.get("pair_elem_ids") or []:
            leaf_id = int(pid)
            leaf = self.by_id.get(leaf_id)
            close_state = int((leaf or {}).get("close_state", self.default_close))
            self.opened[leaf_id] = close_state
            bodies.append(
                bf.client_call(
                    "BattleGroundSpace",
                    "onElementClose",
                    self.space_id,
                    struct.pack("<i", leaf_id),
                )
            )

    def _maybe_append_opened_elements(self, bodies):
        if not self._mirror_opened_elements():
            return
        bodies.append(
            bf.update_property(
                "BattleGroundSpace",
                "openedElements",
                encode_opened_elements(self.opened),
                eid=self.space_id,
            )
        )


def register(session):
    mod = DoorsModule(session)
    mod.start()
    return mod