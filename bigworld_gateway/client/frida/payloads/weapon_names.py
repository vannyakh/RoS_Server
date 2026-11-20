# READ-ONLY: how the client reacts to weapon properties / wear calls.
import sys, BigWorld
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
def co(f):
    f = getattr(f, 'im_func', f)
    return getattr(f, 'func_code', None)
p = BigWorld.player()
for cls in type(p).__mro__:
    for n in ('onWearDtsWeapon', 'set_dtsWeapon1', 'set_dtsWeapon2', 'set_dtsCurWeapon', 'onChangeDtsWeapon', 'tryWearWeapon'):
        f = cls.__dict__.get(n)
        k = co(f) if f else None
        if k:
            w('== %s.%s args=%r' % (cls.__name__, n, list(k.co_varnames[:k.co_argcount])))
            w('names=%r' % list(k.co_names))
            w('consts=%r' % [x for x in k.co_consts if not hasattr(x, 'co_code')])
for n in ('dtsWeapon1', 'dtsWeapon2', 'dtsWeapon3', 'dtsWeapon4', 'dtsWeapon5', 'dtsCurWeapon'):
    v = getattr(p, n, '<none>')
    try: v = dict((k, v[k]) for k in v.keys())
    except Exception: pass
    w('%s=%r' % (n, v))
out.close()
