# READ-ONLY: battle prop catalog (id, type, name, icon path, stack, weight) from the client's own data,
# written as JSON lines. Text only; no images or models are copied.
import sys, json
out = open(OUT, 'w')
fn = None
for mn, mod in sorted(sys.modules.items()):
    if mn == 'shared.lib.gametoolslib.properties' and mod is not None:
        fn = getattr(mod, 'getBattleGroundPropData', None)
text = None
for mn in ('localization', 'lang', 'helpers.localization', 'common.localization'):
    m = sys.modules.get(mn)
    if m is not None:
        text = m
        break

def get(d, k):
    try:
        return d[k]
    except Exception:
        return getattr(d, k, None)

def plain(v):
    if isinstance(v, (int, long, float, bool)) or v is None:
        return v
    if isinstance(v, unicode):
        return v.encode('utf-8')
    if isinstance(v, str):
        return v
    return repr(v)[:80]

n = 0
if fn is not None:
    for i in range(1, 6000):
        try:
            d = fn(i)
        except Exception:
            continue
        if d is None:
            continue
        pt = get(d, 'PROP_TYPE')
        row = {'id': i, 'type': type(pt).__name__.replace('PropType', '') if pt is not None else None}
        for k in ('NAME', 'BRIEF_DES', 'ICON_PATH', 'BIG_ICON_PATH', 'PICK_UP_ICON_PATH', 'MaxStack', 'MAX_CNT_IN_PACKAGE', 'WEIGHT', 'CAPACITY', 'HIERARCHY', 'IsRos2Prop'):
            row[k] = plain(get(d, k))
        out.write(json.dumps(row) + '\n')
        n += 1
out.write(json.dumps({'count': n}) + '\n')
out.close()
