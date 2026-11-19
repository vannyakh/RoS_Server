# READ-ONLY: the client's currency-update handler table (currency id -> handler name) and
# how _setCurrencyAmount stores amounts. Calls only the dict getter.
import sys
import types
out = open(OUT, 'w')
import BigWorld
p = BigWorld.player()
try:
    d = p.getCurrencyUpdateHandleFuncDict()
    out.write('handlers=%r\n' % dict((k, getattr(v, '__name__', repr(v))) for k, v in d.items()))
except Exception as e:
    out.write('handlers err %r\n' % e)
pa = type(p)
for n in ('_setCurrencyAmount', 'getCurrencyUpdateHandleFuncDict'):
    for k in pa.__mro__:
        if n in vars(k):
            c = vars(k)[n].func_code
            out.write('%s names=%r consts=%r\n' % (n, c.co_names, [x for x in c.co_consts if not isinstance(x, types.CodeType)][:30]))
            break
for k in ('freeYuanbao', 'payYuanbao', 'yuanbao'):
    out.write('player.%s=%r\n' % (k, getattr(p, k, '<missing>')))
cu = sys.modules.get('currency_utils')
for n in ('getCurrencyAmount', 'getPlayerCurrency', 'getYuanbao'):
    f = getattr(cu, n, None)
    if f is not None and hasattr(f, 'func_code'):
        out.write('currency_utils.%s names=%r\n' % (n, f.func_code.co_names))
out.close()
