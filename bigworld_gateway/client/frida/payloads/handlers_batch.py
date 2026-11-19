# READ-ONLY: names/consts of client Athlete handlers for VIP, mall buy, currency and hall
# team matching, plus where vipInfo is read. Calls nothing.
import sys
import types
out = open(OUT, 'w')
pa = sys.modules['Athlete'].PlayerAthlete


def info(name):
    f = None
    for k in pa.__mro__:
        if name in vars(k):
            f = vars(k)[name]
            break
    code = getattr(f, 'func_code', None)
    if code is None:
        out.write('%s: none\n' % name)
        return
    out.write('%s (%s)\n  args=%r\n  names=%r\n  consts=%r\n' % (name, k.__name__, code.co_varnames[:code.co_argcount], code.co_names[:50], [c for c in code.co_consts if not isinstance(c, types.CodeType)][:40]))
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            out.write('  nested %s names=%r consts=%r\n' % (c.co_name, c.co_names[:30], [x for x in c.co_consts if not isinstance(x, types.CodeType)][:20]))


for n in ('syncVipInfo', 'buyDtsHallProp', 'buyMallGoodInAppearanceMall', 'buyMallGood', 'onBuyMallGood', 'onBuyMallGoodFailed',
          'onCurrencyUpdated', 'matchBattleGround', 'syncMatchState', 'onEnterHallTeam', 'syncMatchingProgress',
          'onGetMatchedTeamInfo', 'onUpdateLuckyCarnivalData', 'onMatchGameTypesUpdate'):
    info(n)
# who reads vipInfo
hits = []
for mname, mod in sys.modules.items():
    if mod is None:
        continue
    try:
        items = list(vars(mod).items())
    except Exception:
        continue
    for nm, obj in items:
        try:
            fs = []
            if isinstance(obj, types.FunctionType):
                fs.append((nm, obj.func_code))
            elif isinstance(obj, (type, types.ClassType)) and getattr(obj, '__module__', None) == mname:
                for an, av in vars(obj).items():
                    f = getattr(av, 'func_code', None)
                    if f is not None:
                        fs.append((nm + '.' + an, f))
            for fn, code in fs:
                if 'vipInfo' in code.co_names:
                    hits.append('%s.%s consts=%r' % (mname, fn, [c for c in code.co_consts if isinstance(c, str)][:15]))
        except Exception:
            pass
out.write('vipInfo readers:\n  ' + '\n  '.join(hits[:30]) + '\n')
out.close()
