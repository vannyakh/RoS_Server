# READ-ONLY: buy currency and price of every hall prop (client mall_utils over local data)
# and the MallCurrencyType constants. JSON to OUT. No server call, no state change.
import sys
import json
mu = sys.modules['mall_utils']
const = sys.modules['const']
dh = sys.modules['dts_hall_prop_utils']
ids = []
for name in dir(dh):
    pass
lp = sys.modules['supplement_utils'].legacyProperties
src = None
for cand in ('iterDtsHallPropData', 'iterHallPropData', 'iterDtsHallProp'):
    if hasattr(lp, cand):
        src = cand
        break
res = {}
errs = 0
if src:
    for pid, _ in getattr(lp, src)():
        try:
            cid = mu.getDtsHallPropBuyCurrencyID(pid)
            price = mu.getDtsHallPropBuyCurrencyPrice(pid)
            if price:
                res[str(pid)] = [cid, price]
        except Exception:
            errs += 1
mct = dict((k, getattr(const.MallCurrencyType, k)) for k in dir(const.MallCurrencyType) if k.isupper())
out = open(OUT, 'w')
out.write(json.dumps({'source': src, 'errors': errs, 'currency_types': mct, 'prices': res}))
out.close()
