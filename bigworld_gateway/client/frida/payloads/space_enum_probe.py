# READ-ONLY: game-status enums and per-map battleground parameters (prepare time, modes) of the client.
import sys, types

f = open(OUT, 'w')
def w(s): f.write(s + '\n')
def short(v, n=500):
    r = repr(v)
    return r if len(r) <= n else r[:n] + '...'

try:
    import const
    for name in ('BattleGroundGameStatusEnum', 'WaitBornStatus', 'PlaneAuctionStage', 'BattleGroundFlightStage'):
        e = getattr(const, name, None)
        if e is None:
            w('ENUM %s <missing>' % name); continue
        vals = {}
        for k in dir(e):
            if k.startswith('_'): continue
            v = getattr(e, k, None)
            if isinstance(v, (int, long)): vals[k] = v
        w('ENUM %s %s' % (name, sorted(vals.items(), key=lambda kv: kv[1])))
except Exception as ex:
    w('const err %r' % (ex,))

try:
    import maps_utils
    for k in sorted(maps_utils.MAP_SPACE_TYPE):
        w('SPACE_TYPE %s -> %s' % (k, short(maps_utils.MAP_SPACE_TYPE[k], 200)))
    fn = maps_utils.getBattleGroundParamData
    co = fn.func_code
    w('getBattleGroundParamData vars=%s names=%s' % (list(co.co_varnames), list(co.co_names)[:30]))
    for mid in (700, 701, 702, 703, 710, 720, 722, 750, 800, 600, 500, 400, 300, 200, 100, 99, 50, 20, 10, 5, 1):
        try:
            d = fn(mid)
            w('PARAM %s -> %s' % (mid, short(d, 700)))
        except Exception as ex:
            w('PARAM %s err %r' % (mid, ex))
    w('MAP_CLASS_TYPE %s' % short(sorted(maps_utils.MAP_CLASS_TYPE.items()), 1500))
except Exception as ex:
    w('maps err %r' % (ex,))
f.close()
