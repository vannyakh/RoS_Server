from tools.original_data.import_tables import parse_table

SAMPLE = """# -*- coding: utf-8 -*-
name = "物品表"
data = \
{
    1: {'type': 'Prop', 'value': {'NAME': _g89na_trans('00ff'), 'WEIGHT': 2, 'PATH': 'ab'}},
}
"""


def test_parse_table_reads_title_and_records():
    title, data = parse_table(SAMPLE)
    assert title == "物品表"
    assert data[1]["value"]["WEIGHT"] == 2
    assert data[1]["value"]["NAME"] == "T"


def test_parse_table_rejects_non_tables():
    assert parse_table("print('hi')") is None
    assert parse_table('name = "x"\ndata = {broken') is None


def test_loader_returns_empty_without_imported_files(tmp_path, monkeypatch):
    from app.game import original_data

    monkeypatch.setattr(original_data, "DATA_DIR", tmp_path)
    original_data.load_table.cache_clear()
    assert original_data.gun_mechanics() == {}
    original_data.load_table.cache_clear()
