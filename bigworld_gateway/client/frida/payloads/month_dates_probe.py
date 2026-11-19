# READ-ONLY: date ranges in the client's monthly-supplement and season data tables.
import sys
out = open(OUT, 'w')
def w(s): out.write(s[:600] + '\n')
try:
    import shared
    lp = sys.modules.get('legacyProperties') or getattr(shared, 'legacyProperties', None)
    rows = list(lp.iterMonthSupplementParamData())
    w('month rows %d' % len(rows))
    for k, v in rows[-6:]:
        w('  %r: start=%r end=%r id=%r' % (k, v.get('START_TIME') if hasattr(v, 'get') else v.START_TIME, v.get('END_TIME') if hasattr(v, 'get') else v.END_TIME, v.get('SUPPLEMENT_ID') if hasattr(v, 'get') else v.SUPPLEMENT_ID))
    for n in sorted(dir(lp)):
        if 'Season' in n and n.startswith('iter'):
            try:
                rs = list(getattr(lp, n)())
            except Exception as e:
                w('%s err %r' % (n, e)); continue
            w('%s %d rows, last: %r' % (n, len(rs), rs[-1] if rs else None))
except Exception:
    import traceback; w(traceback.format_exc())
out.close()
