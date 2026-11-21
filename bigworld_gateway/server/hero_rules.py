"""Hall hero rules: a player is one of two normal heroes, male or female.

The client's character table (legacyProperties.getCharactersData) also holds 10001/10002 (no hall
model on LDPlayer) and 30001 (bot_base, the robot placeholder). Those are never player bodies, so
every character type that enters or leaves the gateway goes through normalize_hero().
"""

MALE_HERO = 20001      # dataosha_male, GENDER 1
FEMALE_HERO = 20002    # GENDER 2
HERO_GENDER = {MALE_HERO: 1, FEMALE_HERO: 2}
GENDER_HERO = {1: MALE_HERO, 2: FEMALE_HERO}


def normalize_hero(char_type, gender=1):
    """A normal hero type. A type that is not one keeps the player's gender (1 male, 2 female)."""
    try:
        char_type = int(char_type)
    except (TypeError, ValueError):
        char_type = 0
    if char_type in HERO_GENDER:
        return char_type
    return GENDER_HERO.get(gender, MALE_HERO)


def hero_gender(char_type):
    """dtsAppearanceGender of a normal hero (1 male, 2 female)."""
    return HERO_GENDER[normalize_hero(char_type)]
