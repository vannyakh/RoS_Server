# READ-ONLY: guide data tables (keys) and the client code that checks guide completion,
# plus how onSyncSwitches applies a switch.
import sys
import types

out = open(OUT, 'w')


def w(s):
    out.write(s[:1500] + '\n')


def show(label, fn):
    if isinstance(fn, (staticmethod, classmethod)):
        fn = fn.__func__
    co = getattr(fn, 'func_code', None)
    if not isinstance(co, types.CodeType):
        w('== %s: none' % label)
        return
    w('== %s (%s:%d) vars=%r' % (label, co.co_filename, co.co_firstlineno, list(co.co_varnames)))
    w('   names=%r' % (list(co.co_names),))
    w('   consts=%r' % ([c if not isinstance(c, types.CodeType) else '<code>' for c in co.co_consts],))


try:
    import shared
    import BigWorld
    lp = sys.modules.get('legacyProperties') or getattr(shared, 'legacyProperties', None)
    for n in sorted(dir(lp)):
        if 'uide' in n and n.startswith('iter') and not n.endswith('RawData'):
            try:
                rows = list(getattr(lp, n)())
            except Exception as e:
                w('%s err %r' % (n, e))
                continue
            w('%s: %d rows, keys=%r' % (n, len(rows), [r[0] for r in rows][:60]))
    cls = type(BigWorld.player())
    for n in sorted(dir(cls)):
        if 'uide' in n and any(t in n for t in ('Finish', 'finish', 'isGuide', 'Begin', 'begin', 'check', 'Check')):
            show('PlayerAthlete.' + n, getattr(cls, n))
    show('PlayerAthlete.onSyncSwitches', getattr(cls, 'onSyncSwitches', None))
    sw = sys.modules.get('shared.switches') or sys.modules.get('switches')
    w('switches.SysEnableMonthSupply = %r' % (getattr(sw, 'SysEnableMonthSupply', '<missing>'),))
except Exception:
    import traceback
    w(traceback.format_exc())
out.close()
