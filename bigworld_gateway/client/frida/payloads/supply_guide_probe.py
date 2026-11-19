# READ-ONLY: (1) code that opens the monthly Supreme page (refers to UIMonthlySupplyPackage /
# getCurrentMonthSupplementID), (2) the player's guide/tutorial state that auto-opens Supply.
import sys
import types

out = open(OUT, 'w')


def w(s):
    out.write(s[:1600] + '\n')


def code_of(o):
    if isinstance(o, (staticmethod, classmethod)):
        o = o.__func__
    co = getattr(o, 'func_code', None)
    return co if isinstance(co, types.CodeType) else None


def walk(co):
    yield co
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            for x in walk(c):
                yield x


WANT_NAMES = ('getCurrentMonthSupplementID',)
WANT_CONSTS = ('UIMonthlySupplyPackage',)
hits = 0
for modname, mod in sorted(sys.modules.items()):
    if mod is None or hits > 25 or not modname.startswith(('ui', 'common', 'entities', 'helpers', 'Athlete')):
        continue
    try:
        items = list(vars(mod).items())
    except Exception:
        continue
    for k, v in items:
        objs = [(k, v)]
        if isinstance(v, (type, types.ClassType)):
            objs = [(k + '.' + n, o) for n, o in vars(v).items()]
        for label, o in objs:
            co = code_of(o)
            if co is None:
                continue
            for c in walk(co):
                if any(x in c.co_names for x in WANT_NAMES) or any(x in c.co_consts for x in WANT_CONSTS):
                    hits += 1
                    w('CALLER %s:%s (%s:%d) vars=%r' % (modname, label, c.co_filename, c.co_firstlineno, list(c.co_varnames)))
                    w('   names=%r' % (list(c.co_names),))
                    w('   consts=%r' % ([x if not isinstance(x, types.CodeType) else '<code>' for x in c.co_consts],))

try:
    import BigWorld
    p = BigWorld.player()
    for a in sorted(dir(p)):
        if a.startswith('__'):
            continue
        if any(t in a.lower() for t in ('guide', 'tutorial', 'novice', 'newbie', 'firstdraw', 'freelottery')):
            try:
                v = getattr(p, a)
            except Exception:
                continue
            if not callable(v):
                w('ATTR %s = %r' % (a, v))
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
