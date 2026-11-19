# READ-ONLY: checkDtsSigninNotSameDay and the sign-in data window.
import sys, types
out = open(OUT, 'w')
def w(s): out.write(s[:1500] + '\n')
try:
    mod = sys.modules.get('iDtsSignin') or sys.modules.get('entities.iDtsSignin')
    cls = getattr(mod, 'iDtsSignin', None)
    for n in ('checkDtsSigninNotSameDay', 'onCheckEnterSignInUI', 'onRequestDtsSignInAward'):
        f = vars(cls).get(n) if cls else None
        co = getattr(f, 'func_code', None)
        if isinstance(co, types.CodeType):
            w('== %s line %d vars=%r' % (n, co.co_firstlineno, list(co.co_varnames)))
            w('   names=%r' % (list(co.co_names),))
            w('   consts=%r' % ([c if not isinstance(c, types.CodeType) else '<code>' for c in co.co_consts],))
    import shared
    lp = sys.modules.get('legacyProperties') or getattr(shared, 'legacyProperties', None)
    rows = list(lp.iterDtsSigninData())
    w('signin rows %d first=%r' % (len(rows), [(k, [a for a in dir(v) if not a.startswith('_')]) for k, v in rows[:1]]))
except Exception:
    import traceback; w(traceback.format_exc())
out.close()
