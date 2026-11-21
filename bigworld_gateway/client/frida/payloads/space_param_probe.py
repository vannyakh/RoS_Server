# READ-ONLY: BattleGroundParam fields per map id, and where BattleGroundGameStatusEnum lives.
import sys, types

f = open(OUT, 'w')
def w(s): f.write(s + '\n')
def short(v, n=160):
    r = repr(v)
    return r if len(r) <= n else r[:n] + '...'

for mname, mod in sorted(sys.modules.items()):
    if mod is None: continue
    try:
        e = vars(mod).get('BattleGroundGameStatusEnum')
    except Exception:
        e = None
    if e is not None:
        vals = {}
        for k in dir(e):
            if k.startswith('_'): continue
            v = getattr(e, k, None)
            if isinstance(v, (int, long)): vals[k] = v
        w('ENUM in %s: %s' % (mname, sorted(vals.items(), key=lambda kv: kv[1])))
        break

import maps_utils
for mid in (700, 701, 702, 703, 722, 800, 710):
    try:
        d = maps_utils.getBattleGroundParamData(mid)
    except Exception as ex:
        w('MAP %s err %r' % (mid, ex)); continue
    w('MAP %s %s' % (mid, type(d).__name__))
    for k in sorted(dir(d)):
        if k.startswith('_'): continue
        try: v = getattr(d, k)
        except Exception: continue
        if callable(v): continue
        w('   %s = %s' % (k, short(v)))
f.close()
