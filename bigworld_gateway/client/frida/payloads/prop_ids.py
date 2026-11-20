# READ-ONLY: list battleground prop ids (weapons, ammo, heal, armor...) from the client's own data.
import sys
out = open(OUT, 'w')
def w(s): out.write(s + '\n')

lp = None
fn = None
for mn, mod in sorted(sys.modules.items()):
    f = getattr(mod, 'getBattleGroundPropData', None) if mod is not None else None
    if f is not None:
        w('module with getBattleGroundPropData: %s' % mn)
        if mn == 'shared.lib.gametoolslib.properties':
            lp, fn = mod, f
w('fn=%r' % (fn,))
found = {}
if fn is not None:
    for i in range(1, 6000):
        try:
            d = fn(i)
        except Exception:
            continue
        if d is None:
            continue
        found[i] = d
w('count=%d' % len(found))
shown = 0
for i in sorted(found):
    d = found[i]
    try:
        keys = list(d.keys()) if hasattr(d, 'keys') else dir(d)
    except Exception:
        keys = []
    if shown < 2:
        w('sample %d keys=%r' % (i, keys[:30]))
        shown += 1
    try:
        pt = d['PROP_TYPE'] if hasattr(d, 'keys') else getattr(d, 'PROP_TYPE', None)
        name = ''
        for k in ('NAME', 'ITEM_NAME', 'NAME_ID', 'name'):
            try:
                name = d[k]
                break
            except Exception:
                pass
        w('%d type=%r name=%r' % (i, pt if not hasattr(pt, 'keys') else dict(pt.items()) if hasattr(pt, 'items') else pt, name))
    except Exception as e:
        w('%d err=%r' % (i, e))
out.close()
