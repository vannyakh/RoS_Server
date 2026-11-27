"""Currencies an operator can grant, top up or price in.

`coin` and `diamond` are the independent web wallet (cosmetics_service). Every other row is a
currency of the original client: `client_id` is its const.MallCurrencyType value, taken from the
client's own table (hallprop_prices `currency_types`). `gold` and `yuanbao` are the codes the
gateway already keeps balances under. Codes fit the ledger's `[a-z0-9_]{1,16}`.

Only `yuanbao` is charged by an in-game purchase today; the rest can be granted and topped up.
"""

from dataclasses import asdict, dataclass

from app.services.cosmetics_service import COIN, DIAMOND
from app.services.gateway_service import GOLD, GOLD_ID, YUANBAO


@dataclass(frozen=True)
class Currency:
    code: str
    label: str
    client_id: int | None
    scope: str  # "web" or "game"
    spendable: bool  # charged by a purchase route today


CURRENCIES: tuple[Currency, ...] = (
    Currency(COIN, "Coins", None, "web", True),
    Currency(DIAMOND, "Diamonds", None, "web", True),
    Currency(GOLD, "Gold", GOLD_ID, "game", False),
    Currency(YUANBAO, "Diamonds", 2, "game", True),
    Currency("sp", "SP", 3, "game", False),
    Currency("clothing_chips", "Clothing chips", 4, "game", False),
    Currency("christmas_coin", "Christmas coins", 5, "game", False),
    Currency("christmas_ticket", "Christmas tickets", 6, "game", False),
    Currency("share_coin", "Share coins", 8, "game", False),
    Currency("colour_diamond", "Colour diamonds", 9, "game", False),
    Currency("honor_chips", "Honor chips", 10, "game", False),
    Currency("supply_chips", "Supply chips", 11, "game", False),
    Currency("battle_ticket", "Gold battle tickets", 12, "game", False),
    Currency("exchange_ticket", "Exchange tickets", 13, "game", False),
    Currency("brave_book_score", "Brave book chest score", 14, "game", False),
    Currency("commander_ticket", "Commander tickets", 15, "game", False),
    Currency("universal_frag", "Universal fragments", 16, "game", False),
    Currency("point", "Points", 17, "game", False),
    Currency("moonlight", "Moonlight", 18, "game", False),
    Currency("precious_ticket", "Precious tickets", 19, "game", False),
    Currency("vid_coin", "VID coins", 20, "game", False),
    Currency("hot_value", "Hot value", 21, "game", False),
    Currency("treasure_map", "Treasure maps", 22, "game", False),
    Currency("treasure_car", "Treasure cars", 23, "game", False),
    Currency("secret_treasure", "Secret treasure", 30, "game", False),
    Currency("hero_ticket", "Hero supplement tickets", 31, "game", False),
    Currency("red_flag", "Pacesetter red flags", 32, "game", False),
    Currency("highlevel_ticket", "High-level tickets", 91, "game", False),
    Currency("prize_match_coin", "Prize match coins", 201, "game", False),
    Currency("star_diamond", "Star diamonds", 202, "game", False),
    Currency("anniv_coin", "Anniversary coins", 207, "game", False),
    Currency("match_team_coin", "Match team coins", 208, "game", False),
    Currency("monthcard_coin", "Month card coins", 209, "game", False),
    Currency("halloween_coin", "Halloween coins", 210, "game", False),
    Currency("anniv3_coin", "3rd anniversary coins", 211, "game", False),
    Currency("xmas_repair_coin", "Christmas repair coins", 212, "game", False),
    Currency("horse_race_coin", "Horse racing coins", 213, "game", False),
    Currency("dailypay_coin", "Daily pay coins", 214, "game", False),
    Currency("half_anniv_coin", "Half-anniversary coins", 215, "game", False),
    Currency("anniv4_coin", "4th anniversary coins", 216, "game", False),
    Currency("xmas_bell", "Christmas bells", 217, "game", False),
    Currency("recall_exchange", "Recall exchange", 218, "game", False),
)


def currency_list() -> list[dict]:
    return [asdict(row) for row in CURRENCIES]
