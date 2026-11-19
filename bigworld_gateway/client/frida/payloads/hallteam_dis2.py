# READ-ONLY: match-state enums, iHallTeam method list, and the UI code that sends
# createHallTeam / getReadyForBattleGround. Does not call any game method.
import sys
import types

out = open(OUT, 'w')


def w(s):
    out.write(s + '\n')


const = sys.modules.get('const') or sys.modules.get('common.const')
for cname in ('BattleMatchState', 'GameEnterType', 'HallTeamType', 'MatchState'):
    for modname in ('const', 'common.const', 'shared.const'):
        mod = sys.modules.get(modname)
        c = getattr(mod, cname, None) if mod else None
        if c is not None:
            w('ENUM %s.%s = %r' % (modname, cname, dict((k, v) for k, v in vars(c).items() if not k.startswith('__'))))
            break

ih = sys.modules.get('entities.iHallTeam') or sys.modules.get('iHallTeam')
if ih is None:
    for k, m in sys.modules.items():
        if m is not None and k.endswith('iHallTeam'):
            ih = m
            w('module %s' % k)
            break
if ih is not None:
    for k, v in sorted(vars(ih).items()):
        if isinstance(v, (type, types.ClassType)):
            w('CLASS %s methods=%r' % (k, sorted(n for n in vars(v) if not n.startswith('__'))))
        elif isinstance(v, (int, long, str)) and not k.startswith('__'):
            w('CONST %s = %r' % (k, v))

WANT = ('createHallTeam', 'getReadyForBattleGround', 'notReadyForBattleGround', 'onGetOpenMaintenanceFightTipFlag')


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


if ih is not None:
    cls = getattr(ih, 'iHallTeam', None)
    for n in ('getReadyForBattleGround', 'onGetOpenMaintenanceFightTipFlag', 'isInTeam', 'isInFormedTeam', 'onCreate'):
        co = code_of(vars(cls).get(n))
        if co is not None:
            w('METHOD iHallTeam.%s line %d vars=%r' % (n, co.co_firstlineno, list(co.co_varnames)))
            w('   names=%r' % (list(co.co_names),))
            w('   consts=%r' % ([x if not isinstance(x, types.CodeType) else '<code>' for x in co.co_consts],))

hits = 0
for modname, mod in sorted(sys.modules.items()):
    if mod is None or hits > 20:
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
                if any(x in c.co_names for x in WANT):
                    hits += 1
                    w('CALLER %s:%s (%s line %d) vars=%r' % (modname, label, c.co_filename, c.co_firstlineno, list(c.co_varnames)))
                    w('   names=%r' % (list(c.co_names),))
                    w('   consts=%r' % ([x if not hasattr(x, 'co_code') else '<code>' for x in c.co_consts],))
out.close()
