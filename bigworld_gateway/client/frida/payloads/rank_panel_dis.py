# READ-ONLY: disassemble the rank-list panel (own row + list rows) and RankData converters. Calls no game method.
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

WANT = ('onGetPlayerBattleGroundRank', 'onGetRankData', 'onGetPlayerRankFromMS', 'refreshMyRank', 'setSelfRankInfo')
for modname, mod in sorted(sys.modules.items()):
    if mod is None or not (modname.startswith('ui.') or 'Rank' in modname):
        continue
    try:
        items = list(vars(mod).items())
    except Exception:
        continue
    for k, v in items:
        if (isinstance(v, type) or type(v).__name__ == 'classobj') and getattr(v, '__module__', '') == modname:
            if k == 'UIRankList':
                continue
            names = [n for n in WANT if n in vars(v)]
            if names:
                out.write('#### class %s.%s methods=%r\n' % (modname, k, sorted(x for x in vars(v) if not x.startswith('__'))))
                for n in names:
                    dump('%s.%s' % (k, n), vars(v)[n])
rd = sys.modules.get('RankData')
if rd is not None:
    for k, v in sorted(vars(rd).items()):
        if isinstance(v, type) or type(v).__name__ == 'classobj':
            for n in ('getDictFromObj', 'createObjFromDict', '__init__'):
                if n in vars(v):
                    dump('RankData.%s.%s' % (k, n), vars(v)[n])
out.close()
