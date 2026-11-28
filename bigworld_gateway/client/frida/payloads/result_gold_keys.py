# READ-ONLY: which onBattleGroundResult row keys the result screen reads. Lists, for every method of
# UIBattlegroundsResultGold (and UIBattleGameResult), its line range, names and string constants, and
# disassembles on_enter / _showYulefenPanel in full (the two methods that failed on 2026-11-27:
# FailedUnpickle.get at on_enter line 285, KeyError 'newEntertainScore' at line 918).
# Module import only; no game method is called.
import sys

out = open(OUT, 'w')
FULL = ('on_enter', '_showYulefenPanel', 'showResult', 'onBattleGroundResult', 'onBattleGroundDie',
        '_delayShowResult', '_showResult', 'onRealExitBtnEvent', '_showTransitPanel')


def code_of(func):
    return getattr(func, 'func_code', None) or getattr(getattr(func, '__func__', None), 'func_code', None)


def lines(co):
    m = {}; addr = 0; ln = co.co_firstlineno; t = co.co_lnotab
    for k in range(0, len(t), 2):
        m.setdefault(addr, ln); addr += ord(t[k]); ln += ord(t[k + 1])
    m.setdefault(addr, ln)
    return m


def dump_code(co, indent=''):
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


def summary(label, co, full):
    strs = [c for c in co.co_consts if isinstance(c, basestring)]
    out.write('==== %s line %s\n' % (label, co.co_firstlineno))
    out.write('  vars=%r\n  names=%r\n  strs=%r\n' % (list(co.co_varnames), list(co.co_names), strs))
    if full:
        out.write('  consts=%r\n' % [c if not hasattr(c, 'co_code') else '<code %s>' % c.co_name
                                     for c in co.co_consts])
        dump_code(co)
    for c in co.co_consts:
        if hasattr(c, 'co_code'):
            summary(label + '.' + c.co_name, c, full)


for cand in ('ui.UIBattlegroundsResultGold', 'ui.UIBattleGameResult', 'entities.iBattleGround'):
    if cand not in sys.modules:
        try:
            __import__(cand)
        except Exception as e:
            out.write('import %s: %r\n' % (cand, e))

for modname, mod in sorted(sys.modules.items()):
    if mod is None:
        continue
    for cls_name in ('UIBattlegroundsResultGold', 'UIBattleGameResult', 'iBattleGround'):
        v = getattr(mod, cls_name, None)
        if v is None or getattr(v, '__module__', '') != modname:
            continue
        out.write('#### %s.%s bases=%r\n' % (modname, cls_name, [b.__name__ for b in v.__bases__]))
        for n, f in sorted(vars(v).items()):
            c = code_of(f)
            if c is not None and (cls_name != 'iBattleGround' or 'esult' in n or 'Die' in n):
                summary('%s.%s' % (cls_name, n), c, n in FULL)
out.close()
