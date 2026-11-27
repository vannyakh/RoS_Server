# READ-ONLY: export wearable appearance id -> battle prop id (hall PROP_TYPE.PROP_ITEM_ID) and disassemble refreshBattlegroundPropID2AppearanceIDDict. Calls only data getters.
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
for klass in type(p).__mro__:
    f = vars(klass).get('refreshBattlegroundPropID2AppearanceIDDict')
    if f is not None:
        dump('%s.refreshBattlegroundPropID2AppearanceIDDict' % klass.__name__, f)
        break
lp = None
for m, mod in sys.modules.items():
    if mod is not None and hasattr(mod, 'getDtsHallPropData'):
        lp = mod
        out.write('legacy module %s\n' % m)
        break
ids = list(WANT_IDS) if 'WANT_IDS' in globals() else []
au = None
for m, mod in sys.modules.items():
    if mod is not None and m.endswith('dts_appearance_utils'):
        au = mod
        break
rows = 0
for m, mod in sys.modules.items():
    pass
hp = sys.modules.get('hall_props_ids')
src = getattr(lp, 'getAllDtsHallPropID', None) or getattr(lp, 'iterDtsHallPropData', None)
out.write('lp attrs with HallProp: %r\n' % [a for a in dir(lp) if 'HallProp' in a][:30])
for aid in (111900, 111382, 102568):
    try:
        d = lp.getDtsHallPropData(aid)
        pt = d.PROP_TYPE
        out.write('hall %d -> %r\n' % (aid, dict((a, getattr(pt, a)) for a in dir(pt) if a.isupper())))
    except Exception as e:
        out.write('hall %d err %r\n' % (aid, e))
out.close()
