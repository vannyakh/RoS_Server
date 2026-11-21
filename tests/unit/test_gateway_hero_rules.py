"""The gateway only ever hands the hall a normal male or female hero."""

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def rules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("bigworld_gateway/server").resolve()))
    module = importlib.import_module("hero_rules")
    yield importlib.reload(module)
    sys.modules.pop("hero_rules", None)


def test_normal_heroes_are_kept(rules):
    assert rules.normalize_hero(20001, gender=2) == 20001
    assert rules.normalize_hero(20002, gender=1) == 20002


@pytest.mark.parametrize("char_type", [0, 1, 10001, 10002, 30001, -5, None, "abc"])
def test_other_types_fall_back_to_the_players_gender(rules, char_type):
    assert rules.normalize_hero(char_type, gender=1) == 20001
    assert rules.normalize_hero(char_type, gender=2) == 20002


def test_unknown_gender_defaults_to_male(rules):
    assert rules.normalize_hero(30001, gender=7) == 20001


def test_hero_gender_follows_the_normalized_type(rules):
    assert rules.hero_gender(20001) == 1
    assert rules.hero_gender(20002) == 2
    assert rules.hero_gender(30001) == 1
