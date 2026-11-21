"""Battle prop stats read from the imported prop table."""

from app.game import original_data


def _table(monkeypatch, records: dict) -> None:
    monkeypatch.setattr(original_data, "load_table", lambda stem: records if stem == "br_items" else {})


def test_armour_and_attachment_stats(monkeypatch):
    _table(
        monkeypatch,
        {
            "1": {"value": {"PROP_TYPE": {"type": "PropTypebulletProofHelmet", "value": {"AntiDamage": 0.3, "DURABILITY": 80, "LEVEL": 1, "DES": "T"}}}},
            "7": {"value": {"PROP_TYPE": {"type": "PropTypeGunComponentNumeric", "value": {"PROP_LIST": [{"PROPERTY_FACTOR": -0.25, "PROPERTY_ID": 2}, {"PROPERTY_FACTOR": 0.1}]}}}},
            "9": {"value": {"PROP_TYPE": {"type": "Smoke", "value": {"TIME": 10.0, "DURATION": 4.0, "USE_ON_GET": True}}}},
        },
    )
    helmet = {row["label"]: row for row in original_data.prop_stats(1)}
    assert helmet["Damage reduction"] == {"key": "AntiDamage", "label": "Damage reduction", "value": 30.0, "unit": "%", "max": 100.0}
    assert helmet["Durability"]["value"] == 80
    assert [row["label"] for row in original_data.prop_stats(7)] == ["Property 2", "Modifier 2"]
    assert original_data.prop_stats(7)[0]["value"] == -25.0
    # One "Duration" row even when the record has both TIME and DURATION; booleans are skipped.
    assert [row["label"] for row in original_data.prop_stats(9)] == ["Duration"]


def test_missing_table_or_record_gives_no_stats(monkeypatch):
    _table(monkeypatch, {})
    assert original_data.prop_stats(1) == []
