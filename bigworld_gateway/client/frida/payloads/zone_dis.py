# READ-ONLY: how the client draws and animates the safe zone (BattleGroundSpace circle setters, rest-time, circle notify). Calls no game method.
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
sp = BigWorld.entities.get(20001)
cls = type(sp) if sp is not None else getattr(sys.modules.get('BattleGroundSpace'), 'BattleGroundSpace', None)
names = ('set_circleStage', 'set_blueCircleRadius', 'set_blueCircleCenter', 'set_whiteCircleRadius', 'set_whiteCircleCenter',
         'set_blueCircleStartRadius', 'set_gameStageStartTime', 'updateCircleRestTime', 'showCircleNotify', 'showCircleMessage',
         'getCurrentBlueCircle', 'calcBlueCircle', 'updateBlueCircle', 'tickCircle', 'onCircleTimer', 'refreshCircle')
for klass in cls.__mro__:
    for n in names:
        if n in vars(klass):
            dump('%s.%s' % (klass.__name__, n), vars(klass)[n])
out.write('space circle attrs: %r\n' % dict((k, getattr(sp, k, None)) for k in ('circleStage', 'blueCircleRadius', 'whiteCircleRadius', 'gameStageStartTime', 'gameStatus')) if sp else 'no space\n')
md = getattr(sp, 'mapData', None)
bp = None
try:
    import maps_utils
    bp = maps_utils.getBattleGroundParamData(700)
except Exception as e:
    out.write('param err %r\n' % (e,))
if bp is not None:
    for a in sorted(dir(bp)):
        if a.isupper() and ('CIRCLE' in a or 'STAGE' in a or 'POISON' in a or 'TIME' in a):
            out.write('param %s = %s\n' % (a, repr(getattr(bp, a))[:400]))
out.close()
