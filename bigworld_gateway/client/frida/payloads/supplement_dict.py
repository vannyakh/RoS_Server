# READ-ONLY: how the client builds/filters the available-supplement dict (code names and
# constants) and the shape of the supplement data table. Calls no game or server method.
import sys
import types

out = open(OUT, 'w')


def info(label, func):
    code = getattr(func, 'func_code', None) or getattr(getattr(func, '__func__', None), 'func_code', None)
    if code is None:
        out.write('%s: none\n' % label)
        return
    out.write('%s\n  args=%r defaults=%r\n  names=%r\n  consts=%r\n' % (label, code.co_varnames[:code.co_argcount], getattr(func, 'func_defaults', None), code.co_names,
              [c for c in code.co_consts if not isinstance(c, types.CodeType)][:60]))
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            out.write('  nested %s args=%r names=%r consts=%r\n' % (c.co_name, c.co_varnames[:c.co_argcount], c.co_names, [x for x in c.co_consts if not isinstance(x, types.CodeType)][:40]))


su = sys.modules['supplement_utils']
isup = sys.modules['iSupplement']
for n in ('getAvailableSupplementDictByTime', 'getCurOpenSupplementIDByType', 'getSupplementKind', 'getSupplementFreeLotteryMaxTimes', 'OneSupplementBoxData'):
    info('supplement_utils.' + n, getattr(su, n, None))
for n in ('generalSupplementFilter', 'advanceSupplementFilter', 'newSupplementFilter'):
    info('iSupplement.' + n, getattr(isup, n, None))
info('iSupplement.queryAvailableSupplement', getattr(isup.iSupplement, 'queryAvailableSupplement', None))
info('iSupplement.openSupplyBoxFree', getattr(isup.iSupplement, 'openSupplyBoxFree', None))
out.write('supplement_utils.const keys=%r\n' % [k for k in vars(su) if k.isupper()])
for k in ('FREE_LOTTERY_TIME_INTERVAL', 'MULTIPLE_OPEN_SUPPLEMENT_ID', 'NO_PRIVILEGE_FREE_LOTTERY_MAX_TIME', 'PRIVILEGE_FREE_LOTTERY_MAX_TIME'):
    out.write('%s=%r\n' % (k, getattr(su, k, None)))
# supplement data table: find a data module with 'supplement' in its name
for mname, mod in sorted(sys.modules.items()):
    if mod is None or 'data' not in mname.lower() or 'suppl' not in mname.lower():
        continue
    d = getattr(mod, 'data', None)
    out.write('DATA %s type=%r len=%r\n' % (mname, type(d), len(d) if hasattr(d, '__len__') else None))
    if isinstance(d, dict):
        for i, (k, v) in enumerate(sorted(d.items())[:3]):
            out.write('  %r: %r\n' % (k, v if len(repr(v)) < 1500 else repr(v)[:1500]))
        out.write('  keys=%r\n' % sorted(d.keys())[:400])
# the player's cached state
import BigWorld
p = BigWorld.player()
for k in ('availSupplementDict', 'supplementFreeLotteryTimeStampDict', 'freeLotteryTimesDict', 'hasAlreadyShowSupplyID'):
    v = getattr(p, k, '<missing>')
    out.write('player.%s=%r\n' % (k, v if len(repr(v)) < 800 else repr(v)[:800]))
out.close()
