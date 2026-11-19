# READ-ONLY: HallTheme._createNewTheme lookup and whether theme ids have data.
import sys, types
out = open(OUT, 'w')


def w(s):
    out.write(s[:1600] + '\n')


try:
    mod = sys.modules['ui.main.HallTheme']
    cls = mod.HallTheme
    for n in ('_createNewTheme', '_clearOldTheme'):
        co = vars(cls)[n].func_code
        w('== %s vars=%r' % (n, list(co.co_varnames)))
        w('   names=%r' % (list(co.co_names),))
        w('   consts=%r' % ([c if not isinstance(c, types.CodeType) else '<code>' for c in co.co_consts],))
    import const, shared
    w('DEFAULT_ROS2_HALL_THEME_ID=%r' % getattr(const, 'DEFAULT_ROS2_HALL_THEME_ID', None))
    for k in dir(const):
        if 'THEME' in k.upper() and 'HALL' in k.upper():
            w('const.%s = %r' % (k, getattr(const, k)))
    lp = sys.modules.get('legacyProperties') or getattr(shared, 'legacyProperties', None)
    for fn in [n for n in dir(lp) if 'Theme' in n and n.startswith('get')][:20]:
        w('lp.%s' % fn)
    for tid in (0, 270000, 270001, 279001):
        for fn in ('getHallThemeData', 'getDtsHallThemeData', 'getHallThemeConfigData'):
            f = getattr(lp, fn, None)
            if f:
                try:
                    d = f(tid)
                    w('%s(%d) -> %r light=%r' % (fn, tid, d is not None, getattr(d, 'LIGHT_CONF', None) if d else None))
                except Exception as e:
                    w('%s(%d) err %r' % (fn, tid, e))
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
