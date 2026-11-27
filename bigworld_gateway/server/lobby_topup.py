"""Top-Up screen for the original client: packs grant diamonds on this server, no payment.

Client flow (Athlete.requsetPayGoods, read with client/frida/payloads/topup_dis.py and
topup_confirm_dis.py):
  1. requestRealNameAuthenCheckBeforeRequsetingPayGoods(STRING goodsID) to the server.
  2. A real server answers onRequestRealNameAuthenCheckBeforeRequsetingPayGoods(goodsID, BOOL),
     after which the client starts the NetEase SDK / Google Play payment (_requsetPayGoods).
  3. After payment the server confirms with onConfirmPayOrder(BOOL ok, STRING sn, INT32 ingot,
     INT32 ingot_send, ARRAY<STRING> bids) and updates the balance (iCurrency.onYBUpdated).
This server never sends step 2, so no SDK or store payment can start. It credits the pack at once
(AMOUNT + NORMAL_PRESENT from the client's PayGoods table, extract/pay_goods.json) and sends step 3.
pay_utils.isPaying expires by itself (PAYING_REQUIRE_CD), so an unanswered request cannot lock the
screen. TOPUP_GRANT=off turns the grant off (the request is then only logged).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_PACKS = None


def packs():
    global _PACKS
    if _PACKS is None:
        with open(os.path.join(HERE, "extract", "pay_goods.json"), encoding="utf-8") as f:
            _PACKS = json.load(f)
    return _PACKS


def enabled():
    return os.environ.get("TOPUP_GRANT", "on") != "off"


def grant(goods_id):
    """(base diamonds, bonus diamonds) for a pack id, or None for an unknown id."""
    p = packs().get(goods_id)
    if not p:
        return None
    return int(p.get("AMOUNT") or 0), int(p.get("NORMAL_PRESENT") or 0)
