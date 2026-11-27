"""RO-067: openElement / closeElement via DoorsModule."""

from __future__ import annotations

import struct

import pytest

from wire_helpers import pack_close, pack_open

SPACE_ID = 20001


def test_open_known_door_echoes_on_element_open(session, sent, doors_mod, tiny_doors_data, bf, reqs):
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.start()
    msgid, payload = pack_open(reqs, 815, 1)
    session.dispatch_inbound(msgid, payload)
    assert len(sent) == 1
    expected = bf.client_call("BattleGroundSpace", "onElementOpen", SPACE_ID, struct.pack("<ib", 815, 1))
    assert sent[0] == expected
    assert mod.opened[815] == 1


def test_open_bad_state_for_known_door_is_refused(session, sent, doors_mod, tiny_doors_data, reqs):
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.start()
    msgid, payload = pack_open(reqs, 815, 99)
    session.dispatch_inbound(msgid, payload)
    assert sent == []
    assert 815 not in mod.opened


def test_close_known_door_echoes_on_element_close(session, sent, doors_mod, tiny_doors_data, bf, reqs):
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.start()
    mod.opened[815] = 1
    msgid, payload = pack_close(reqs, 815)
    session.dispatch_inbound(msgid, payload)
    assert len(sent) == 1
    assert sent[0] == bf.client_call("BattleGroundSpace", "onElementClose", SPACE_ID, struct.pack("<i", 815))
    assert mod.opened[815] == 0


def test_double_door_open_answers_both_leaves(session, sent, doors_mod, tiny_doors_data, bf, reqs):
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.start()
    msgid, payload = pack_open(reqs, 4660, 3)
    session.dispatch_inbound(msgid, payload)
    assert len(sent) == 2
    assert sent[0] == bf.client_call("BattleGroundSpace", "onElementOpen", SPACE_ID, struct.pack("<ib", 4660, 3))
    assert sent[1] == bf.client_call("BattleGroundSpace", "onElementOpen", SPACE_ID, struct.pack("<ib", 4661, 1))
    assert mod.opened[4660] == 3 and mod.opened[4661] == 1


def test_unknown_elem_echoes_open(session, sent, doors_mod, tiny_doors_data, bf, reqs):
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.start()
    msgid, payload = pack_open(reqs, 999001, 1)
    session.dispatch_inbound(msgid, payload)
    assert len(sent) == 1
    assert mod.opened[999001] == 1


def test_opened_elements_property_update_when_enabled(session, sent, doors_mod, tiny_doors_data, bf, reqs):
    data = __import__("json").loads(tiny_doors_data.read_text(encoding="utf-8"))
    data["opened_elements_on_reply"] = True
    tiny_doors_data.write_text(__import__("json").dumps(data), encoding="utf-8")
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.start()
    msgid, payload = pack_open(reqs, 815, 1)
    session.dispatch_inbound(msgid, payload)
    assert len(sent) == 2
    prop_body = bf.update_property(
        "BattleGroundSpace",
        "openedElements",
        doors_mod.encode_opened_elements(mod.opened),
        eid=SPACE_ID,
    )
    assert sent[1] == prop_body


def test_opened_values_for_create_entity(doors_mod, tiny_doors_data, session):
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.opened = {815: 1, 832: 2}
    assert mod.opened_values_for_create() == {}
    data = __import__("json").loads(tiny_doors_data.read_text(encoding="utf-8"))
    data["opened_elements_on_reply"] = True
    tiny_doors_data.write_text(__import__("json").dumps(data), encoding="utf-8")
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.opened = {815: 1, 832: 2}
    values = mod.opened_values_for_create()
    assert set(values) == {"openedElements"}
    assert values["openedElements"] == doors_mod.encode_opened_elements(mod.opened)


def test_module_loads_production_table(session, doors_mod):
    mod = doors_mod.DoorsModule(session)
    assert mod.by_id
    assert 832 in mod.known_ids


def test_wrong_space_entity_id_is_ignored(session, sent, doors_mod, tiny_doors_data, reqs):
    mod = doors_mod.DoorsModule(session, doors_data_path=tiny_doors_data)
    mod.start()
    msgid, payload = pack_open(reqs, 815, 1, space_id=19999)
    session.dispatch_inbound(msgid, payload)
    assert sent == []