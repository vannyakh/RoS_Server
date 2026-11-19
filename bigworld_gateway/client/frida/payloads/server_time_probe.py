# READ-ONLY: how the client derives server time, and which dates the date-gated lobby
# screens (monthly Supreme Supply, season pass) compare it with. Only calls pure getters.
import sys
import time
import types

out = open(OUT, 'w')


def w(s):
    out.write(s[:1500] + '\n')


def code_of(o):
    if isinstance(o, (staticmethod, classmethod)):
        o = o.__func__
    co = getattr(o, 'func_code', None)
    return co if isinstance(co, types.CodeType) else None


def show(label, o):
    co = code_of(o)
    if co is None:
        w('== %s: (none)' % label)
        return
    w('== %s (%s:%d) vars=%r' % (label, co.co_filename, co.co_firstlineno, list(co.co_varnames)))
    w('   names=%r' % (list(co.co_names),))
    w('   consts=%r' % ([c if not isinstance(c, types.CodeType) else '<code>' for c in co.co_consts],))


try:
    import BigWorld
    p = BigWorld.player()
    cu = sys.modules.get('client_utils')
    w('device time.time() = %r' % time.time())
    for n in ('getServerSysTime', 'getServerTime', 'getServerTimeZone', 'getServerDateTime'):
        f = getattr(cu, n, None)
        show('client_utils.' + n, f)
        if f is not None:
            try:
                w('   value = %r' % (f(),))
            except Exception as e:
                w('   value error %r' % e)
    for n in ('serverTimeOffset', 'serverTimeDiff', 'timeOffset', 'serverTime'):
        for mod in (cu, sys.modules.get('Globals')):
            if mod is not None and hasattr(mod, n):
                w('%s.%s = %r' % (mod.__name__, n, getattr(mod, n)))
    cls = type(p)
    for n in ('syncServerTime', 'syncServerTimeZone'):
        show('PlayerAthlete.' + n, getattr(cls, n, None))

    # functions that decide the monthly box / season deadlines
    want = ('getCurrentMonthSupplementID', 'getSeasonEndTime', 'getSeasonLeftDays', 'getCurSeasonEndTime',
            'getBraveBookSeasonEndTime', 'getCurrentSeasonID', 'getCurSeason')
    for modname, mod in sorted(sys.modules.items()):
        if mod is None:
            continue
        try:
            items = vars(mod).items()
        except Exception:
            continue
        for k, v in items:
            if k in want:
                show('%s.%s' % (modname, k), v)
            elif isinstance(v, (type, types.ClassType)):
                for n in want:
                    if n in vars(v):
                        show('%s.%s.%s' % (modname, k, n), vars(v)[n])
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
