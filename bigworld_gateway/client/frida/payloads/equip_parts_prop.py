# READ-ONLY: find the curr_equip_parts property on the player class (MRO) and disassemble its getter. Calls no game method.
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
    attr = vars(klass).get('curr_equip_parts')
    if attr is not None:
        out.write('found on %s.%s: %r\n' % (klass.__module__, klass.__name__, type(attr)))
        fget = getattr(attr, 'fget', None)
        if fget is not None:
            dump('%s.curr_equip_parts.fget' % klass.__name__, fget)
            for c in code_of(fget).co_names:
                if c.startswith('get') or c.startswith('_'):
                    f2 = getattr(klass, c, None)
                    if f2 is not None and code_of(f2) is not None:
                        dump('%s.%s' % (klass.__name__, c), f2)
        break
else:
    out.write('no class attribute; instance dict has it: %r\n' % ('curr_equip_parts' in getattr(p, '__dict__', {}),))
out.close()
