# READ-ONLY: UIBattlegroundsResult (the normal result screen) methods, names and string constants, with
# full disassembly of on_enter / showResult and friends. Run 3 (2026-11-28) entered it with no error
# and no panel was seen. Module import only; no game method is called.
import sys

out = open(OUT, 'w')
FULL = ('delayShowResult', 'isInFightStatus', 'on_enter', 'on_init', 'showResult', 'on_show', 'refresh', 'onRealExitBtnEvent', 'onExitBtnEvent', 'onNextBtnEvent', 'playAnim', 'showRank')


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


for cand in ('ui.UIBattlegroundsResult', 'entities.BattleGroundSpace'):
    if cand not in sys.modules:
        try:
            __import__(cand)
        except Exception as e:
            out.write('import %s: %r\n' % (cand, e))

for modname, mod in sorted(sys.modules.items()):
    if mod is None:
        continue
    for cls_name in ('UIBattlegroundsResult', 'BattleGroundSpace'):
        v = getattr(mod, cls_name, None)
        if v is None or getattr(v, '__module__', '') != modname:
            continue
        out.write('#### %s.%s bases=%r\n' % (modname, cls_name, [b.__name__ for b in v.__bases__]))
        for n, f in sorted(vars(v).items()):
            c = code_of(f)
            if c is not None and (cls_name != 'BattleGroundSpace' or 'ight' in n or 'tatus' in n):
                summary('%s.%s' % (cls_name, n), c, n in FULL)
for modname, mod in sorted(sys.modules.items()):
    v = getattr(mod, 'BattleGroundSpace', None) if mod is not None else None
    if v is not None and getattr(v, '__module__', '') == modname:
        for k in sorted(dir(v)):
            if 'ight' in k or 'tatus' in k:
                out.write('BattleGroundSpace.%s = %r\n' % (k, getattr(v, k, None)))
out.close()
