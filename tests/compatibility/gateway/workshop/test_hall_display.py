"""Depot Display choices: the lobby vehicle (setDtsHallVehicleAppearance) and the lobby firearm
(setOutGameWeapon). Ids are real client props: 140010 Spark V3 and 140031 Nova X1 are skins of the
same car (vehicle 115501), 140403 is another vehicle, 120920 is an AKM skin."""
import athlete_requests as a

SPARK_V3, NOVA_X1, WILD_BEAST, AKM_SKIN = 140010, 140031, 140403, 120920


def test_display_keeps_one_skin_per_vehicle():
    o = a.Outfit()
    o.set_hall_vehicle(SPARK_V3)
    o.set_hall_vehicle(NOVA_X1)
    assert o.hall_vehicle == [NOVA_X1]


def test_newest_display_choice_comes_first():
    o = a.Outfit()
    o.set_hall_vehicle(WILD_BEAST)
    o.set_hall_vehicle(NOVA_X1)
    assert o.hall_vehicle == [NOVA_X1, WILD_BEAST]


def test_old_save_with_two_skins_of_one_vehicle_loads_the_last():
    o = a.Outfit.from_dict({"hall_vehicle": [SPARK_V3, NOVA_X1]})
    assert o.hall_vehicle == [NOVA_X1]


def test_display_refuses_a_non_vehicle():
    assert a.Outfit().set_hall_vehicle(AKM_SKIN) is False


def test_display_firearm_is_saved_per_gender_and_survives_a_save():
    o = a.Outfit()
    assert o.set_out_weapon(1, AKM_SKIN, 0)
    back = a.Outfit.from_dict(o.to_dict())
    assert back.get_out_weapon(1) == (AKM_SKIN, 0)
    assert back.get_out_weapon(2) == (0, 0)


def test_display_firearm_zero_clears_it():
    o = a.Outfit()
    o.set_out_weapon(1, AKM_SKIN, 0)
    assert o.set_out_weapon(1, 0, 0)
    assert o.get_out_weapon(1) == (0, 0)


def test_display_firearm_refuses_a_vehicle_skin():
    assert a.Outfit().set_out_weapon(1, NOVA_X1, 0) is False
