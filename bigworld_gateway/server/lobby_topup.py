"""Top-Up pack amounts for the original client: packs grant diamonds on this server, no payment.

Client flow (Athlete.requsetPayGoods, read with client/frida/payloads/topup_dis.py and
topup_confirm_dis.py):
  1. requestRealNameAuthenCheckBeforeRequsetingPayGoods(STRING goodsID) to the server.
  2. The server answers onRequestRealNameAuthenCheckBeforeRequsetingPayGoods(goodsID, BOOL).
  3. After payment the server confirms with onConfirmPayOrder(BOOL ok, STRING sn, INT32 ingot,
     INT32 ingot_send, ARRAY<STRING> bids) and updates the balance (iCurrency.onYBUpdated).
ros_server.GateUDP._pay_request answers step 2 with False (so no NetEase SDK or store payment can
start) and, with GATEWAY_PRIVATE_TOPUP on, _complete_private_pay credits the pack at once and sends
step 3. The amount is AMOUNT + NORMAL_PRESENT from the client's PayGoods table
(extract/pay_goods.json, `grant`); pay_goods.diamonds_for_bid is only the fallback for ids the
table does not list. pay_utils.isPaying expires by itself (PAYING_REQUIRE_CD), so an unanswered
request cannot lock the screen.
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


def grant(goods_id):
    """(base diamonds, bonus diamonds) for a pack id, or None for an unknown id."""
    p = packs().get(goods_id)
    if not p:
        return None
    return int(p.get("AMOUNT") or 0), int(p.get("NORMAL_PRESENT") or 0)
