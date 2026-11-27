# READ-ONLY: plane boarding / jump / fall handlers on the battle player and Plane entity, plus battle-state enums. Calls no game method.
# and list match-state constants. Does not call any game method.
import sys

out = open(OUT, 'w')


def code_of(func):
    return getattr(func, 'func_code', None) or getattr(getattr(func, '__func__', None), 'func_code', None)


def lines(co):
    m = {}; addr = 0; ln = co.co_firstlineno; t = co.co_lnotab
    for k in range(0, len(t), 2):
        m.setdefault(addr, ln); addr += ord(t[k]); ln += ord(t[k + 1])
    m.setdefault(addr, ln)
    return m


def dump_code(co, indent=''):
    # opcodes are remapped in this build: print names/consts/vars and the per-line arg refs
    out.write('%s  file %s line %s vars=%r\n' % (indent, co.co_filename, co.co_firstlineno, list(co.co_varnames)))
    out.write('%s  names=%r\n' % (indent, list(co.co_names)))
    out.write('%s  consts=%r\n' % (indent, [c if not hasattr(c, 'co_code') else '<code %s>' % c.co_name for c in co.co_consts]))
    lm = lines(co); code = co.co_code; i = 0; cur = co.co_firstlineno; row = {}
    while i < len(code):
        if i in lm: cur = lm[i]
        op = ord(code[i])
        if op >= 90:
            arg = ord(code[i + 1]) | (ord(code[i + 2]) << 8)
            row.setdefault(cur, []).append('%d:%d' % (op, arg)); i += 3
        else:
            row.setdefault(cur, []).append(str(op)); i += 1
    for ln in sorted(row):
        out.write('%s  L%d %s\n' % (indent, ln, ' '.join(row[ln])))
    for c in co.co_consts:
        if hasattr(c, 'co_code'):
            out.write('%s  --- nested %s\n' % (indent, c.co_name))
            dump_code(c, indent + '    ')


def dump(label, func):
    out.write('==== %s\n' % label)
    code = code_of(func)
    if code is None:
        out.write('  (no code)\n')
        return
    dump_code(code)

import BigWorld
p = BigWorld.player()
cls = type(p)
def find(klass, n):
    for k in klass.__mro__:
        if n in vars(k):
            return k, vars(k)[n]
    return None, None
for n in ('set_planeID', 'set_battleState', 'set_flightStage', 'set_fallPhase', 'set_hasLanded', 'set_leftPlayerNumOnPlane',
          'requestGetOffPlane', 'getOffPlane', 'onGetOffPlane', 'changeFallPhase', 'jumpFlight', 'isOnPlane', 'inPlane'):
    k, f = find(cls, n)
    if f is not None:
        dump('%s.%s' % (k.__name__, n), f)
for modname in ('Plane', 'entities.Plane'):
    mod = sys.modules.get(modname)
    if mod is not None:
        for k, v in vars(mod).items():
            if isinstance(v, type) and getattr(v, '__module__', '') == modname:
                out.write('#### class %s.%s: %r\n' % (modname, k, sorted(x for x in vars(v) if not x.startswith('__'))))
                for n in ('enterWorld', 'onEnterWorld', 'tick', 'update', '_updatePos', 'getPosByTime', 'calcPos', 'set_movePath', 'set_inJumpArea'):
                    if n in vars(v):
                        dump('%s.%s' % (k, n), vars(v)[n])
c = sys.modules.get('const')
for name in ('BattleState', 'FlightStage', 'FallPhase', 'PlaneMode', 'GameStatus', 'BattleGroundGameStatus', 'DtsGameStatus'):
    v = getattr(c, name, None)
    if v is not None:
        out.write('const.%s = %r\n' % (name, dict((a, b) for a, b in vars(v).items() if not a.startswith('_')) if hasattr(v, '__dict__') else v))
out.close()
