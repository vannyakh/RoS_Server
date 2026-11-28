# READ-ONLY (lane 2): daily-activity (Benefits) tables, sign-in setters, monthly Supreme box id.
# Calls only table iterators and pure helpers; writes nothing to the game state.
import sys
import types
out = open(OUT, 'w')


def w(s):
    out.write(s + '\n')


def fields(o):
    d = {}
    for k in dir(o):
        if k.startswith('_'):
            continue
        try:
            v = getattr(o, k)
        except Exception:
            continue
        if callable(v):
            continue
        d[k] = v
    return d


def code_of(f):
    f = getattr(f, 'im_func', f)
    for c in (getattr(f, 'func_closure', None) or ()):
        if isinstance(c.cell_contents, types.FunctionType):
            return c.cell_contents.func_code
    return getattr(f, 'func_code', None)


try:
    import const
    import shared
    props = sys.modules.get('properties') or getattr(shared, 'properties', None)
    w('DAILY_ACTIVITY_DATA_ID=%r WEEKLY_ACTIVITY_DATA_ID=%r' % (
        getattr(const, 'DAILY_ACTIVITY_DATA_ID', None), getattr(const, 'WEEKLY_ACTIVITY_DATA_ID', None)))
    for k, v in props.iterDailyActivityData():
        w('activity %r %r' % (k, fields(v)))
    for key in (getattr(const, 'DAILY_ACTIVITY_DATA_ID', None), getattr(const, 'WEEKLY_ACTIVITY_DATA_ID', None)):
        try:
            r = props.getActivityRewardData(key)
            w('reward %r %r' % (key, fields(r)))
        except Exception as e:
            w('reward %r error %r' % (key, e))
except Exception:
    import traceback
    w(traceback.format_exc())

try:
    for modname in ('iDtsSignin', 'iDailyActivity'):
        m = sys.modules.get(modname)
        if not m:
            w('no module %s' % modname)
            continue
        cls = getattr(m, modname, None)
        for n in sorted(dir(cls)):
            if n.startswith('__'):
                continue
            c = code_of(getattr(cls, n))
            if c:
                w('%s.%s args=%r names=%r consts=%r' % (modname, n, c.co_varnames[:c.co_argcount], c.co_names,
                                                        [x for x in c.co_consts if not isinstance(x, types.CodeType)][:12]))
except Exception:
    import traceback
    w(traceback.format_exc())

try:
    su = sys.modules['supplement_utils']
    w('getCurrentMonthSupplementID()=%r' % (su.getCurrentMonthSupplementID(),))
    import time
    w('time.time()=%r' % time.time())
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
