"""Gateway pre-start space entity bytes (original client createEntity framing).

Reads only `bigworld_gateway/server/battle_flow.py`; the app code never imports the gateway.
The wire layout is documented in `bigworld_gateway/docs/CREATE_ENTITY_FRAMING.md`. A passing test shows
the bytes match that document, not that the original client accepts them.
"""

import struct
import sys
from pathlib import Path

GATEWAY = Path(__file__).resolve().parents[2] / "bigworld_gateway" / "server"


def _battle_flow():
    sys.path.insert(0, str(GATEWAY))
    try:
        import battle_flow

        return battle_flow
    finally:
        sys.path.remove(str(GATEWAY))


def _create_entity_payload(data: bytes) -> bytes:
    """Strip the enterAoI message, then the createEntity id (0x0b) and its 16-bit length."""
    bf = _battle_flow()
    assert data[0] == bf.MSG_ENTER_AOI
    after_aoi = data[1 + 5 :] if len(data) > 6 else b""
    assert after_aoi[0] == bf.MSG_CREATE_ENTITY
    length = struct.unpack_from("<H", after_aoi, 1)[0]
    return after_aoi[3 : 3 + length]


def test_space_entity_has_the_flag_compression_and_mask_bytes_before_properties():
    bf = _battle_flow()
    payload = _create_entity_payload(bf.debug_command("space", 700))
    entity_id, entity_type = struct.unpack_from("<IH", payload, 0)
    assert entity_id == bf.SPACE_ID
    assert entity_type == bf.client_type("BattleGroundSpace")
    # id 4, type 2, position 12, three direction bytes, then the entity flag, compression type, mask flag
    flag, compression, mask_flag = payload[21], payload[22], payload[23]
    assert (flag, compression) == (0, 0)
    assert mask_flag == 1  # a bitmask follows; without this byte the client reads mapID's low byte as one


def test_space_command_puts_the_map_and_a_running_game_status_on_the_wire():
    bf = _battle_flow()
    payload = _create_entity_payload(bf.debug_command("space", 700))
    assert struct.pack("<i", 700) in payload  # mapID
    # gameStatus 0 is not a valid key on the client (KeyError in set_gameStatus), so the command sends 1
    assert bf.debug_command("space0", 700) != bf.debug_command("space", 700)


def test_leave_removes_the_space_entity():
    bf = _battle_flow()
    leave = bf.debug_command(f"leave {bf.SPACE_ID}", 700)
    assert leave[0] == bf.MSG_LEAVE_AOI and struct.pack("<I", bf.SPACE_ID) in leave


def test_spacet_puts_the_stage_start_on_the_wire_as_a_float():
    bf = _battle_flow()
    payload = _create_entity_payload(bf.debug_command("spacet 12.5", 700))
    assert struct.pack("<f", 12.5) in payload  # gameStageStartTime, compared with BigWorld.serverTime
    # with a different stage start the entity bytes differ only there
    other = _create_entity_payload(bf.debug_command("spacet 99.0", 700))
    assert len(other) == len(payload) and other != payload


def test_flight_steps_all_build_and_end_in_the_air_with_can_fall():
    bf = _battle_flow()
    lines = [line for _delay, group in bf.FLIGHT_STEPS for line in group]
    assert [d for d, _ in bf.FLIGHT_STEPS] == sorted(d for d, _ in bf.FLIGHT_STEPS)
    for line in lines:
        assert bf.debug_command(line.format(stage="12.000"), 700)
    assert lines[-1] == "setp fallPhase 2"  # CAN_FALL, const.FallPhase on the client
    assert any(line.startswith("setp planeID 0") for line in lines)  # released from the plane before the drop


def test_tp_is_a_fixed_size_forced_position_message():
    bf = _battle_flow()
    data = bf.debug_command("tp 698 19300 -373", 700)
    assert data[0] == 0x59 and len(data) == 1 + 36
    entity, space, vehicle, x, y, z = struct.unpack_from("<IIIfff", data, 1)
    assert (entity, space, vehicle, x, y, z) == (bf.AVATAR_ID, 1, 0, 698.0, 19300.0, -373.0)


def test_setp_uses_the_property_wire_type():
    bf = _battle_flow()
    int8 = bf.debug_command("setp fallPhase 2", 700)    # INT8: one value byte
    int32 = bf.debug_command("setp planeID 20002", 700)  # INT32: four value bytes
    assert int8[-1] == 2 and len(int32) == len(int8) + 3 and int32[-4:] == struct.pack("<i", 20002)


def test_spaces_sets_the_game_status():
    bf = _battle_flow()
    assert bf.debug_command("spaces 2 12.0", 700) != bf.debug_command("spaces 1 12.0", 700)
