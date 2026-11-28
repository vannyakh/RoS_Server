# READ-ONLY: find and disassemble the death/result screen class UIBattlegroundsResult (opened by
# iBattleGround._showResult with the onBattleGroundResult args). Imports its module if it is not loaded
# yet (module import only, no game method is called).
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


names = sorted(n for n in sys.modules if n and ('result' in n.lower() or 'readyexit' in n.lower()))
out.write('modules: %r\n' % names)
try:
    import uiMgr
    out.write('uiMgr has: %r\n' % [n for n in dir(uiMgr) if 'path' in n.lower() or 'conf' in n.lower()][:20])
except Exception as e:
    out.write('uiMgr: %r\n' % (e,))
for cand in ('ui.UIBattlegroundsResult', 'ui.battlegrounds.UIBattlegroundsResult', 'UIBattlegroundsResult',
             'ui.battle.UIBattlegroundsResult', 'ui.dts.UIBattlegroundsResult'):
    if cand in sys.modules:
        continue
    try:
        __import__(cand)
        out.write('imported %s\n' % cand)
        break
    except Exception as e:
        out.write('import %s: %r\n' % (cand, e))

seen = set()
for modname, mod in sorted(sys.modules.items()):
    if mod is None:
        continue
    v = getattr(mod, 'UIBattlegroundsResult', None)
    if v is None or getattr(v, '__module__', '') != modname:
        continue
    out.write('#### %s\n' % modname)
    for n, f in sorted(vars(v).items()):
        c = code_of(f)
        if c is not None and id(c) not in seen:
            seen.add(id(c))
            dump('%s.%s' % (modname, n), f)
out.close()
