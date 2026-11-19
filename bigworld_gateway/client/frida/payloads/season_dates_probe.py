# READ-ONLY: season date table, monthly Supreme Supply dates, and the syncServerTime
# arithmetic (line map of the handler). Only reads data tables / calls pure getters.
import sys
import types

out = open(OUT, 'w')


def w(s):
    out.write(s[:2000] + '\n')


def unwrap(fn):
    for cell in (getattr(fn, 'func_closure', None) or ()):
        try:
            v = cell.cell_contents
        except ValueError:
            continue
        if isinstance(v, types.FunctionType):
            return unwrap(v)
    return fn


def show(label, fn):
    fn = unwrap(fn)
    co = getattr(fn, 'func_code', None)
    if co is None:
        w('== %s: none' % label)
        return
    w('== %s (%s:%d) vars=%r' % (label, co.co_filename, co.co_firstlineno, list(co.co_varnames)))
    w('   names=%r' % (list(co.co_names),))
    w('   consts=%r' % ([c if not isinstance(c, types.CodeType) else '<code>' for c in co.co_consts],))
    w('   code=%s' % ' '.join('%d' % ord(c) for c in co.co_code))


try:
    ut = sys.modules.get('common.utils') or sys.modules.get('utils')
    w('getCurrentSeasonID() = %r' % (ut.getCurrentSeasonID(),))
    for n in ('iterNewSeasonData',):
        f = getattr(ut, n, None)
        if f:
            rows = list(f())
            w('%s: %d rows' % (n, len(rows)))
            for r in rows[-8:]:
                w('   %r' % (r,))
    su = sys.modules.get('supplement_utils')
    show('supplement_utils.getCurrentMonthSupplementID', getattr(su, 'getCurrentMonthSupplementID', None))
    for k, v in sorted(vars(su).items()):
        if 'month' in k.lower() or 'MONTH' in k:
            w('su.%s = %r' % (k, v if not callable(v) else '<fn>'))
    import Avatar
    show('syncServerTime', vars(Avatar.Avatar).get('syncServerTime') if hasattr(Avatar, 'Avatar') else None)
    import BigWorld
    w('BigWorld.serverTime() = %r' % (BigWorld.serverTime(),))
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
