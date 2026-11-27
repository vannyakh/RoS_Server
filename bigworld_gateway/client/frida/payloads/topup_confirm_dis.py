# READ-ONLY: Top-Up confirm handlers and the PayGoods table (goods id -> diamonds). Calls no game method.
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

ath = sys.modules.get('Athlete')
pa = getattr(ath, 'PlayerAthlete', None)
for name in ('onConfirmPayOrder', 'onRequestRealNameAuthenCheckBeforeRequsetingPayGoods', 'onAddHistoryPayGoodsIDs'):
    if pa is not None and hasattr(pa, name):
        dump('PlayerAthlete.' + name, getattr(pa, name))
pu = sys.modules.get('pay_utils')
if pu is not None:
    out.write('pay_utils attrs: %r\n' % sorted(k for k in vars(pu) if not k.startswith('__')))
    for n in ('isPaying', 'setPaying', 'onPayFinish', 'finishPay'):
        if hasattr(pu, n) and code_of(getattr(pu, n)) is not None:
            dump('pay_utils.' + n, getattr(pu, n))
try:
    import shared.tables as T
    pg = getattr(T, 'PayGoods', None)
    out.write('PayGoods type %r\n' % type(pg))
    data = pg if isinstance(pg, dict) else getattr(pg, 'data', None) or {}
    for k in sorted(data)[:60]:
        out.write('PAYGOODS %r = %r\n' % (k, data[k]))
except Exception as e:
    out.write('PayGoods error %r\n' % (e,))
out.close()
