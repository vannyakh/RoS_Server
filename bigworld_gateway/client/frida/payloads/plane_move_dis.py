# READ-ONLY: how the Plane moves (Plane.resetFilter, filter type, users of movePath/moveSpeed/getOnPlaneTime). Calls no game method.
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
pl = BigWorld.entities.get(20002)
mod = sys.modules.get('Plane')
cls = getattr(mod, 'Plane', None)
for n in ('resetFilter', 'enterWorld', 'onGetOff'):
    if cls is not None and n in vars(cls):
        dump('Plane.' + n, vars(cls)[n])
if pl is not None:
    out.write('plane pos %r filter %r\n' % (pl.position, getattr(pl, 'filter', None)))
    for k in ('movePath', 'moveSpeed', 'mode', 'inJumpArea', 'customPlan'):
        out.write('  plane.%s = %r\n' % (k, getattr(pl, k, None)))
def walk(co, acc):
    acc.update(co.co_names)
    for c in co.co_consts:
        if hasattr(c, 'co_code'):
            walk(c, acc)
    return acc
for modname, m in sorted(sys.modules.items()):
    if m is None or modname.startswith(('lib', 'encodings')):
        continue
    try:
        items = list(vars(m).items())
    except Exception:
        continue
    for k, v in items:
        objs = [(k, v)]
        if isinstance(v, type) and getattr(v, '__module__', '') == modname:
            objs = [('%s.%s' % (k, n), f) for n, f in vars(v).items()]
        for label, f in objs:
            try:
                c = code_of(f)
            except Exception:
                c = None
            if c is None or not hasattr(c, 'co_names'):
                continue
            ns = walk(c, set())
            if 'movePath' in ns or 'getOnPlaneTime' in ns or 'PlaneMoveFilter' in ns:
                out.write('USER %s:%s line %s\n' % (modname, label, c.co_firstlineno))
out.close()
