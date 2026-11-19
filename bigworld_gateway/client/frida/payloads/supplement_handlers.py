# READ-ONLY: names/constants of the client's supply (draw) and portrait handlers, so the
# gateway can send replies in the shape they read. Calls nothing.
import sys
import types

out = open(OUT, 'w')


def info(label, func, depth=0):
    code = getattr(func, 'func_code', None) or getattr(getattr(func, '__func__', None), 'func_code', None)
    if code is None:
        out.write('%s: none\n' % label)
        return
    out.write('%s\n  args=%r\n  names=%r\n  consts=%r\n' % (label, code.co_varnames[:code.co_argcount], code.co_names,
              [c for c in code.co_consts if not isinstance(c, types.CodeType)][:60]))
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            out.write('  nested %s names=%r consts=%r\n' % (c.co_name, c.co_names, [x for x in c.co_consts if not isinstance(x, types.CodeType)][:40]))


pa = getattr(sys.modules.get('Athlete'), 'PlayerAthlete', None)
for name in ('onQueryAvailableSupplement', 'onOpenFreeSupplyBox', 'onOpenSupplyBox', 'onOpenSupplyBoxFailed',
             'onMultiOpenSupplyBox', 'onUpdateFreeLotteryTimeStampDict', 'onUpdateBuySupplementCntDict',
             'onUpdateAlreadyShowSupplyID', 'onRequestFilePickerToken', 'onSetPortrait'):
    f = None
    for klass in getattr(pa, '__mro__', ()):
        if name in vars(klass):
            f = vars(klass)[name]
            out.write('# %s defined in %s.%s\n' % (name, klass.__module__, klass.__name__))
            break
    info('PlayerAthlete.' + name, f)

# modules whose name mentions supply/supplement: their module-level data tables
for mname, mod in sorted(sys.modules.items()):
    if mod is None or not any(w in mname.lower() for w in ('suppl', 'supply', 'lottery')):
        continue
    keys = sorted(k for k in vars(mod) if not k.startswith('__'))
    out.write('MODULE %s keys=%r\n' % (mname, keys[:80]))
out.close()
