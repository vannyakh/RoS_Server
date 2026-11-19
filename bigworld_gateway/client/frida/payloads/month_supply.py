# READ-ONLY: how the client picks the current monthly supply box (clock source and the
# monthly boxes' sale dates). Calls only pure local helpers.
import sys
import types
out = open(OUT, 'w')
su = sys.modules['supplement_utils']


def inner(f):
    for c in (getattr(f, 'func_closure', None) or ()):
        if isinstance(c.cell_contents, types.FunctionType):
            return c.cell_contents
    return f


for n in ('getCurrentMonthSupplementID', 'getCurrentSpringFestivalMonthSupplementID'):
    f = inner(getattr(su, n))
    c = f.func_code
    out.write('%s names=%r consts=%r\n' % (n, c.co_names, [x for x in c.co_consts if not isinstance(x, types.CodeType)]))
    for x in c.co_consts:
        if isinstance(x, types.CodeType):
            out.write('  nested %s names=%r consts=%r\n' % (x.co_name, x.co_names, x.co_consts[:10]))
lp = su.legacyProperties
for sid, o in lp.iterSupplementData():
    if su.getSupplementKind(sid) == su.SupplementKindEnum.MONTH_SUPPLEMENT if hasattr(su, 'SupplementKindEnum') else False:
        out.write('month box %s %s..%s sale=%s\n' % (sid, o.ONLINE_TIME, o.OFFLINE_TIME, o.IS_IN_SALE))
out.write('getCurrentMonthSupplementID()=%r\n' % (su.getCurrentMonthSupplementID(),))
import BigWorld
out.write('serverTime=%r time=%r\n' % (getattr(BigWorld, 'serverTime', lambda: None)(), __import__('time').time()))
out.close()
