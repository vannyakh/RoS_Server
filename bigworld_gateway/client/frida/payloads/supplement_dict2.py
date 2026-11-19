# READ-ONLY: unwrap supplement_utils' decorated helpers (closure cells) and show the data
# table they read. Calls no game or server method.
import sys
import types

out = open(OUT, 'w')


def inner(func):
    for cell in (getattr(func, 'func_closure', None) or ()):
        v = cell.cell_contents
        if isinstance(v, types.FunctionType):
            return v
    return func


def info(label, func):
    func = inner(func)
    code = getattr(func, 'func_code', None)
    if code is None:
        out.write('%s: none\n' % label)
        return
    out.write('%s\n  args=%r\n  names=%r\n  consts=%r\n' % (label, code.co_varnames[:code.co_argcount], code.co_names,
              [c for c in code.co_consts if not isinstance(c, types.CodeType)][:60]))
    g = getattr(func, 'func_globals', {})
    for n in code.co_names:
        v = g.get(n)
        if isinstance(v, types.ModuleType):
            out.write('    global %s -> module %s\n' % (n, v.__name__))


su = sys.modules['supplement_utils']
for n in ('getAvailableSupplementDictByTime', 'getSupplementKind', 'getCurOpenSupplementIDByType', 'getSupplementFreeLotteryMaxTimes', 'getSupplementFreeLotteryTimeInterval', 'getSupplementCurrencyType'):
    info(n, getattr(su, n))
out.close()
