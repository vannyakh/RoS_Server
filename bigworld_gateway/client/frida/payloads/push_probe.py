# READ-ONLY: onSetSwitches, the weekly supply push decision, and the supply draw-guide.
import sys
import types

out = open(OUT, 'w')


def w(s):
    out.write(s[:1500] + '\n')


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


def show(label, co):
    w('== %s (%s:%d) vars=%r' % (label, co.co_filename, co.co_firstlineno, list(co.co_varnames)))
    w('   names=%r' % (list(co.co_names),))
    w('   consts=%r' % ([c if not isinstance(c, types.CodeType) else '<code>' for c in co.co_consts],))


try:
    import BigWorld
    p = BigWorld.player()
    cls = type(p)
    for n in ('onSetSwitches', 'onUpdateAlreadyShowSupplyID'):
        co = code_of(getattr(cls, n, None))
        if co:
            show('PlayerAthlete.' + n, co)
    for a in ('alreadyShowSupplyID', 'hasAlreadyShowSupplyID', 'alreadyShowSupplyIDList'):
        if hasattr(p, a):
            w('ATTR %s = %r' % (a, getattr(p, a)))
    WANT_NAMES = ('alreadyShowSupplyID', 'weeklyPush')
    WANT_CONSTS = ('weeklyPush', 'UISupplyGuide', 'UIFreeDrawGuide')
    hits = 0
    for modname, mod in sorted(sys.modules.items()):
        if mod is None or hits > 15 or not modname.startswith(('ui', 'entities', 'helpers', 'Athlete', 'common')):
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
                        show('%s:%s' % (modname, label), c)
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
